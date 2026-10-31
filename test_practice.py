import random
from pathlib import Path
import tempfile
import unittest
import numpy as np

from monitor import estimate_pitch
from music import QUALITIES, voicing
from practice import Store, Judge, candidates, choose_exercise


class MusicTests(unittest.TestCase):
    def test_all_voicings_match_actual_strings(self):
        for root in range(12):
            for key,q in QUALITIES.items():
                tones=voicing(root,key)
                self.assertEqual(len({t.midi%12 for t in tones}),len(q[2]))
                self.assertEqual({t.midi%12 for t in tones},{(root+s)%12 for s in q[2]})
                self.assertEqual(next(t for t in tones if t.degree=="1").string,5)
                for t in tones:
                    self.assertEqual(t.midi,{6:40,5:45,4:50,3:55}[t.string]+t.fret)

    def test_spelling(self):
        self.assertEqual([t.note for t in voicing(0,"dim7")],["G♭","C","E♭","B♭♭"])
        self.assertEqual([t.note for t in voicing(2,"major")],["A","D","F♯"])
        self.assertEqual([t.note for t in voicing(6,"major")],["D♭","G♭","B♭"])

    def test_all_seventh_chords_require_four_tones(self):
        pool=candidates(0,"major","Seventh chords","Build a chord")
        self.assertEqual(len(pool),24)
        for key in {e.quality for e in pool}:
            self.assertEqual(len([e for e in pool if e.quality==key]),4)


class JudgeTests(unittest.TestCase):
    def setUp(self):
        self.j=Judge(); self.target=voicing(0,"major")[1]
        self.good={"midi":48,"periodicity":.99,"cents":1,"clipped":False}

    def test_tolerance_is_plus_or_minus_25_cents(self):
        for cents in [-25,25]:
            self.j.begin(self.target); self.j.quiet()
            self.assertEqual(self.j.note(dict(self.good,cents=cents)),"correct")
        for cents in [-25.1,25.1]:
            self.j.begin(self.target); self.j.quiet()
            self.assertEqual(self.j.note(dict(self.good,cents=cents)),"tuning")
            self.assertEqual(self.j.misses,0)

    def test_free_play_and_held_note_are_not_answers(self):
        self.assertEqual(self.j.note(self.good),"ignored")
        self.j.begin(self.target)
        self.assertEqual(self.j.note(self.good),"ignored")
        self.j.quiet()
        self.assertEqual(self.j.note(self.good),"correct")
        self.j.quiet()
        self.assertEqual(self.j.note(self.good),"ignored")
        self.j.begin(self.target)
        self.assertEqual(self.j.note(self.good),"ignored")

    def test_noise_clipping_and_octaves_do_not_count_as_mistakes(self):
        self.j.begin(self.target); self.j.quiet()
        for field,val in [("periodicity",.8),("clipped",True)]:
            self.assertEqual(self.j.note(dict(self.good,**{field:val})),"unclear")
        self.assertEqual(self.j.note(dict(self.good,midi=60)),"octave")
        self.assertEqual(self.j.misses,0)

    def test_retry_is_counted_once_per_separate_note(self):
        self.j.begin(self.target); self.j.quiet()
        wrong=dict(self.good,midi=50)
        self.assertEqual(self.j.note(wrong),"retry")
        self.assertEqual(self.j.note(wrong),"ignored")
        self.j.quiet()
        self.assertEqual(self.j.note(self.good),"correct")
        self.assertEqual(self.j.misses,1)


class PersistenceTests(unittest.TestCase):
    def test_restart_preserves_helped_and_independent_answers(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/"build") as path:
            store=Store(path)
            pool=candidates(0,"major","Current chord","Intervals")
            store.record(pool[0],"assisted",11,1,True,[50,48])
            store.record(pool[1],"independent",3,0,False,[52])
            store.set_settings({"speech":True,"channel":0}); store.close()
            store=Store(path)
            self.assertEqual(store.total(),2)
            self.assertTrue(store.settings()["speech"])
            rows=store.summary(); self.assertEqual(rows[0][0],pool[0].key)
            self.assertEqual(rows[0][4],1)
            # Assisted skill wins more draws than an independently answered one.
            rng=random.Random(3)
            drawn=[choose_exercise(pool[:2],rows,[],rng).key for _ in range(1000)]
            self.assertGreater(drawn.count(pool[0].key),drawn.count(pool[1].key))
            self.assertNotEqual(choose_exercise(pool,rows,[pool[0].key]).key,pool[0].key)
            store.close()


class PitchTests(unittest.TestCase):
    def test_single_notes_detuning_and_harmonics(self):
        rng=np.random.default_rng(13); sr=48000; n=np.arange(4096)/sr
        for midi in [40,43,45,48,50,51,52,54,55,59,60,64,69]:
            for cents in [-20,0,20]:
                f=440*2**((midi-69+cents/100)/12)
                for harmonics in [(1,.4,.2),(.25,1,.4)]:
                    x=sum(a*np.sin(2*np.pi*f*(i+1)*n+.15*i) for i,a in enumerate(harmonics))
                    x=.12*x*np.exp(-n*2)+rng.normal(0,.0005,len(n))
                    result=estimate_pitch(x,sr)
                    self.assertIsNotNone(result)
                    self.assertEqual(result["midi"],midi)
                    self.assertLess(abs(result["cents"]-cents),4)

    def test_silence_and_noise(self):
        self.assertIsNone(estimate_pitch(np.zeros(4096),48000))
        self.assertIsNone(estimate_pitch(np.random.default_rng(8).normal(0,.1,4096),48000))


if __name__=="__main__":
    (Path(__file__).parent/"build").mkdir(exist_ok=True)
    unittest.main()
