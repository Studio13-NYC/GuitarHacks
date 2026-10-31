"""Unscored background and open-string reference capture shared by all lessons."""
import math

OPEN_STRINGS = (
    (6, 40, "low E", "The thickest string (string 6)."),
    (5, 45, "A", "The second-thickest string (string 5)."),
    (4, 50, "D", "The third-thickest string (string 4)."),
    (3, 55, "G", "The third-thinnest string (string 3)."),
    (2, 59, "B", "The second-thinnest string (string 2)."),
    (1, 64, "high E", "The thinnest string (string 1)."),
)


class Calibration:
    def __init__(self, minimum_gate):
        self.stage = "noise"
        self.index = 0
        self.minimum_gate = minimum_gate
        self.gate = minimum_gate
        self.noise = []
        self.noise_seconds = 0.0
        self.reference_cents = {}
        self.readings = []
        self.armed = False
        self.started = 0.0

    @property
    def current(self):
        return OPEN_STRINGS[self.index]

    def frame(self, frame):
        if frame.get("overflow") or frame.get("clipped"):
            return False
        if self.stage == "noise":
            self.noise.append(frame["db"])
            self.noise_seconds += frame.get("duration", 0)
            if self.noise_seconds >= 1.2:
                ordered=sorted(self.noise)
                self.noise_floor=ordered[int(.9*(len(ordered)-1))]
                self.gate=min(-15, max(self.minimum_gate, self.noise_floor+10))
                self.stage="strings"
                self.started=frame["monotonic"]
                return True
        elif self.stage == "strings" and frame["monotonic"] >= self.started and frame.get("quiet"):
            self.armed=True
        return False

    def note(self, pitch):
        if self.stage != "strings" or not self.armed or pitch.get("started",0) < self.started:
            return "ignored"
        self.armed=False
        if pitch.get("periodicity",0)<.95 or pitch.get("clipped"):
            return "unclear"
        string, expected, _, _ = self.current
        # Calibration permits modest detuning; lesson answers use the measured reference ±25 cents.
        cents=1200*math.log2(pitch["hz"]/(440*2**((expected-69)/12)))
        if abs(cents)>80:
            return "wrong"
        self.reference_cents[string]=cents
        self.readings.append(dict(string=string,hz=pitch["hz"],cents=cents,db=pitch["db"]))
        self.started=pitch["monotonic"]
        if self.index == len(OPEN_STRINGS)-1:
            self.stage="done"
            # Keep the trigger below the quietest reference, but above measured background.
            softest=min(r["db"] for r in self.readings)
            self.gate=min(-15,max(self.minimum_gate,self.noise_floor+10,softest-10))
            return "done"
        self.index+=1
        return "accepted"

