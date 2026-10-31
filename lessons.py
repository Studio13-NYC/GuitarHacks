"""Declarative lesson plug-ins. Lessons never open devices or judge audio."""
from dataclasses import dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class Card:
    lesson_id: str
    id: str
    prompt: str
    instruction: str
    hint: str
    midi: int
    match: str = "exact"
    string: int | None = None

    @property
    def key(self):
        return f"lesson:{self.lesson_id}:{self.id}:{self.match}:{self.midi}"

    @property
    def label(self):
        return f"{self.prompt} · {self.instruction}"


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    description: str
    cards: tuple[Card, ...]


def _text(obj, key, limit):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{key}: expected text of 1–{limit} characters")
    return value.strip()


def _identifier(obj):
    value = _text(obj, "id", 80)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
        raise ValueError("id: use lowercase letters, digits, hyphens or underscores")
    return value


def read_lesson(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError("Lesson is larger than 2 MB")
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("Expected a lesson object with version 1")
    lesson_id = _identifier(doc)
    title = _text(doc, "title", 80)
    description = _text(doc, "description", 500)
    entries = doc.get("cards")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 5000:
        raise ValueError("cards: expected 1–5000 cards")
    seen, cards = set(), []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each card must be an object")
        ident = _identifier(entry)
        if ident in seen:
            raise ValueError(f"Duplicate card id: {ident}")
        seen.add(ident)
        midi, match = entry.get("midi"), entry.get("match", "exact")
        if type(midi) is not int or not 40 <= midi <= 76:
            raise ValueError(f"{ident}: midi must be an integer from 40 (E2) to 76 (E5)")
        if match not in ("exact", "pitch_class"):
            raise ValueError(f"{ident}: match must be exact or pitch_class")
        string = entry.get("string")
        if string is not None and (type(string) is not int or not 1 <= string <= 6):
            raise ValueError(f"{ident}: string must be an integer from 1 to 6")
        cards.append(Card(lesson_id, ident, _text(entry, "prompt", 80),
                          _text(entry, "instruction", 240), _text(entry, "hint", 500),
                          midi, match, string))
    return Lesson(lesson_id, title, description, tuple(cards))


def load_lessons(directory):
    """Invalid or duplicate plug-ins are reported, never silently substituted."""
    lessons, errors, seen = [], [], set()
    for path in sorted(Path(directory).glob("*.json")):
        try:
            lesson = read_lesson(path)
            if lesson.id in seen:
                raise ValueError(f"Duplicate lesson id: {lesson.id}")
            seen.add(lesson.id)
            lessons.append(lesson)
        except (ValueError, OSError, TypeError) as error:
            errors.append(f"{path.name}: {error}")
    return lessons, errors
