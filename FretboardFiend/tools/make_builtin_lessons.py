"""Regenerate shipped lesson data from standard tuning and existing voicings."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from music import QUALITIES, chord_name, voicing

STRINGS = {6: (40, "low E"), 5: (45, "A"), 4: (50, "D"),
           3: (55, "G"), 2: (59, "B"), 1: (64, "high E")}
STRING_GUIDES = {6:"the thickest string (low E / string 6)", 5:"the A string (string 5)",
                 4:"the D string (string 4)",3:"the G string (string 3)",
                 2:"the B string (string 2)",1:"the thinnest string (high E / string 1)"}
NATURALS = [("C", 0), ("D", 2), ("E", 4), ("F", 5), ("G", 7), ("A", 9), ("B", 11)]
ALL_NOTES = [("C", 0), ("C♯", 1), ("D♭", 1), ("D", 2), ("D♯", 3), ("E♭", 3),
             ("E", 4), ("F", 5), ("F♯", 6), ("G♭", 6), ("G", 7), ("G♯", 8),
             ("A♭", 8), ("A", 9), ("A♯", 10), ("B♭", 10), ("B", 11)]


def note_cards(notes):
    for n, (name, pc) in enumerate(notes):
        for string, (open_midi, string_name) in STRINGS.items():
            fret = (pc-open_midi) % 12 or 12
            midi = open_midi+fret
            register = f"One octave above open {string_name}." if fret == 12 else "Find it between frets 1–12."
            yield dict(id=f"note-{n}-string-{string}", prompt=f"Play {name}\non the {string_name} string",
                       instruction=f"String {string}. {register}\nDo not use the open string.",
                       hint=f"Press fret {fret} on {STRING_GUIDES[string]}. That is {name}{midi//12-1}.",
                       midi=midi, match="exact", string=string)


def chord_cards(sevenths):
    for root in range(12):
        for quality, definition in QUALITIES.items():
            if (len(definition[2]) == 4) != sevenths:
                continue
            for tone in voicing(root, quality):
                register = ("One octave above its lowest position on this string (frets 12–23)."
                            if tone.fret >= 12 else "Use its lowest position on this string (open to fret 11).")
                yield dict(id=f"root-{root}-{quality}-string-{tone.string}",
                           prompt=f"Play the {tone.interval}\nof {chord_name(root, quality)}",
                           instruction=f"Use {STRING_GUIDES[tone.string]}.\n{register}",
                           hint=f"The {tone.interval} is {tone.note}{tone.midi//12-1}. Press fret {tone.fret} on the {tone.string_name} string with your {tone.finger} finger.",
                           midi=tone.midi, match="exact", string=tone.string)


def write(folder, filename, ident, title, description, cards):
    doc = dict(version=1, id=ident, title=title, description=description, cards=list(cards))
    (folder/filename).write_text(json.dumps(doc, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main():
    folder = ROOT/"lessons"
    folder.mkdir(exist_ok=True)
    write(folder, "01-natural-notes.json", "natural-notes-v1", "Natural notes · all strings",
          "Find and play a natural note on one specified string. Use frets 1–12; hints show its location.", note_cards(NATURALS))
    write(folder, "02-all-notes.json", "all-notes-v1", "All notes · all strings",
          "Find notes including sharps and flats. Frets 1–12, standard tuning.", note_cards(ALL_NOTES))
    anywhere = []
    for n, (name, pc) in enumerate(ALL_NOTES):
        fret = (pc-40) % 12 or 12
        anywhere.append(dict(id=f"note-{n}", prompt=f"Play {name}", instruction="Choose any string. Open strings are allowed.\nUse a note from open low E up to high E at fret 12.",
                             hint=f"One place: low E string, fret {fret}", midi=40+fret, match="pitch_class"))
    write(folder, "03-anywhere.json", "anywhere-v1", "Any string · all notes",
          "Play the named note anywhere from open low E to high E at fret 12.", anywhere)
    write(folder, "04-triad-tones.json", "triad-tones-v1", "Triad tones · all roots",
          "Find a root, third or fifth in major, minor and diminished triads.", chord_cards(False))
    write(folder, "05-seventh-tones.json", "seventh-tones-v1", "Seventh tones · all roots",
          "Find a chord tone in a seventh chord. Pick one note, not a strum.", chord_cards(True))


if __name__ == "__main__":
    main()
