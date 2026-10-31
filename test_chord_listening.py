import unittest
import numpy as np
from audio import PitchTracker
from chord_listening import ChordPass


class ListeningTests(unittest.TestCase):
    def setUp(self):
        self.tracker = PitchTracker(-40, .3)
        self.pass_ = ChordPass(-40)
        self.now = 1.
        self.rng = np.random.default_rng(17)

    def send(self, samples, overflow=False):
        self.now += len(samples)/48000
        frame, note = self.tracker.process(samples, 48000, overflow, self.now)
        self.pass_.frame(frame)
        if note: self.pass_.note(note)

    def quiet(self, blocks=16):
        for _ in range(blocks): self.send(np.zeros(4096))

    def tone(self, midi, blocks=8, amplitude=.15):
        hz = 440*2**((midi-69)/12)
        for _ in range(blocks): self.send(amplitude*np.sin(2*np.pi*hz*np.arange(4096)/48000))

    def begin(self):
        self.quiet(20)
        self.tone(40, 3)
        self.quiet(8)
        self.assertEqual(self.pass_.stage, 'strings')

    def test_strum_is_not_a_string_and_full_chord_maps_known_strings(self):
        self.begin()
        self.assertEqual(self.pass_.index, 0)
        for midi in [40, 47, 52, 56, 59, 64]:
            self.tone(midi)
            self.quiet(8)
        self.assertEqual(self.pass_.stage, 'complete')
        self.assertEqual(self.pass_.frets, [0, 2, 2, 1, 0, 0])

    def test_highest_root_preset_can_capture_its_fret_14_notes(self):
        self.begin()
        for midi in [52, 59, 64, 68, 71, 76]:
            self.tone(midi);self.quiet(8)
        self.assertEqual(self.pass_.stage, 'complete')
        self.assertEqual(self.pass_.frets, [12, 14, 14, 13, 12, 12])

    def test_percussive_muted_pluck_advances_but_silence_does_not(self):
        self.begin()
        self.quiet(40)
        self.assertEqual(self.pass_.index, 0)
        x = self.rng.normal(0, .15, 4096)*np.exp(-np.arange(4096)/1200)
        self.send(x)
        self.quiet(8)
        self.assertEqual(self.pass_.index, 1)
        self.assertEqual(self.pass_.kinds[0], 'muted')
        self.assertIsNone(self.pass_.frets[0])

    def test_short_or_quiet_pitched_note_is_not_auto_muted(self):
        self.begin()
        self.tone(40, 1)
        self.quiet(12)
        self.assertEqual(self.pass_.index, 0)
        self.tone(40, 8, .005)
        self.quiet(12)
        self.assertEqual(self.pass_.index, 0)

    def test_sustained_noise_clipping_and_overflow_do_not_advance(self):
        for kind in ['sustained', 'clip', 'overflow']:
            self.setUp();self.begin()
            for _ in range(8 if kind=='sustained' else 1):
                x = self.rng.normal(0, .1, 4096)
                if kind=='clip': x[0] = 1.
                self.send(x, kind=='overflow')
            self.quiet(10)
            self.assertEqual(self.pass_.index, 0, kind)

    def test_wrong_range_does_not_snap_to_chord_and_previous_string_retries(self):
        self.begin();self.tone(64);self.quiet(8)
        self.assertEqual(self.pass_.index, 0)
        self.tone(41);self.quiet(8)  # Wrong chord tone must still be captured honestly.
        self.assertEqual(self.pass_.frets[0], 1)
        self.pass_.retry(self.now)
        self.assertEqual(self.pass_.index, 0)
        self.assertEqual(self.pass_.kinds[0], 'pending')
        self.pass_.note(dict(midi=40, hz=82.4, cents=0, periodicity=1, started=0, monotonic=0))
        self.assertEqual(self.pass_.index, 0)

    def test_manual_muted_requires_string_stage(self):
        self.pass_.muted(self.now)
        self.assertEqual(self.pass_.index, 0)
        self.begin();self.pass_.muted(self.now)
        self.assertEqual(self.pass_.index, 1)
        self.assertEqual(self.pass_.kinds[0], 'muted-manual')

    def test_first_pick_and_pick_after_muted_need_only_one_quiet_gap(self):
        self.quiet(15)  # Completes the measured quiet background.
        self.tone(40, 3)
        self.quiet(4)
        self.assertEqual(self.pass_.stage, 'strings')
        x=self.rng.normal(0,.15,4096)*np.exp(-np.arange(4096)/1200)
        self.send(x);self.quiet(4)
        self.assertEqual(self.pass_.index,1)
        self.tone(45)
        self.assertEqual(self.pass_.index,2)


if __name__ == '__main__': unittest.main()
