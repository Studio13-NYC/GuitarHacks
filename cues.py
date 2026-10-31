"""A quiet, optional completion cue through the Windows default output."""
import math
from pathlib import Path
import struct
import wave
import winsound


class CuePlayer:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "soft-cue.wav"

    def play(self):
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            rate, duration = 22050, .18
            samples = []
            for i in range(int(rate * duration)):
                t = i / rate
                envelope = min(1, t / .012) * (1 - t / duration) ** 2
                samples.append(int(32767 * .055 * envelope * math.sin(2 * math.pi * 660 * t)))
            with wave.open(str(self.path), "wb") as output:
                output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                output.writeframes(struct.pack(f"<{len(samples)}h", *samples))
        winsound.PlaySound(str(self.path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
