"""Bounded single-note monitoring; detections are observations, not lesson scores."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
import sounddevice as sd


NOTE_NAMES = ["C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"]


def estimate_pitch(samples: np.ndarray, sample_rate: float):
    """YIN-style difference estimate for one pitched sound, 70-850 Hz.

    A periodic signal is not proof that just one guitar string was played.
    The returned periodicity value is not a calibrated probability.
    """
    # Average adjacent samples before decimation. Preserve enough cycles for E2.
    x = np.asarray(samples, dtype=np.float64)
    x = x[: len(x) // 4 * 4].reshape(-1, 4).mean(axis=1)
    x -= x.mean()
    rate = sample_rate / 4
    low = max(2, int(rate / 850))
    high = min(int(rate / 70), len(x) // 2 - 1)
    if high <= low or np.sqrt(np.mean(x * x)) < 1e-7:
        return None
    window = len(x) - high
    shifts = np.lib.stride_tricks.sliding_window_view(x, window)[: high + 1]
    difference = np.sum((shifts - x[:window]) ** 2, axis=1)
    normalized = np.ones(high + 1)
    normalized[1:] = difference[1:] * np.arange(1, high + 1) / np.maximum(np.cumsum(difference[1:]), 1e-20)
    candidates = np.flatnonzero(normalized[low:high] < 0.12)
    if not len(candidates):
        return None
    lag = int(candidates[0] + low)
    while lag + 1 < high and normalized[lag + 1] < normalized[lag]:
        lag += 1
    left, center, right = normalized[lag - 1: lag + 2]
    denominator = left - 2 * center + right
    adjustment = float(np.clip(0.5 * (left - right) / denominator, -0.5, 0.5)) if abs(denominator) > 1e-12 else 0.0
    frequency = float(rate / (lag + adjustment))
    fractional_midi = 69 + 12 * np.log2(frequency / 440)
    midi = int(round(fractional_midi))
    return {
        "midi": midi,
        "note": f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}",
        "hz": round(frequency, 2),
        "cents": round(float(100 * (fractional_midi - midi)), 1),
        "periodicity": round(float(1 - normalized[lag]), 3),
    }


def choose_device(name: str):
    apis = sd.query_hostapis()
    matches = [(i, d) for i, d in enumerate(sd.query_devices())
               if name.casefold() in d["name"].casefold()
               and d["max_input_channels"] >= 2
               and apis[d["hostapi"]]["name"] == "Windows WASAPI"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one WASAPI input matching {name!r}; found {len(matches)}. No fallback input selected.")
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--device", default="M12 In 5/6 - Guitar-DI")
    parser.add_argument("--pair-channel", type=int, choices=[1, 2], default=1,
                        help="1 = Model 12 channel 5; 2 = channel 6 on the default pair")
    parser.add_argument("--gate-db", type=float, default=-45)
    parser.add_argument("--levels-only", action="store_true")
    args = parser.parse_args()
    if not 0 < args.seconds <= 600:
        parser.error("Use a duration above zero and no more than 600 seconds.")
    index, device = choose_device(args.device)
    rate = float(device["default_samplerate"])
    sd.check_input_settings(device=index, channels=2, dtype="float32", samplerate=rate)
    folder = Path(__file__).resolve().parent / "sessions"
    folder.mkdir(exist_ok=True)
    log_path = folder / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.jsonl"
    with log_path.open("x", encoding="utf-8") as log:
        def emit(kind, **values):
            record = {"utc": datetime.now(timezone.utc).isoformat(), "type": kind, **values}
            line = json.dumps(record, allow_nan=False)
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()

        count, frames, overflows = 0, 0, 0
        maxima = np.zeros(2)
        recent = []
        last_note = None
        silent_blocks = 0
        start = time.monotonic()
        last_status = start
        try:
            with sd.InputStream(device=index, channels=2, samplerate=rate,
                                blocksize=4096, dtype="float32", latency="high",
                                extra_settings=sd.WasapiSettings(exclusive=False)) as stream:
                start = last_status = time.monotonic()
                emit("listening", device=device["name"], pair_channel=args.pair_channel,
                     sample_rate=rate, seconds=args.seconds, latency=stream.latency,
                     log=str(log_path), scoring="disabled; calibration observations only")
                while time.monotonic() - start < args.seconds:
                    data, overflowed = stream.read(4096)
                    frames += len(data)
                    overflows += int(overflowed)
                    rms = np.sqrt(np.mean(data.astype(np.float64) ** 2, axis=0))
                    maxima = np.maximum(maxima, np.max(np.abs(data), axis=0))
                    db = 20 * np.log10(np.maximum(rms, 1e-10))
                    selected = data[:, args.pair_channel - 1]
                    result = None
                    if not args.levels_only and db[args.pair_channel - 1] >= args.gate_db and not overflowed:
                        result = estimate_pitch(selected, rate)
                    if result is None:
                        recent.clear()
                        silent_blocks += 1
                        if silent_blocks >= 3:
                            last_note = None
                    else:
                        silent_blocks = 0
                        recent.append(result)
                        recent = recent[-4:]
                        if len(recent) == 4 and len({r["midi"] for r in recent}) == 1:
                            if result["midi"] != last_note:
                                count += 1
                                # Median across consecutive frames reduces attack jitter.
                                report = dict(result)
                                for field in ["hz", "cents", "periodicity"]:
                                    report[field] = round(float(np.median([r[field] for r in recent])), 3)
                                emit("note", **report, rms_db=round(float(db[args.pair_channel - 1]), 1),
                                     clipped=bool(np.max(np.abs(selected)) >= 0.999))
                                last_note = result["midi"]
                    now = time.monotonic()
                    if now - last_status >= 5:
                        emit("levels", elapsed=round(now-start, 1),
                             pair_rms_db=[round(float(v), 1) for v in db],
                             selected_pair_channel=args.pair_channel, note_events=count, overflows=overflows)
                        last_status = now
        except KeyboardInterrupt:
            emit("interrupted")
        except Exception as error:
            emit("error", message=str(error))
            raise
        finally:
            emit("stopped", elapsed=round(time.monotonic()-start, 1), frames=frames,
                 note_events=count, peak_db=[round(float(20*np.log10(max(v, 1e-10))), 1) for v in maxima],
                 overflows=overflows, log=str(log_path))


if __name__ == "__main__":
    main()
