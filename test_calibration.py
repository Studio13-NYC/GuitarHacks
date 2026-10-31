import unittest
from calibration import Calibration


class CalibrationTests(unittest.TestCase):
    def test_background_and_six_strings_produce_references_without_scores(self):
        c = Calibration(-36)
        for i in range(15):
            c.frame(dict(db=-50, duration=.1, monotonic=i, quiet=True, overflow=False))
        self.assertEqual(c.stage, "strings")
        self.assertEqual(c.gate, -36)
        for i, midi in enumerate([40,45,50,55,59,64]):
            now=20+i*3
            c.frame(dict(db=-60,duration=.4,monotonic=now,quiet=True,overflow=False))
            result=c.note(dict(midi=midi,cents=20,hz=440*2**((midi+.2-69)/12),
                               periodicity=.99,db=-25,started=now+1,monotonic=now+2))
            self.assertEqual(result,"done" if i==5 else "accepted")
        self.assertEqual(c.stage,"done")
        self.assertEqual(set(c.reference_cents),{1,2,3,4,5,6})
        self.assertTrue(all(abs(v-20)<.01 for v in c.reference_cents.values()))

    def test_wrong_string_and_stale_notes_do_not_advance(self):
        c=Calibration(-36)
        for i in range(15): c.frame(dict(db=-48,duration=.1,monotonic=i,quiet=True,overflow=False))
        c.frame(dict(db=-60,duration=.4,monotonic=20,quiet=True,overflow=False))
        p=dict(midi=45,cents=0,hz=110,periodicity=.99,db=-25,started=21,monotonic=22)
        self.assertEqual(c.note(dict(p,started=0)),"ignored")
        self.assertEqual(c.note(p),"wrong")
        self.assertEqual(c.index,0)
        self.assertEqual(c.reference_cents,{})


if __name__ == '__main__': unittest.main()
