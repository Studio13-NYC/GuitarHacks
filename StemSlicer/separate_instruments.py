"""Separate locally and preserve unclipped float estimates for final export."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
from demucs.api import Separator

from export_stems import decode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="htdemucs_6s")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    meta, audio = decode(args.source)
    torch.manual_seed(0)
    separator = Separator(model=args.model, device="cuda", shifts=1, progress=True)
    sr, channels = separator.samplerate, separator.audio_channels
    if (int(meta["sample_rate"]), meta["channels"]) != (sr, channels):
        raise ValueError("Source must match model format; no resampling is performed")
    original, stems = separator.separate_tensor(torch.from_numpy(audio.T.copy()), sr=sr)
    assert np.array_equal(original.numpy().T, audio)
    args.output.mkdir(parents=True)
    for name, samples in stems.items():
        samples = samples.detach().cpu().T.contiguous().numpy()
        assert samples.shape == audio.shape and np.isfinite(samples).all()
        # Demucs 4.1.0's own float WAV writer clamps values to +/-1. FFmpeg
        # preserves float overs so a single shared gain can be applied later.
        subprocess.run([
            "ffmpeg", "-v", "error", "-n", "-f", "f32le", "-ar", str(sr),
            "-ac", str(channels), "-i", "pipe:0", "-c:a", "pcm_f32le",
            str(args.output / f"{name}.wav")
        ], input=samples.astype("<f4").tobytes(), check=True)
    report = {
        "source": str(args.source.resolve()),
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "model": args.model, "seed": 0, "shifts": 1, "device": "cuda",
        "sample_rate": sr, "channels": channels, "samples_per_channel": len(audio),
        "start_offset_samples": 0, "resampling": False, "trimming": False,
        "stems": list(stems), "float_writer": "ffmpeg pcm_f32le, no clamping"
    }
    (args.output / "separation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
