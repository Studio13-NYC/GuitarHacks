"""Free-order pitch quotas for every occurrence of a note, open through fret 14.

A single mixed signal cannot identify strings. Equal pitches therefore share a
quota; repeated plucks can satisfy it. We deliberately leave string stats unknown.
"""
from dataclasses import replace
import json
import statistics
from session import Session
from exercises import STRINGS


class EverywhereSession(Session):
    def start(self, lesson, now=None, reference_cents=None, **limits):
        if self.active:
            raise RuntimeError('End the current run before starting another')
        if not lesson.cards:
            raise ValueError('A run needs locations')
        self.lesson = lesson
        self.cards = list(lesson.cards)
        self.unfound = list(self.cards)
        self.found = []
        self.mistakes = []
        self.misses = 0
        self.completed = self.attempts = self.total_attempts = 0
        self.reference_cents = reference_cents or {}
        self.run_started = self.clock() if now is None else now
        self.run_finished = None
        self.seconds_limit = self.attempt_limit = 0
        comparison = json.dumps(['everywhere-v1',sorted(c.key for c in self.cards)])
        self.run_id = self.store.start_run(lesson.title,0,0,len(self.cards),comparison)
        self.active = True
        self._begin_location(now)

    def _begin_location(self, now=None):
        self.card = self.unfound[0]
        reference = statistics.median(self.reference_cents.values()) if self.reference_cents else 0
        self.judge.begin(self.card,accept_octaves=True,reference_cents=reference)
        self.attempts = 0
        self.begin_card(now)

    def tick(self):
        return None  # This game is a race against elapsed time, with unlimited retries.

    def note(self, pitch):
        if not self.active or pitch.get('started',0) < self.started:
            return 'ignored'
        result = self.judge.note(pitch)
        if result == 'correct':
            midi = self.judge.heard[-1]
            card = next((c for c in self.unfound if c.midi == midi),None)
            if card is None:
                self.judge.done = False
                self.judge.heard.pop()
                return 'duplicate'  # That pitch's quota is already filled (or outside 0–14).
            self.attempts += 1
            self.total_attempts += 1
            self._save(card,'assisted' if self.judge.misses else 'independent',self.clock()-self.started,True)
            self.unfound.remove(card)
            self.found.append(card)
            self.completed += 1
            if self.unfound:
                self._begin_location()
            else:
                self._finish('complete')
            return 'correct'
        if result == 'retry':
            self.attempts += 1
            self.total_attempts += 1
            self.misses += 1
            midi = self.judge.heard[-1]
            positions = [(string,midi-opened) for string,(opened,_) in STRINGS.items()
                         if 0 <= midi-opened <= 14]
            if positions:
                # Prefer the last credited string and nearby fret; otherwise the lowest fret.
                last = self.found[-1] if self.found else None
                position = min(positions,key=lambda p:(p[0]!=last.string,abs(p[1]-(last.midi-STRINGS[last.string][0])),p[1])
                               if last else (False,p[1],p[0]))
                self.mistakes.append(position)
        return result

    def _save(self, card, outcome, seconds, shown):
        # Identity tracks the pitch quota, not evidence of a physical string/fret.
        anonymous = replace(card,string=None,instruction='Open–14 · pitch match')
        self.store.record(anonymous,outcome,seconds,self.judge.misses if shown else 0,
                          False,self.judge.heard if shown else [],self.run_id,
                          self.attempts if shown else 0,shown,0,0)

    def quit(self):
        if not self.active:
            return
        for index,card in enumerate(self.unfound):
            self._save(card,'skipped',max(0,self.clock()-self.started) if index==0 else 0,index==0)
            self.completed += 1
        self.unfound.clear()
        self._finish('quit')
