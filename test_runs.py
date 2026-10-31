"""Deterministic boundaries for timed sets and adaptive selection."""
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from exercises import make_exercise, STRINGS
from practice import Store
from session import Session

ROOT=Path(__file__).resolve().parent

class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'build')
        self.store=Store(self.temp.name)
        self.now=100.0
        self.s=Session(self.store,clock=lambda:self.now,rng=random.Random(4))
        self.lesson=make_exercise(3,0,5)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def pick(self,midi):
        self.s.frame(dict(quiet=True,monotonic=self.now))
        return self.s.note(dict(midi=midi,cents=0,periodicity=.99,started=self.now))

    def rows(self):
        return self.store.connection.execute('SELECT outcome,seconds,attempt_count,shown FROM attempts ORDER BY id').fetchall()

    def test_third_attempt_can_succeed_and_saves_actual_elapsed(self):
        self.s.start(self.lesson)
        self.now+=2
        self.assertEqual(self.pick(50),'retry')
        self.assertEqual(self.s.note(dict(midi=50,cents=0,periodicity=.99,started=self.now)),'ignored')
        self.now+=3
        self.assertEqual(self.pick(51),'retry')
        self.now+=4
        self.assertEqual(self.pick(48),'correct')
        self.assertEqual(self.rows(),[('assisted',9.0,3,1)])
        self.now+=20
        self.assertIsNone(self.s.tick())
        self.assertEqual(self.s.countdown,11)
        self.assertEqual(len(self.rows()),1)

    def test_attempt_limit_and_timeout_are_distinct_and_do_not_double_record(self):
        self.s.start(self.lesson,attempt_limit=2)
        self.now+=1
        self.assertEqual(self.pick(50),'retry')
        self.now+=1
        self.assertEqual(self.pick(50),'exhausted')
        self.assertEqual(self.rows()[0],('exhausted',2.0,2,1))
        self.s.next()
        self.now+=20
        self.assertEqual(self.pick(48),'timeout')
        self.assertEqual(self.rows()[1],('timeout',20.0,0,1))
        self.assertIsNone(self.s.tick())
        self.assertEqual(self.pick(48),'ignored')

    def test_correct_just_before_deadline_is_accepted(self):
        self.s.start(self.lesson)
        self.now+=19.999
        self.assertEqual(self.pick(48),'correct')
        self.assertAlmostEqual(self.rows()[0][1],19.999)

    def test_quit_during_completed_card_gap_marks_only_unseen_remainder(self):
        self.s.start(self.lesson)
        self.now+=2
        self.pick(48)
        self.now+=1
        self.s.quit()
        self.s.quit()
        self.assertEqual(len(self.rows()),12)
        self.assertEqual(self.rows()[0],('independent',2.0,1,1))
        self.assertTrue(all(r==('skipped',0.0,0,0) for r in self.rows()[1:]))
        self.assertEqual(self.store.connection.execute('SELECT outcome,elapsed FROM runs').fetchone(),('quit',3.0))
        self.assertFalse(self.s.active)

    def test_quit_during_card_keeps_attempts_and_elapsed(self):
        self.s.start(self.lesson)
        self.now+=4
        self.pick(50)
        self.now+=2
        self.s.quit()
        self.assertEqual(self.rows()[0],('skipped',6.0,1,1))
        self.assertEqual(len(self.rows()),12)

    def test_set_stops_at_twelve_and_new_set_resets_counts(self):
        self.s.start(self.lesson)
        for i in range(12):
            self.now+=1
            self.assertEqual(self.pick(48),'correct')
            if i<11:
                self.now+=3
                self.s.next()
        self.assertFalse(self.s.active)
        self.assertEqual(self.s.remaining,0)
        self.assertFalse(self.s.next())
        self.assertEqual(len(self.rows()),12)
        self.assertEqual(self.store.connection.execute('SELECT outcome FROM runs').fetchone()[0],'complete')
        self.s.start(self.lesson)
        self.assertEqual(self.s.completed,0)
        self.assertEqual(self.s.attempts,0)
        self.assertEqual(self.s.remaining,12)

    def test_adaptation_rewards_faster_answers_and_retries_and_ignores_unseen(self):
        cards=make_exercise(1,0,5).cards
        fast,slow,retry,failed,unseen=cards[:5]
        for card,outcome,secs,attempts,shown in [(fast,'independent',2,1,1),(slow,'independent',18,1,1),
                (retry,'assisted',18,3,1),(failed,'timeout',20,0,1),(unseen,'skipped',0,0,0)]:
            self.store.record(card,outcome,secs,0,False,[],None,attempts,shown,20,3)
        weights=self.store.difficulty()
        self.assertLess(weights[fast.key],weights[slow.key])
        self.assertLess(weights[slow.key],weights[retry.key])
        self.assertLess(weights[retry.key],weights[failed.key])
        self.assertNotIn(unseen.key,weights)
        # Real sampler must favor the weak note while still revisiting the strong one.
        from lessons import Lesson
        pool=Lesson('qa','QA','',(fast,failed))
        counts={fast.key:0,failed.key:0}
        for _ in range(250):
            self.s.start(pool,size=1)
            counts[self.s.card.key]+=1
            # Remove this unplayed QA run without affecting the adaptive evidence.
            self.s.shown=False
            self.s.quit()
        self.assertGreater(counts[failed.key],counts[fast.key]*2)
        self.assertGreater(counts[fast.key],0)

    def test_four_modes_keep_identity_and_correct_frets(self):
        all_cards=make_exercise().cards
        self.assertEqual(len(all_cards),72)
        for mode,count in [(0,72),(1,12),(2,6),(3,1)]:
            cards=make_exercise(mode,2,5).cards
            self.assertEqual(len(cards),count)
            for c in cards:
                self.assertIn(c.key,{a.key for a in all_cards})
                self.assertTrue(1<=c.midi-STRINGS[c.string][0]<=12)
                if mode in (1,3):self.assertEqual(c.string,5)
                if mode in (2,3):self.assertEqual(c.midi%12,2)

    def test_existing_database_is_migrated_without_touching_records(self):
        self.store.close()
        legacy=Path(self.temp.name)/'legacy'
        legacy.mkdir()
        with sqlite3.connect(legacy/'progress.sqlite3') as db:
            db.execute('CREATE TABLE attempts(id INTEGER PRIMARY KEY, utc TEXT, skill TEXT, label TEXT, outcome TEXT, seconds REAL, misses INTEGER, hinted INTEGER, heard TEXT)')
            db.execute("INSERT INTO attempts VALUES(1,'saved-date','saved-skill','Saved card','independent',7,0,0,'[48]')")
        db.close()
        self.store=Store(legacy)
        original=self.store.connection.execute('SELECT utc,skill,label,outcome,seconds,misses,hinted,heard FROM attempts').fetchall()
        self.store.close()
        self.store=Store(legacy)
        self.assertEqual(self.store.connection.execute('SELECT utc,skill,label,outcome,seconds,misses,hinted,heard FROM attempts').fetchall(),original)
        self.assertIsNone(self.store.connection.execute('SELECT attempt_count FROM attempts').fetchone()[0])

if __name__=='__main__':unittest.main()
