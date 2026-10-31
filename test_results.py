"""Run reports, comparable bests, free-order quotas, and actual UI/audio wiring."""
import random
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from exercises import make_exercise, STRINGS
from practice import Store
from session import Session
from everywhere import EverywhereSession
from test_flashcards import QApplication, MainWindow, SyntheticCapture, QTest, Qt, np, wave

ROOT=Path(__file__).resolve().parent


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'build')
        self.store=Store(self.temp.name)
        self.now=100.

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def pick(self,s,midi,**extra):
        s.frame(dict(quiet=True,monotonic=self.now))
        return s.note(dict(midi=midi,cents=0,periodicity=.99,started=self.now,**extra))

    def finish(self,note=0,seconds=2,limit=20):
        s=Session(self.store,clock=lambda:self.now,rng=random.Random(3))
        s.start(make_exercise(3,note,5),seconds_limit=limit,size=2)
        for index in range(2):
            self.now+=seconds
            self.pick(s,s.card.midi)
            if index==0:
                self.now+=3
                s.next()
        return s

    def test_best_excludes_failures_quits_other_targets_and_limits(self):
        first=self.finish(seconds=2)
        self.assertEqual(self.store.run_stats(first.run_id)['best'],7)
        self.finish(note=2,seconds=.1)
        self.finish(seconds=.1,limit=30)
        failed=Session(self.store,clock=lambda:self.now)
        failed.start(make_exercise(3,0,5),size=2)
        failed.skip()
        failed.next()
        failed.skip()
        quit_run=Session(self.store,clock=lambda:self.now)
        quit_run.start(make_exercise(3,0,5),size=2)
        quit_run.quit()
        slower=self.finish(seconds=5)
        stats=self.store.run_stats(slower.run_id)
        self.assertEqual((stats['best'],stats['best_runs']),(7,2))
        self.assertEqual((stats['solved'],stats['first_try'],stats['missed'],stats['red']),(2,2,0,0))

    def test_report_distinguishes_wrong_notes_timeouts_exhaustion_and_unseen(self):
        s=Session(self.store,clock=lambda:self.now)
        s.start(make_exercise(3,0,5),size=4,attempt_limit=2)
        self.now+=1
        self.pick(s,50)
        self.now+=2
        self.pick(s,48)
        s.next()
        self.now+=20
        s.tick()
        s.next()
        self.now+=1
        self.pick(s,50)
        self.now+=1
        self.pick(s,50)
        s.quit()
        stats=self.store.run_stats(s.run_id)
        self.assertEqual((stats['solved'],stats['missed'],stats['red'],stats['attempts']),(1,3,3,4))
        self.assertEqual((stats['timed_out'],stats['exhausted'],stats['skipped']),(1,1,1))
        self.assertAlmostEqual(stats['average'],25/3)
        self.assertEqual(stats['strings'][5]['count'],3)
        self.assertEqual(stats['strings'][5]['missed'],2)
        self.assertIsNone(stats['best'])

    def test_all_twelve_notes_enumerate_exactly_frets_zero_through_fourteen(self):
        total=0
        for pc in range(12):
            cards=make_exercise(4,pc).cards
            self.assertEqual(len(cards),len({c.key for c in cards}))
            for c in cards:
                self.assertEqual(c.midi%12,pc)
                self.assertIn(c.midi-STRINGS[c.string][0],range(15))
            total+=len(cards)
        self.assertEqual(total,90)
        self.assertIn(78,[c.midi for c in make_exercise(4,6).cards])

    def test_free_order_fresh_plucks_quotas_misses_and_no_invented_string_stats(self):
        s=EverywhereSession(self.store,clock=lambda:self.now)
        s.start(make_exercise(4,0))
        self.now+=250
        self.assertIsNone(s.tick())
        self.assertEqual(self.pick(s,62),'retry')
        self.assertEqual(s.misses,1)
        self.assertEqual(len(s.mistakes),1)
        self.assertEqual(self.pick(s,48,clipped=True),'unclear')
        self.assertEqual(s.misses,1)
        quotas=Counter(c.midi for c in s.cards)
        for midi,count in sorted(quotas.items(),reverse=True):
            for _ in range(count):
                self.now+=1
                self.assertEqual(self.pick(s,midi),'correct')
                self.assertEqual(s.note(dict(midi=midi,cents=0,periodicity=.99,started=self.now)),'ignored')
            if s.active:
                self.assertEqual(self.pick(s,midi),'duplicate')
        self.assertFalse(s.active)
        self.assertEqual(s.remaining,0)
        self.assertEqual(len(s.found),len(s.cards))
        stats=self.store.run_stats(s.run_id)
        self.assertEqual(stats['red'],1)
        self.assertEqual(stats['attempts'],len(s.cards)+1)
        self.assertEqual(stats['strings'],{})
        self.assertEqual(stats['missed'],0)
        self.assertEqual(stats['best'],s.elapsed)

    def test_race_quit_saves_pending_misses_and_remaining_once(self):
        s=EverywhereSession(self.store,clock=lambda:self.now)
        s.start(make_exercise(4,4))
        self.now+=2
        self.pick(s,40)
        self.now+=3
        self.pick(s,42)
        s.quit()
        s.quit()
        stats=self.store.run_stats(s.run_id)
        self.assertEqual(stats['solved'],1)
        self.assertEqual(stats['missed'],len(s.cards)-1)
        self.assertEqual(stats['red'],1)
        self.assertEqual(stats['total'],5)
        self.assertIsNone(stats['best'])


class ResultsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_generated_audio_updates_dots_miss_counter_and_finished_screen(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            w=MainWindow(Path(folder),ROOT/'lessons',SyntheticCapture)
            try:
                w.splash_timer.stop()
                w.settings.update(input='QA generated audio',cues=False)
                w.show_setup()
                w.show()
                w.show_everywhere()
                self.assertTrue(w.note_box.isVisible())
                self.assertFalse(w.string_box.isVisible())
                self.assertFalse(w.seconds_spin.isVisible())
                w.note_combo.setCurrentIndex(6)
                w.session=EverywhereSession(w.store)
                w.session.start(w.selected_lesson())
                capture=SyntheticCapture('QA',0,-36,w)
                w.capture=capture
                capture.frame.connect(w.audio_frame)
                capture.note.connect(w.audio_note)
                capture.finished.connect(w.capture_finished)
                w.show_card()
                self.assertTrue(w.fretboard.isVisible())
                capture.play(np.zeros(4096))
                capture.play(wave(55))
                self.assertEqual(w.attempt_display.text(),'Misses\n1')
                self.assertEqual(len(w.fretboard.mistakes),1)
                for midi in [c.midi for c in reversed(w.session.cards)]:
                    capture.play(np.zeros(4096))
                    capture.play(wave(midi))
                self.assertEqual(w.session.remaining,0)
                self.assertEqual(len(w.fretboard.found),len(w.session.cards))
                self.assertEqual(w.transition,'race_done')
                w.next_timer.stop()
                w.advance_step()
                self.assertEqual(w.pages.currentWidget(),w.results_page)
                self.assertEqual(w.result_values['red'].text(),'1')
                self.assertEqual(w.result_values['missed'].text(),'0')
                self.assertIn('Not measured',w.slowest_string.text())
                self.assertIsNone(w.capture)
                w.show_setup()
                w.show_notes()
                self.assertTrue(w.seconds_spin.isVisible())
            finally:
                w.close()


if __name__=='__main__':unittest.main()
