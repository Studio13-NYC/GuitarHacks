# Chord detection options — October 30, 2026

## Recommendation

Keep the guided, muted-between-strings capture for fingering. Tune and validate it with the user's clean guitar signal before adding another model. If simultaneous strum tracking is needed, evaluate the already-installed Jam Origin through the existing Windows MIDI Services route. NeuralNote/MuScriptor can be reused as an after-recording cross-check, not assumed suitable for immediate feedback. Basic Pitch is a lightweight local comparison candidate, not a demonstrated accuracy upgrade.

This is research, not a comparative benchmark result. The separate guided chord-listening update was subsequently installed after explicit restart approval on October 30. No detector settings, audio devices or models were changed for this research.

## Verified local state

- `monitor.py::estimate_pitch` is a YIN-style, single-pitch estimator covering 70–850 Hz. `audio.py::PitchTracker` adds level/onset, quiet-gap, pitch-stability and confidence gates. Reconfiguring those can improve individual-string capture; it does not produce multiple simultaneous fundamentals.
- The new `chord_listening.py` uses known string order and accepts frets 0–14. Strum is only an onset cue. Muted plucks are classified using transient duration, lack of detected periodic pitch and spectral flatness; this is heuristic, not a trained guitar-mute model.
- `NeuralNote/models/muscriptor-large-f16.gguf` exists (2,739,142,176 bytes). `NeuralNote/cli/main.cpp` loads it per process, then transcribes the whole provided signal. `--instruments` conditions inference; the current MIDIfier already selects guitar groups for known guitar stems. This is not merely a post-export filter.
- The checked-in muscriptor.cpp API processes 16 kHz mono audio in 5-second chunks. Its callback reports completed notes by chunks, not live per-pick events. It explicitly warns that transcription blocks for seconds to minutes.
- Prior local verification in `NeuralNote/verification/RESULTS.md` records 17.8 seconds to transcribe a 15-second full-mix fixture on RTX 3080, plus model load. This is an October 28 logged result, not a new timing run or a benchmark of isolated guitar chords.
- The Jam executable is present. Its latest inspected local standalone log is dated October 28 and identifies version 3.0.75. Earlier startup/audio/licensing problems in `JAM-MIDI-PLAN.md` have not been retested here. Some deployment descriptions in that old plan are historical; it is not the current installed-build inventory.

## Reuse and reconfiguration

1. Guided detector: measure actual background and quiet-string levels; calibrate tuning per string; constrain candidate pitch to the prompted string's playable range; check octave/harmonic ambiguity instead of accepting a lower-confidence result. Benchmark short notes and B/high E explicitly. A secondary spectral check would be new algorithm work, not a settings-only change.
2. Muted plucks: evaluate examples of dead-string attacks, quiet fretted notes, palm-muted pitched notes and handling noise. Tune only from labeled examples. Silence must remain pending; a pitched palm-muted note must remain a note. Keep correction available.
3. NeuralNote: reuse guitar-conditioned inference on a recorded strum/pass. A persistent model instance would remove repeated load overhead; smaller models could be compared for speed, but neither change promises accuracy. Do not assume the Large model's poor full-song output predicts its isolated-guitar result.
4. Jam: configure the standard tracker for polyphony and actual tuning; verify clean input gain and gate using its own documentation. Connect tracked notes through the existing dedicated GuitarHacks MIDI loopback. MIDI Services improves transport/availability/timestamps; it does not estimate pitches. Do not apply musical scale/chord correction in a grading path, because that could hide wrong notes.

## Current upstream findings

- Jam's standard tracker supports monophonic and polyphonic conversion without a special pickup. Its docs specify tuning/input-gain/gate controls. Hex per-string tracking requires a hex pickup: https://jam.live/modules/modules/#midi-guitar-3
- The official changelog still lists Windows 3.0.75 (October 12, 2026): https://jam.live/downloads/changelog/
- JAM API docs require 3.0.80+. The WebSocket page describes localhost port 8080 and notes including pitch/string/bend, but calls the API immature. Do not infer availability on 3.0.75 or guaranteed string identity from the schema: https://jam.live/developers/ and https://jam.live/developers/websocket/
- NeuralNote v2 uses MuScriptor and runs inference locally. Code is Apache-2.0; MuScriptor weights are CC BY-NC 4.0. Its live recording interface is not proof of live pitch tracking: https://github.com/DamRsn/NeuralNote
- Spotify Basic Pitch is local, polyphonic, supports ONNX on Windows, and works best with one instrument at a time. Its model uses approximately two-second audio windows; faster-than-real-time throughput is not zero-lookahead latency. Candidate for short recorded-strum verification: https://github.com/spotify/basic-pitch and https://github.com/spotify/basic-pitch/blob/main/basic_pitch/constants.py

## Acceptance before choosing an engine

Use identical clean DI takes with known chords and string-by-string ground truth. Include open/barre/seventh chords, quiet B/high E, repeated pitches on different strings, wrong notes, dead plucks and palm-muted pitched notes. Measure missing/extra notes, octave errors, false-muted classifications, false passes and end-to-end delay. Keep string/fret assignment grounded in the guided pass: ordinary mixed pickup audio does not uniquely establish fingering. No comparative accuracy claim is justified until those recordings are evaluated.
