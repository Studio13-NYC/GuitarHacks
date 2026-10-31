# Unified practice UI — October 25, 2026

## Implemented behavior

- Note flash cards and Find everywhere use the same dark/mint palette, rounded workspace, bold headings, and lower-left controls as Chord Painter. Their calibration and results screens use the same page shell.
- Home selects the section. Flash-card modes stay inside Flash cards; Find everywhere has its own note selector. Existing timers, attempt limits, calibration, scoring, and history remain in the existing Python engine.
- Connection is an embedded page with Back, Save, and Cancel. It does not create a second top-level window.
- Audio input failures and recoverable practice/lesson errors appear inside the setup page rather than opening another window.
- All practice pages stay in the original `QMainWindow`. WebEngine is prepared before the window is shown. The live source check retained native window ID `41750156` across Home, Flash cards, Find everywhere, and Chord Painter.
- Reopening the same data profile activates the existing window, preserving its current section and round. An actual second source launch exited and left that same Chord Painter window present.

## Verification

`uv run --frozen --group build python -m unittest discover -v` passed **53 tests**. `node --test test_painter.cjs` passed **9 tests**. Logs are `build/unified-ui-tests.log` and `build/unified-painter-tests.log`.

Tests cover generated audio through calibration and scoring, settings/history preservation, navigation, embedded Connection Save/Cancel, local socket activation, reacquiring a released profile lock, narrow layouts, fitting the full Find everywhere heading, and keeping the live note and requested string visible together. Qt-rendered previews using isolated synthetic data are in `build/unified-ui-preview`. They are layout evidence, not learner results. The offscreen fixture loads the installed Segoe UI fonts and production theme.

The source app was also checked in the actual Windows UI using isolated data at `build/unified-native-qa`. Native window identity was compared before and after switching into Chord Painter and reopening the app. The initial packaged candidate showed the new Flash cards and embedded Connection pages, and entered calibration in the same window. Its selected Model 12 main-mix endpoint returned no audio data; the app stopped capture and returned to setup without scoring an answer. The error was then changed to an inline message and covered by a regression test. Hardware routing and device settings were not changed.

Build command:

```powershell
Set-Location 'D:\Studio13\Lab\Music\GuitarHacks'
.\build.ps1 -OutputDirectory build\unified-release-final
```

Final candidate: `D:\Studio13\Lab\Music\GuitarHacks\build\unified-release-final\GuitarHacks.exe`.

## Final executable and installation

The final packaged build retained native window ID `23531778` across Home, Find everywhere, calibration, the inline no-input message, and Chord Painter. The Find everywhere heading and Start button were visible in the default layout. Minimize followed by a repeated executable launch restored the same Painter window without changing the section; the repeated launch exited with code 0. The remaining two same-name processes were the original PyInstaller launcher and its application child. The isolated test database contained zero practice attempts.

Installed to `D:\Studio13\Lab\Music\GuitarHacks\FretboardFiend\release\GuitarHacks.exe` and relaunched. SHA-256: `609703DFE500A31B80394B94A644E5EEA6E9621719F63697A3AE55B8687A5904`. The previous executable is in `backups/20261025-202454-before-unified-install`. All four existing learner data files retained identical hashes through replacement, before relaunch; evidence is `build/unified-install.json` and that backup's `data-before.json`.

## Boundaries

One interactive window is enforced per data folder. Explicit `--data-dir` profiles remain independent so testing does not write learner data. PyInstaller and Qt WebEngine helper processes are expected; they are not extra practice windows. The local lock uses process liveness rather than an age timeout. The website/Android version is unchanged, and real-guitar pitch accuracy was not recalibrated in this UI update.

Qt documents that dynamically adding the first OpenGL widget to a shown hierarchy can recreate the native window. Preparing the embedded view before showing the application avoids that transition here, as verified by the unchanged native window ID. Reference: [Qt widget composition limitations](https://doc.qt.io/qt-6/qopenglwidget.html#limitations-and-other-considerations).
