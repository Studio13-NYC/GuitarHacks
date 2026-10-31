import unittest
import numpy as np
from audio import PitchTracker
from guitar_setup import GuitarSetup, OPEN


class GuitarSetupTests(unittest.TestCase):
    def setUp(self):
        self.setup=GuitarSetup();self.tracker=PitchTracker(-36,.3);self.now=1.

    def send(self,x):
        self.now+=len(x)/48000
        f,_=self.tracker.process(x,48000,now=self.now)
        self.setup.frame(f)

    def quiet(self,n=16):
        for _ in range(n):self.send(np.zeros(4096))

    def tone(self,midi,n=8,amplitude=.008,cents=0):
        x=amplitude*np.sin(2*np.pi*(440*2**((midi-69+cents/100)/12))*np.arange(4096)/48000)
        for _ in range(n):self.send(x)

    def test_notes_below_old_gate_calibrate_and_tuning_is_measured(self):
        self.quiet()
        for midi in OPEN:self.tone(midi,cents=-35);self.quiet(8)
        self.assertEqual(self.setup.stage,'ready')
        self.assertLess(self.setup.gate,-45)
        for r in self.setup.readings:self.assertAlmostEqual(r['cents'],-35,delta=2)

    def test_wrong_note_and_silence_do_not_advance(self):
        self.quiet();self.tone(59);self.quiet(8)
        self.assertEqual(self.setup.index,0)
        self.assertIn('waiting for string 6',self.setup.message)
        self.tone(40);self.assertEqual(self.setup.index,1)
        self.tone(45)  # no mute: do not accept the next string
        self.assertEqual(self.setup.index,1)
        self.quiet(8);self.tone(45);self.assertEqual(self.setup.index,2)

    def test_pitched_background_never_arms_and_noise_is_rejected(self):
        self.tone(40,30,amplitude=.2)
        self.assertEqual(self.setup.stage,'calibration-noise')
        rng=np.random.default_rng(8)
        for _ in range(20):self.send(rng.normal(0,.2,4096))
        self.assertEqual(self.setup.stage,'error')

    def test_optional_fretted_check_requires_the_requested_note(self):
        self.setup=GuitarSetup((4,5));self.quiet()
        self.tone(59);self.assertEqual(self.setup.stage,'calibration-note')
        self.quiet(8);self.tone(64)
        self.assertEqual(self.setup.stage,'ready')

    def test_detuned_neighbour_is_not_learned_as_the_open_string(self):
        self.quiet();self.tone(41,cents=-35)
        self.assertEqual(self.setup.index,0)
        self.assertEqual(self.setup.readings,[])


if __name__=='__main__':unittest.main()
