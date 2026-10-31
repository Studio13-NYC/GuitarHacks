"""Measured guitar setup, independent of quiz answers and the saved trigger gate."""
import math
import statistics

OPEN = (40, 45, 50, 55, 59, 64)
NAMES = ('low E', 'A', 'D', 'G', 'B', 'high E')


class GuitarSetup:
    def __init__(self, check=None):
        self.stage = 'calibration-noise'
        self.index = 0 if check is None else check[0]
        self.check = check
        self.readings = []
        self.noise = []
        self.elapsed = 0.
        self.quiet = 0.
        self.stable = []
        self.armed = False
        self.floor = -90.
        self.gate = -75.
        self.message = 'Mute all strings for the background check.'

    def prompt(self):
        fret = self.check[1] if self.check else 0
        self.message = f'Play string {6-self.index} ({NAMES[self.index]}), '+(f'fret {fret}.' if fret else 'open.')+' Let it ring briefly, then mute.'

    def frame(self, f):
        if self.stage in ('ready', 'error'): return
        dt = f.get('duration', 0.)
        raw = f.get('raw_pitch')
        if f.get('clipped') or f.get('overflow'):
            self.stable = [];self.quiet = 0.;self.armed = False
            self.message = 'Input clipped or interrupted. Mute, then retry.'
            return
        if self.stage == 'calibration-noise':
            if raw and raw.get('periodicity', 0) >= .95:
                self.noise = [];self.elapsed = 0.
                self.message = 'A note is still ringing. Mute all strings for the background check.'
                return
            self.noise.append(f['db']);self.elapsed += dt
            if self.elapsed >= 1.2:
                self.floor = sorted(self.noise)[int(.9*(len(self.noise)-1))]
                if self.floor > -25:
                    self.stage = 'error';self.message = 'Background is too loud. Check input/channel and reduce noise, then Recalibrate.'
                    return
                self.gate = max(-75., self.floor+12)
                self.stage = 'calibration-note';self.armed = True;self.prompt()
            return
        below = f['db'] < self.gate-6
        self.quiet = self.quiet+dt if below else 0.
        if self.quiet >= .3: self.armed = True
        if not self.armed: return
        expected = OPEN[self.index]+(self.check[1] if self.check else 0)
        if not raw or raw.get('periodicity', 0) < .95 or f['db'] < self.gate:
            self.stable = []
            if not below: self.message = 'Sound is not a clear steady note. Mute the other strings and pick again.'
            return
        cents = 1200*math.log2(raw['hz']/(440*2**((expected-69)/12)))
        if abs(cents) > 45:
            self.stable = []
            self.message = f'Heard {raw["note"]}; waiting for string {6-self.index}'+(f' fret {self.check[1]}.' if self.check else ' open.')
            return
        self.stable.append((dt,cents,f['db']))
        if max(x[1] for x in self.stable)-min(x[1] for x in self.stable)>35:
            self.stable = [self.stable[-1]]
        if sum(x[0] for x in self.stable)<.3: return
        self.readings.append(dict(string=6-self.index,cents=statistics.median(x[1] for x in self.stable),db=statistics.median(x[2] for x in self.stable)))
        self.stable = [];self.armed = False;self.quiet = 0.
        if self.check or self.index == 5:
            self.stage = 'ready'
            self.gate = max(-75.,self.floor+10,min(x['db'] for x in self.readings)-12)
            self.message = 'Calibration passed. Listening is ready — click or say Go.'
        else:
            self.index += 1;self.prompt()
