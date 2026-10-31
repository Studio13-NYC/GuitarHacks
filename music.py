"""Standard-tuning voicings with a movable root on the A string."""
from dataclasses import dataclass

ROOTS = ("C", "D♭", "D", "E♭", "E", "F", "G♭", "G", "A♭", "A", "B♭", "B")
LETTERS = "CDEFGAB"
NATURALS = (0, 2, 4, 5, 7, 9, 11)
INTERVALS = {"1": "root", "3": "major third", "♭3": "minor third", "5": "perfect fifth",
             "♭5": "diminished fifth", "7": "major seventh", "♭7": "minor seventh", "♭♭7": "diminished seventh"}
# Name, symbol, semitones in harmonic order, intervals, frets relative to A-root fret.
QUALITIES = {
    "major": ("Major triad", "", (0,4,7), ("1","3","5"), (0,0,-1)),
    "minor": ("Minor triad", "m", (0,3,7), ("1","♭3","5"), (0,0,-2)),
    "dim": ("Diminished triad", "dim", (0,3,6), ("1","♭3","♭5"), (-1,0,-2)),
    "maj7": ("Major seventh", "maj7", (0,4,7,11), ("1","3","5","7"), (0,0,-1,1)),
    "dom7": ("Dominant seventh", "7", (0,4,7,10), ("1","3","5","♭7"), (0,0,-1,0)),
    "min7": ("Minor seventh", "m7", (0,3,7,10), ("1","♭3","5","♭7"), (0,0,-2,0)),
    "half_dim": ("Half-diminished seventh", "m7♭5", (0,3,6,10), ("1","♭3","♭5","♭7"), (-1,0,-2,0)),
    "dim7": ("Diminished seventh", "dim7", (0,3,6,9), ("1","♭3","♭5","♭♭7"), (-1,0,-2,-1)),
    "min_maj7": ("Minor-major seventh", "m(maj7)", (0,3,7,11), ("1","♭3","5","7"), (0,0,-2,1)),
}


@dataclass(frozen=True)
class Tone:
    note: str
    degree: str
    midi: int
    string: int
    fret: int
    finger: str

    @property
    def interval(self):
        return INTERVALS[self.degree]

    @property
    def string_name(self):
        return {6: "low E", 5: "A", 4: "D", 3: "G"}[self.string]

    @property
    def location(self):
        return f"{self.string_name} string · fret {self.fret} · {self.finger} finger"


def voicing(root: int, quality: str) -> list[Tone]:
    q = QUALITIES[quality]
    root_letter = LETTERS.index(ROOTS[root][0])
    notes = []
    for i, semitone in enumerate(q[2]):
        letter = (root_letter + i*2) % 7
        accidental = (root + semitone - NATURALS[letter] + 6) % 12 - 6
        notes.append(LETTERS[letter] + ("♭" * -accidental if accidental < 0 else "♯" * accidental))
    result = []
    for string_index, offset in enumerate(q[4]):
        harmonic_index = (2, 0, 1, 3)[string_index]
        fret = root + 3 + offset
        result.append(Tone(notes[harmonic_index], q[3][harmonic_index],
                           (40,45,50,55)[string_index]+fret, 6-string_index, fret,
                           ("middle","ring","index","pinky")[string_index]))
    return result


def chord_name(root, quality):
    return ROOTS[root] + QUALITIES[quality][1]


def spoken(text):
    return text.replace("♭♭", " double flat ").replace("♭", " flat ").replace("♯", " sharp ")
