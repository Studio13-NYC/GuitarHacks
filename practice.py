"""Practice selection and local results. Free play never enters this store."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sqlite3

from music import QUALITIES, Tone, chord_name, voicing


@dataclass(frozen=True)
class Exercise:
    root: int
    quality: str
    mode: str
    tone: Tone

    @property
    def key(self):
        return f"{self.root}:{self.quality}:{self.mode}:{self.tone.degree}"

    @property
    def label(self):
        return f"{chord_name(self.root, self.quality)} · {self.tone.note} · {self.tone.degree} ({self.mode})"


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.directory / "progress.sqlite3")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY, utc TEXT NOT NULL, skill TEXT NOT NULL,
            label TEXT NOT NULL, outcome TEXT NOT NULL, seconds REAL NOT NULL,
            misses INTEGER NOT NULL, hinted INTEGER NOT NULL, heard TEXT NOT NULL)""")
        self.connection.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, started TEXT NOT NULL, finished TEXT,
            lesson TEXT NOT NULL, seconds_limit INTEGER NOT NULL,
            attempt_limit INTEGER NOT NULL, size INTEGER NOT NULL, outcome TEXT, elapsed REAL)""")
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(attempts)")}
        for name, declaration in {"run_id":"INTEGER", "attempt_count":"INTEGER",
                                  "shown":"INTEGER", "seconds_limit":"INTEGER",
                                  "attempt_limit":"INTEGER", "string_number":"INTEGER"}.items():
            if name not in columns:
                self.connection.execute(f"ALTER TABLE attempts ADD COLUMN {name} {declaration}")
        run_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(runs)")}
        if 'comparison_key' not in run_columns:
            self.connection.execute('ALTER TABLE runs ADD COLUMN comparison_key TEXT')
        self.connection.commit()

    def settings(self):
        return {k: json.loads(v) for k, v in self.connection.execute("SELECT key,value FROM settings")}

    def set_settings(self, values):
        with self.connection:
            for k, v in values.items():
                self.connection.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (k,json.dumps(v)))

    def record(self, exercise, outcome, seconds, misses, hinted, heard,
               run_id=None, attempt_count=None, shown=None, seconds_limit=None, attempt_limit=None):
        with self.connection:
            self.connection.execute("INSERT INTO attempts(utc,skill,label,outcome,seconds,misses,hinted,heard,run_id,attempt_count,shown,seconds_limit,attempt_limit,string_number) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), exercise.key, exercise.label,
                 outcome, max(0,seconds), misses, int(hinted), json.dumps(heard),
                 run_id,attempt_count,shown,seconds_limit,attempt_limit,getattr(exercise,'string',None)))

    def start_run(self, lesson, seconds_limit, attempt_limit, size, comparison_key=None):
        with self.connection:
            return self.connection.execute(
                "INSERT INTO runs(started,lesson,seconds_limit,attempt_limit,size,comparison_key) VALUES(?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(),lesson,seconds_limit,attempt_limit,size,comparison_key)).lastrowid

    def run_stats(self, ident):
        """Use recorded outcomes; never infer which string was played in free order."""
        run = self.connection.execute('SELECT size,elapsed,comparison_key FROM runs WHERE id=?',(ident,)).fetchone()
        if run is None:
            raise ValueError('Unknown run')
        rows = self.connection.execute('''SELECT outcome,seconds,misses,attempt_count,shown,string_number
            FROM attempts WHERE run_id=? ORDER BY id''',(ident,)).fetchall()
        solved = [r for r in rows if r[0] in ('independent','assisted')]
        shown = [r for r in rows if r[4]]
        strings = {}
        for outcome,seconds,misses,attempts,was_shown,string in shown:
            if string is not None:
                group = strings.setdefault(string,dict(count=0,seconds=0,missed=0,red=0))
                group['count'] += 1
                group['seconds'] += seconds
                group['missed'] += outcome not in ('independent','assisted')
                group['red'] += misses
        for group in strings.values():
            group['average'] = group['seconds']/group['count']
        # Fast failures must not beat a completed set. Compare the same pool and settings.
        best = self.connection.execute('''SELECT MIN(r.elapsed),COUNT(*) FROM runs r
            WHERE r.comparison_key=? AND r.outcome='complete'
            AND (SELECT COUNT(*) FROM attempts a WHERE a.run_id=r.id)=r.size
            AND NOT EXISTS(SELECT 1 FROM attempts a WHERE a.run_id=r.id
                           AND a.outcome NOT IN ('independent','assisted'))''',(run[2],)).fetchone()
        return dict(size=run[0],total=run[1] or 0,solved=len(solved),
                    missed=sum(r[0] not in ('independent','assisted') for r in rows),
                    red=sum(r[2] for r in rows),first_try=sum(r[0]=='independent' for r in rows),
                    attempts=sum(r[3] or 0 for r in rows),
                    average=sum(r[1] for r in shown)/len(shown) if shown else None,
                    timed_out=sum(r[0]=='timeout' for r in rows),
                    exhausted=sum(r[0]=='exhausted' for r in rows),
                    skipped=sum(r[0]=='skipped' for r in rows),strings=strings,
                    best=best[0],best_runs=best[1])

    def finish_run(self, ident, outcome, elapsed):
        with self.connection:
            self.connection.execute("UPDATE runs SET finished=?,outcome=?,elapsed=? WHERE id=? AND finished IS NULL",
                (datetime.now(timezone.utc).isoformat(),outcome,max(0,elapsed),ident))

    def difficulty(self):
        """Recent shown attempts, normalized for the learner's chosen limits."""
        rows = self.connection.execute("""SELECT skill,outcome,seconds,attempt_count,seconds_limit,attempt_limit
            FROM attempts WHERE shown=1 ORDER BY id DESC""")
        scores = {}
        for key,outcome,seconds,attempts,limit,max_attempts in rows:
            history = scores.setdefault(key,[])
            if len(history) >= 8:
                continue
            failed = outcome in ("timeout","exhausted","skipped")
            effort = min(1,max(0,(attempts or 0)-1)/max(1,(max_attempts or 3)-1))
            slow = min(1,seconds/max(1,limit or 20))
            history.append(3*failed+2*effort+slow)
        return {key:1+sum(value*.8**i for i,value in enumerate(values))/
                sum(.8**i for i in range(len(values))) for key,values in scores.items()}

    def summary(self):
        return self.connection.execute("""SELECT skill, label, count(*),
            sum(CASE WHEN outcome='independent' THEN 1 ELSE 0 END),
            sum(CASE WHEN outcome='assisted' THEN 1 ELSE 0 END),
            sum(CASE WHEN outcome='skipped' THEN 1 ELSE 0 END), sum(misses), avg(seconds), max(id)
            FROM attempts GROUP BY skill ORDER BY sum(misses)+sum(hinted) DESC, max(id) DESC""").fetchall()

    def total(self):
        return self.connection.execute("SELECT count(*) FROM attempts").fetchone()[0]

    def recent(self):
        return self.connection.execute("SELECT utc,label,outcome,misses FROM attempts ORDER BY id DESC LIMIT 30").fetchall()

    def close(self):
        self.connection.close()


def candidates(root, quality, scope, mode):
    qualities = [quality] if scope == "Current chord" else [
        key for key, q in QUALITIES.items()
        if scope == "All chords" or (scope == "Triads") == (len(q[2]) == 3)]
    result = []
    for key in qualities:
        tones = voicing(root,key)
        for degree in QUALITIES[key][3]:
            result.append(Exercise(root,key,mode,next(t for t in tones if t.degree==degree)))
    return result


def choose_exercise(pool, summaries, recent, rng=random):
    stats = {r[0]:r for r in summaries}
    available = [e for e in pool if e.key not in recent[-2:]] or pool
    weights = []
    for e in available:
        s = stats.get(e.key)
        if not s:
            weights.append(2.5)
        else:
            # Difficult items recur more often; independent retrieval lowers their weight.
            tries, independent, assisted, skipped, misses, seconds = s[2:8]
            weights.append(1 + min(5,(assisted+skipped+misses)*2/max(1,tries))
                           + min(1,max(0,seconds-8)/12) + 1/(independent+1))
    return rng.choices(available,weights=weights,k=1)[0]


class Judge:
    """One prompt, no timeout penalty, no scoring while speaking or between prompts."""
    def __init__(self):
        self.target = None
        self.armed = False
        self.done = False
        self.misses = 0
        self.hinted = False
        self.heard = []
        self.accept_octaves = False
        self.reference_cents = 0.0

    def begin(self, target, accept_octaves=False, reference_cents=0.0):
        self.__init__()
        self.target = target
        self.accept_octaves = accept_octaves
        self.reference_cents = reference_cents

    def quiet(self):
        if self.target is not None and not self.done:
            self.armed = True

    def note(self, pitch):
        if not self.armed or self.done or self.target is None:
            return "ignored"
        if pitch.get("periodicity",0) < .95 or pitch.get("clipped",False):
            return "unclear"
        self.armed = False  # Require a fresh pause before another counted attempt.
        adjusted = pitch["midi"] + (pitch.get("cents",0)-self.reference_cents)/100
        midi = round(adjusted)
        if abs(100*(adjusted-midi)) > 25.000001:
            return "tuning"  # Out-of-tolerance input is not evidence of a wrong fret.
        self.heard.append(midi)
        if midi == self.target.midi or (self.accept_octaves and midi % 12 == self.target.midi % 12):
            self.done = True
            return "correct"
        if midi % 12 == self.target.midi % 12:
            return "octave"  # Could be a harmonic; never record this as a wrong note.
        self.misses += 1
        return "retry"
