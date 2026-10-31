"""Bounded practice runs, deadlines, attempts and adaptive selection."""
import random
import json
import statistics
import time
from practice import Judge


class Session:
    def __init__(self, store, clock=time.monotonic, rng=None):
        self.store, self.clock = store, clock
        self.rng = rng or random.Random()
        self.lesson = self.card = None
        self.judge = Judge()
        self.active = False
        self.started = 0.0
        self.completed = 0
        self.reference_cents = {}
        self.cards = []
        self.index = -1
        self.shown = False
        self.attempts = 0
        self.run_id = None
        self.run_started = None
        self.run_finished = None
        self.seconds_limit, self.attempt_limit = 20, 3
        self.result = None

    @property
    def remaining(self):
        return max(0,len(self.cards)-self.completed)

    @property
    def elapsed(self):
        if self.run_started is None:
            return 0.0
        return max(0,(self.run_finished if self.run_finished is not None else self.clock())-self.run_started)

    @property
    def countdown(self):
        if not self.shown:
            return float(self.seconds_limit)
        now = self.ended if self.judge.done else self.clock()
        return max(0,self.seconds_limit-(now-self.started))

    def start(self, lesson, now=None, reference_cents=None, seconds_limit=20, attempt_limit=3, size=12):
        if self.active:
            raise RuntimeError('End the current run before starting another')
        if not lesson.cards or seconds_limit < 1 or attempt_limit < 1 or size < 1:
            raise ValueError('A run needs cards and positive limits')
        self.lesson = lesson
        self.reference_cents = reference_cents or {}
        self.seconds_limit, self.attempt_limit = seconds_limit,attempt_limit
        self.completed, self.index = 0,-1
        self.cards = []
        weights = self.store.difficulty()
        for _ in range(size):
            recent = {c.key for c in self.cards[-2:]}
            pool = [c for c in lesson.cards if c.key not in recent] or list(lesson.cards)
            self.cards.append(self.rng.choices(pool,[weights.get(c.key,2.5) for c in pool],k=1)[0])
        self.run_started = self.clock() if now is None else now
        self.run_finished = None
        comparison = json.dumps([lesson.id,sorted(c.key for c in lesson.cards),seconds_limit,attempt_limit,size])
        self.run_id = self.store.start_run(lesson.title,seconds_limit,attempt_limit,size,comparison)
        self.active = True
        self.next(now)

    def next(self, now=None):
        if not self.active or (self.index >= 0 and not self.judge.done):
            return False
        self.index += 1
        self.card = self.cards[self.index]
        fallback = statistics.median(self.reference_cents.values()) if self.reference_cents else 0.0
        self.judge.begin(self.card,accept_octaves=self.card.match=='pitch_class',
                         reference_cents=self.reference_cents.get(self.card.string,fallback))
        self.attempts, self.shown, self.result = 0,False,None
        self.begin_card(now)
        return True

    def begin_card(self, now=None):
        self.started = self.clock() if now is None else now
        self.shown = True
        self.judge.armed = False

    def frame(self, frame):
        if self.active and frame.get('monotonic',0) >= self.started and frame.get('quiet'):
            self.judge.quiet()

    def tick(self):
        if self.active and self.shown and not self.judge.done and self.clock()-self.started >= self.seconds_limit:
            self._record('timeout',self.started+self.seconds_limit)
            return 'timeout'
        return None

    def note(self, pitch):
        if not self.active or self.judge.done or pitch.get('started',0) < self.started:
            return 'ignored'
        if self.tick():
            return 'timeout'
        result = self.judge.note(pitch)
        if result in ('correct','retry'):
            self.attempts += 1
        if result == 'correct':
            self._record('assisted' if self.attempts>1 or self.judge.hinted else 'independent')
        elif result == 'retry' and self.attempts >= self.attempt_limit:
            self._record('exhausted')
            return 'exhausted'
        return result

    def hint(self):
        if self.active and not self.judge.done:
            self.judge.hinted = True
        return self.card.hint if self.card else ''

    def skip(self):
        if not self.active or self.judge.done:
            return False
        self._record('skipped')
        return True

    def quit(self):
        if not self.active:
            return
        if not self.judge.done:
            self._record('skipped',finish_run=False)
        for card in self.cards[self.index+1:]:
            self.store.record(card,'skipped',0,0,False,[],self.run_id,0,False,self.seconds_limit,self.attempt_limit)
            self.completed += 1
        self._finish('quit')

    def pause(self):
        self.quit()

    def _record(self, outcome, now=None, finish_run=True):
        self.ended = self.clock() if now is None else now
        self.judge.done = True
        self.result = outcome
        self.store.record(self.card,outcome,min(self.seconds_limit,max(0,self.ended-self.started)),
            self.judge.misses,self.judge.hinted,self.judge.heard,self.run_id,self.attempts,
            self.shown,self.seconds_limit,self.attempt_limit)
        self.completed += 1
        if finish_run and self.remaining == 0:
            self._finish('complete')

    def _finish(self, outcome):
        self.active = False
        self.judge.armed = False
        self.run_finished = self.clock()
        self.store.finish_run(self.run_id,outcome,self.elapsed)
