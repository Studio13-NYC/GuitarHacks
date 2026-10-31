"""Split a combined guitar WAV with a local two-source HTDemucs checkpoint."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
import yaml
from demucs.apply import apply_model
from demucs.htdemucs import HTDemucs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    settings = dict(config["htdemucs"])
    # PyYAML treats the published YAML's "1e-3" notation as a string.
    settings["dconv_init"] = float(settings["dconv_init"])
    # The training configuration includes this single-band setting; stock
    # HTDemucs already operates this way and has no num_subbands argument.
    if settings.pop("num_subbands", 1) != 1:
        raise ValueError("Multiband checkpoint is unsupported")
    training = config["training"]
    sources = training["instruments"]
    if sources != ["lead", "rhythm"]:
        raise ValueError(f"Unexpected sources: {sources}")
    sr, channels = training["samplerate"], training["channels"]
    metadata = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate,channels", "-of", "json", str(args.source)
    ]))["streams"][0]
    if (int(metadata["sample_rate"]), metadata["channels"]) != (sr, channels):
        raise ValueError("Input must match model format; no resampling is performed")
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(args.source), "-map", "0:a:0",
        "-f", "f32le", "-c:a", "pcm_f32le", "pipe:1"
    ])
    audio = np.frombuffer(raw, dtype="<f4").reshape(-1, channels)
    if not np.isfinite(audio).all():
        raise ValueError("Nonfinite input samples")
    wav = torch.from_numpy(audio.T.copy())
    torch.manual_seed(0)
    model = HTDemucs(sources=sources, samplerate=sr, audio_channels=channels,
                    segment=training["segment"], **settings)
    state = torch.load(args.model, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval()
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    with torch.inference_mode():
        estimates = apply_model(model, ((wav - mean) / std)[None],
                                device=args.device, shifts=1, overlap=0.5,
                                split=True, progress=True)[0].cpu()
    estimates = estimates * std + mean
    if tuple(estimates.shape) != (2, channels, len(audio)):
        raise ValueError("Model changed the sample count")
    if not torch.isfinite(estimates).all():
        raise ValueError("Nonfinite output samples")
    args.output.mkdir(parents=True)
    for name, estimate in zip(sources, estimates):
        subprocess.run([
            "ffmpeg", "-v", "error", "-n", "-f", "f32le", "-ar", str(sr),
            "-ac", str(channels), "-i", "pipe:0", "-c:a", "pcm_f32le",
            str(args.output / f"{name}-guitar.wav")
        ], input=estimate.T.contiguous().numpy().astype("<f4").tobytes(), check=True)
    report = {
        "source": str(args.source.resolve()),
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "checkpoint_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "model_credit": "HTDemucs4 Lead-Rhythm Guitar by Dry Paint Dealer Undr",
        "sources": sources, "sample_rate": sr, "channels": channels,
        "samples_per_channel": len(audio), "start_offset_samples": 0,
        "resampling": False, "trimming": False, "device": args.device,
        "seed": 0, "shifts": 1, "overlap": 0.5,
        "note": "Independent model estimates; not guaranteed to sum to the input."
    }
    (args.output / "separation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
