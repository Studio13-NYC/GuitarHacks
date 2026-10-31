# Windows Home screen — October 25, 2026

The normal Windows launch now opens Home after the splash. Three large cards lead to Note flash cards, Find everywhere, and Chord Painter. Connection settings stays below the cards. Home is reachable from section setup, audio practice/results, and Chord Painter.

## Verified behavior

- The existing 44 Python regression tests passed (`build/home-regression.log`). Four additional Qt widget tests in `test_home.py` passed. The nine existing Node tests also passed.
- Real Qt widgets cover startup, section selection without opening audio, preservation of flash-card settings including older settings without per-section keys, ending calibration without scoring, ending an active audio run once, and cancellation of pending transitions.
- At 680 × 640 the cards stack with vertical scrolling and no horizontal overflow; at 1100 × 820 they form three columns.
- In the actual Windows source UI, Home opened Note flash cards and Chord Painter. A live test Painter round returned to Home and reopened on Question 1 of 10 with its remaining time retained and an explicit Resume button. QA data was isolated in `build/home-native-qa`.
- In the packaged executable, normal launch opened Home; Find everywhere opened with its mode selected; Home returned to the chooser; Tab followed by Space opened Chord Painter with its new Home button. QA data was isolated in `build/home-exe-qa`. No startup errors appeared in its app log.

## Commands and artifacts

```powershell
Set-Location 'D:\Studio13\Lab\Music\GuitarHacks'
uv run --group build python -m unittest test_home -v
uv run --frozen python -m unittest discover -v
node --test test_painter.cjs
.\build.ps1 -OutputDirectory build\home-release-candidate
```

Candidate: `D:\Studio13\Lab\Music\GuitarHacks\build\home-release-candidate\GuitarHacks.exe`

Installed: `D:\Studio13\Lab\Music\GuitarHacks\FretboardFiend\release\GuitarHacks.exe`

SHA-256: `0A448014CF7508BCDE60048B8B6691776D057E4C25D3016A17B4CC1587A84CC4`

Previous executable: `backups/20261025-200213-before-home/GuitarHacks.exe`. All four existing data files had identical SHA-256 hashes before and after replacement, before relaunch. Evidence: `build/home-install.json` and the backup's `data-before.json`. The first copy attempt encountered a temporary file lock during shutdown; the retry succeeded after the process exited. The installed app was relaunched normally and its Home screen was verified in the actual Windows UI.

## Scope

This is the Windows chooser. The hosted Chord Painter site and its Android/offline version are unchanged. `--painter` remains available for intentional direct launches. A Painter round survives returning Home during the same app session; closing the app still discards an unfinished round. Audio practice ends when returning Home and stores unfinished cards as skipped. This update did not re-test real-guitar pitch accuracy.
