"""Split a backing WAV into two sample-aligned, complementary 24-bit WAVs."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
import torch
from demucs.api import Separator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    args = parser.parse_args()
    ffprobe = args.ffmpeg.with_name("ffprobe.exe")
    metadata = json.loads(subprocess.check_output([
        str(ffprobe), "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate,channels", "-of", "json", str(args.source)
    ]))["streams"][0]
    sample_rate, channels = int(metadata["sample_rate"]), metadata["channels"]
    if (sample_rate, channels) != (44100, 2):
        raise ValueError("This workflow requires a stereo 44100 Hz backing WAV; no resampling is performed.")
    if args.output.exists():
        raise FileExistsError(args.output)

    def decode(path):
        raw = subprocess.check_output([
            str(args.ffmpeg), "-v", "error", "-i", str(path),
            "-map", "0:a:0", "-f", "f32le", "-c:a", "pcm_f32le", "pipe:1"
        ])
        return np.frombuffer(raw, dtype="<f4").reshape(-1, channels).copy()

    source = decode(args.source)
    torch.manual_seed(0)
    separator = Separator(model="htdemucs", device="cuda", shifts=1, progress=True)
    if separator.samplerate != sample_rate or separator.audio_channels != channels:
        raise ValueError("Model format mismatch")
    original, stems = separator.separate_tensor(torch.from_numpy(source.T.copy()), sr=sample_rate)
    assert original.shape == (channels, len(source))
    assert np.array_equal(original.numpy().T, source), "Separator changed the source timeline"
    drums = stems["drums"].detach().cpu().numpy().T.astype(np.float64)
    assert drums.shape == source.shape, "Drum estimate changed sample count"
    source = source.astype(np.float64)
    remainder = source - drums
    assert np.isfinite(drums).all() and np.isfinite(remainder).all()
    peak = max(float(np.abs(drums).max()), float(np.abs(remainder).max()))
    gain = min(1.0, 10 ** (-1 / 20) / peak) if peak else 1.0
    args.output.mkdir(parents=True)

    def export(name, audio):
        path = args.output / name
        subprocess.run([
            str(args.ffmpeg), "-v", "error", "-n", "-f", "f64le", "-ar", str(sample_rate),
            "-ac", str(channels), "-i", "pipe:0", "-c:a", "pcm_s24le", str(path)
        ], input=np.ascontiguousarray(audio * gain, dtype="<f8").tobytes(), check=True)
        return path

    drums_path = export("drums.wav", drums)
    backing_path = export("backing-without-drums.wav", remainder)
    saved_drums, saved_backing = decode(drums_path), decode(backing_path)
    assert saved_drums.shape == source.shape == saved_backing.shape
    reconstructed = saved_drums.astype(np.float64) + saved_backing.astype(np.float64)
    error = reconstructed - source * gain
    max_error = float(np.abs(error).max())
    assert max_error <= 2 / 2**23, f"Recombined WAVs differ from the source: {max_error}"
    report = {
        "source": str(args.source.resolve()),
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "model": "htdemucs", "device": "cuda", "shifts": 1, "random_seed": 0,
        "sample_rate": sample_rate, "channels": channels, "bits_per_sample": 24,
        "samples_per_channel": len(source), "duration_seconds": len(source) / sample_rate,
        "start_offset_samples": 0, "resampling": False, "trimming": False,
        "common_gain_db": 20 * math.log10(gain),
        "recombined_vs_source_max_sample_error": max_error,
        "recombined_vs_source_rms_error": float(np.sqrt(np.mean(error**2))),
        "drums_peak_dbfs": 20 * math.log10(float(np.abs(saved_drums).max())),
        "backing_without_drums_peak_dbfs": 20 * math.log10(float(np.abs(saved_backing).max())),
        "files": [str(drums_path.resolve()), str(backing_path.resolve())],
    }
    (args.output / "alignment-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
