# Guided chord listening implementation plan

> Execute with superpowers:executing-plans, using the existing workspace; it has no root Git repository. Preserve unrelated edits and back up touched files.

**Goal:** Let Chord Painter accept a strum followed by individually picked strings, including automatically recognized muted plucks, as an alternative to clicking.

**Architecture:** Existing Capture supplies observations to a separate guided-pass state machine. PainterBridge controls its lifetime and publishes state to the existing diagram. No target-chord information enters audio detection. Existing chord grading remains unchanged.

**Tech stack:** Python, NumPy, sounddevice, PySide6 WebEngine/WebChannel, existing JavaScript chord UI.

**Spec:** User-approved guided low-E-to-high-E pass with brief mutes; user amendment requires played muted strings to advance automatically. Initial strum begins capture but is not a polyphonic transcription. Silence never means a muted string. Short nonperiodic transients can be classified conservatively as muted; uncertain sounds wait for retry. Manual muted and previous-string controls remain available. No explanatory lesson feature. Settings and practice history stay local.

## Constraints and review focus

- Use configured input/channel, with no implicit device fallback or persistent gate change.
- Detect voiced note before considering muted classification; reject clipping, dropped frames, sustained noise and unresolved periodic transients. Synthetic verification cannot prove real-guitar accuracy.
- Require a fresh quiet gap for each string; never carry an old note into the next string. Skip counts as an explicit user choice only.
- Pause grading timer while listening; preserve guesses and normal submission after review. Respect hidden note/interval choices in feedback.
- Stop microphone on navigation, mode switch, cancellation, completion, error and shutdown; retain thread until finished. Do not start audio alongside an existing flashcard capture.

## Tasks

- [x] Back up source; add signal flatness evidence to Capture frames without changing flashcard acceptance.
- [x] Add `chord_listening.py`: pure `ChordPass.frame/note/retry/muted` state transitions and QObject capture controller. Explicit unresolved/accepted/muted states; map known string and measured MIDI pitch to fret.
- [x] Test waveform-driven notes/muted plucks, silence, weak tones, noise, clipping, stale frames, repeats, full sequence and rollback using unittest.
- [x] Add bridge slots/signals and lifecycle wiring in `painter_view.py` / `app.py`; test controller with injected capture signals and real Qt WebEngine interaction.
- [x] Add Click/Listen controls, guided status, highlighted string, retry/muted actions in `chord_painter`; keep existing settings, history and label controls. Desktop audio only, explicit browser availability message.
- [x] Run affected tests plus existing Python/JS suites. Inspect actual rendered surface. Build isolated executable; document limitations and actual results.
- [x] Install when app is closed or after explicit restart approval; verify packaged surface and preserved saved data.

## Execution ledger

- Installed after explicit restart approval; executable SHA-256 `3635F0C5CFDB6AA9D169CAF14720D702FC84563EA9E48078AC52B8DDCC3A5E3D`. Four saved-data files were unchanged during replacement. Reopened installed Chord Painter and selected Paint the chord / Listen; verified guided instructions and capture controls without starting a scored round or microphone capture.

- Source backups created under `backups/chord-listening-20261030`; root is not a Git repository, so no commit/revert operations used.
- Guided state machine, audio evidence, bridge and UI implemented. Waveform tests cover pitch, muted transients, silence, noise, clipping, stale events and retries. Embedded Qt tests cover timer/scoring, labels, auto muted highlight, navigation and input failure.
- Ruling: support frets 0–14, not the initial 0–12 implementation assumption, because existing root-12 chord presets include fret-14 notes. Added waveform regression.
- Review fix: reuse the already-observed quiet gap at strum-release and auto-muted transitions; do not require the player to provide it twice. Regression failed before fix and passes after it.
- Muted classification remains heuristic and real-guitar validation is outstanding. No confidence percentage or polyphonic transcription claim is made.
- Independent review also found stale capture summaries when a new/reset question clears the diagram. Added failing UI regression and cleared review state on new question/mode/manual edits; affected tests pass.
