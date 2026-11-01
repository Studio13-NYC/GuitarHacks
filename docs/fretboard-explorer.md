# Fretboard Explorer

October 31, 2026. User requested a name-to-positions lookup within the former Find Everywhere section, plus clearing incorrect text answers throughout the games.

The Home card is now Fretboard Explorer. Its unscored reference accepts a note or chord name, shows constituent notes/intervals and their standard-tuning positions, and lets a selected dot describe its exact string, fret and sounding pitch. Open–14 remains the default; open–12 and open–24 are available. Note versus Chord is explicit so B can mean either one pitch class or B major. The existing Find Everywhere audio exercise is reached from a note result and keeps its current scoring/range.

Implementation uses `chord_painter/core.js` as the single chord definition/parser source, with an optional root spelling argument for interval labels. `explorer.html`, `explorer.js`, and `explorer.css` run unchanged in the native ExplorerView and the Azure site. Native QWebChannel supports Home and a validated note-to-practice handoff. Lookup has no capture, score storage or GPT connection. Chord Painter also links to Explorer; browser navigation opens a separate tab and pauses the active question. The older separate ChordLab Sites deployment is not changed.

The current app's only quiz text answer is Guess. Incorrect answers and timeouts clear it without altering scoring. Correct answers remain visible, empty submissions are ignored, and focus does not escape a completion dialog.

Validation: `node --test test_explorer.cjs test_painter.cjs`; `.venv\Scripts\python.exe -m unittest test_home test_painter_listening test_explorer_view`. Qt screenshots: `build/explorer-note.png`, `build/explorer-chord.png`. See CHORD-PAINTER-QA.md for installation/deployment state. No live audio accuracy claim is part of this reference feature.

## Local movable-shape update — October 31, 2026

Uncommitted local work, per user request. In Chord mode, C/A/G/E/D checkboxes choose complete movable voicings; E and A start checked. Each selected voicing gets a diagram with string labels, muted/open markers, root highlighting and a low-E-to-high-E fret sequence. The full-neck view is collapsed initially and shows the union of the checked shapes. Note lookup retains every matching position. Selections persist while switching note/chord within the open view, but are not saved across launches.

Explicit E and A patterns cover all 15 supported chord qualities. C/G/D cover major, minor, dominant 7, major 7, minor 7 and minor-major 7; D also covers sus2/sus4. Unavailable patterns are stated, not generated heuristically. Complete voicings outside the selected range or with a different slash bass are excluded and explained. C-form dominant/minor sevenths omit the fifth and label that omission. Some full C/G variants require wide stretches; diagrams specify pitches, not finger numbers.

Validation: `node --test test_explorer.cjs test_painter.cjs` (19 passed); `.venv\Scripts\python.exe -m unittest test_explorer_view` (3 passed; real Qt checkboxes, empty selection, fret-limit feedback and note/chord switching). Screenshot: `build/explorer-chord.png`. Package/install state is recorded in CHORD-PAINTER-QA.md.
