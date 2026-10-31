# Flashcard detection help — October 30, 2026

The setup selection screen and open-string calibration have a **Report detection
problem** button. The default issue is **Note not detected**; the current open
string is preselected. Live note name, frequency in Hz, and cents flat/sharp are shown during
calibration and practice, including clear pitches too quiet to register as answers.
Observing a pitch below the gate does not score or advance a card.
During silence the last clear reading remains for 2.5 seconds, explicitly labelled
**Last heard**. A fresh clear pitch replaces it immediately; moving to the next
setup/card target clears it. Rejected notes also populate this readout.
When calibration turns the target red, its instruction panel retains the heard
note/frequency and expected note until setup advances, including through silence.

The guided check measures two seconds of muted background and six seconds of
the selected open string. It can adjust the detection gate within -75 to -15
dBFS when a stable target is at least 12 dB above the measured background. It
can shorten the stable-note duration from 0.5 to 0.3 seconds only after measuring
at least 0.3 seconds of steady target pitch. Pitch confidence and tuning limits
are unchanged. It does not change hardware gain, drivers, devices or channels.

An adjustment is provisional until two fresh muted-then-plucked target notes
pass the normal detector. Only then are gate/hold settings persisted. Calibration
resumes on the same string and preserves earlier references. Failed retests,
timeouts and cancellation restore the prior capture settings. Clipping,
interruption, insufficient signal/noise separation or wrong pitch get specific
guidance instead of an unverified automatic adjustment. Diagnostic notes do not
create practice attempts or scores.

Each incident is a UTC-stamped JSONL file under the current app data directory:
`FretboardFiend/release/data/diagnostics/note-detection-*.jsonl` for the installed
app. **Open incident log** opens that record. It includes the selected issue,
string MIDI note, input/channel, recent level/pitch observations, baseline
measurements, diagnosis, settings before/after, retest notes and final outcome.
No raw audio is saved. If a log cannot be created, automatic changes are blocked.

Validation from `D:\Studio13\Lab\Music\GuitarHacks`:

```powershell
.venv\Scripts\python.exe -m unittest discover -q
& .\build.ps1 -OutputDirectory build\detection-help-release
```

- 95 tests passed, including quiet B observations without scoring, measured
  sensitivity adjustment, shorter stable hold, two-pluck verification, wrong-note
  and noisy/clipped input rejection, rollback, failure logging and retained setup
  progress, and an E replacing the previous B immediately. Full suite log:
  `build/detection-help-tests.log`.
- Native UI fixture: `build/detection-help-qa/preview.py`. It deliberately generates
  a -43 dBFS B3 approximately 12 cents flat against -66 dBFS background. It is not
  a recording of Nick's guitar.
- The native UI showed B3/12 cents flat/too quiet; the check adjusted -36 to -48
  dBFS, verified two fresh plucks, saved the incident, and resumed past B to high E.
  Evidence: `build/detection-help-qa/data/diagnostics/`.
- Source backups: `backups/detection-help-20261030`.
- Candidate executable: `build/detection-help-release/GuitarHacks.exe`, SHA-256
  `1d3b8f7d58fb8fbcfdf638d2fa6a9dc24d1ddd4ab7cb957daa042da4ec5293ab`.
- Final packaged build opened successfully with isolated settings copied from
  the configured channel-5 input. No generated audio is included in the app;
  only the separate `build/detection-help-qa/preview.py` fixture produces it.

Known limitation: the original physical B-string failure is not diagnosed by the
older app log; that log only confirms the channel-5 input opened. The new check
still needs to be run with the user's actual guitar. Periodicity is a detector
quality measure, not a probability, and one pitch cannot identify which physical
string was played. Input routing and tuning remain user-verifiable.

Installed verification (2026-10-30): release/GuitarHacks.exe matches the candidate SHA-256 above. Both approved old windows were closed; one installed app was reopened. Native UI navigation reached Note flash cards, confirmed the Report detection problem button, and retained M12 In 5/6 - Guitar-DI (USBAudio2-ACX). Left on Flashcards setup for the user's real-guitar check.
