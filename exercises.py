"""The four note-finding modes share one note/string progress identity."""
from lessons import Card, Lesson

NOTES = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")
STRINGS = {6:(40,"low E"),5:(45,"A"),4:(50,"D"),3:(55,"G"),2:(59,"B"),1:(64,"high E")}
MODES = ("Any note, any string", "Any note, one string", "One note, any string", "One note, one string", "Find everywhere")


def make_exercise(mode=0, note=0, string=5):
    if mode == 4:
        cards = tuple(Card("everywhere-v1",f"string-{number}-fret-{fret}",NOTES[note],
                           "Open–14 · any order",f"{label} string · fret {fret}",opened+fret,"exact",number)
                      for number,(opened,label) in STRINGS.items() for fret in range(15)
                      if (opened+fret)%12 == note)
        return Lesson("everywhere-v1",f"Find everywhere · {NOTES[note]}","Open strings through fret 14",cards)
    cards = []
    for pc,name in enumerate(NOTES):
        if mode in (2,3) and pc != note:
            continue
        for number,(opened,label) in STRINGS.items():
            if mode in (1,3) and number != string:
                continue
            fret = (pc-opened)%12 or 12
            location = f"{label} string" + (" · octave up" if fret == 12 else "")
            cards.append(Card("fretboard-v2",f"pc-{pc}-string-{number}",name,location,
                              f"{label} string · fret {fret}",opened+fret,"exact",number))
    return Lesson("fretboard-v2",MODES[mode],"Frets 1–12 · standard tuning",tuple(cards))
