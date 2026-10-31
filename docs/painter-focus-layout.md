# Chord Painter focus layout — October 31, 2026

Request: remove the dense controls and diagnostics above the guitar; make the exercise the focus.

Chosen approach: keep the existing Qt WebEngine surface and event handlers, place the diagram left and the chord/listening prompt plus main action right. Settings and input diagnostics use native HTML dialogs. Calibration uses the same diagram/instruction area, highlights the requested string, and temporarily hides unrelated chord dots without changing them. The alternate permanent sidebar would keep secondary controls on screen; a separate wizard would duplicate the existing calibration lifecycle. Neither is needed.

Main controls: mode tabs, Settings, fret navigation, quiz action, Quit, Input & calibration. Independent dot-label switches, chord/round configuration, results, reset, pause and reveal live in Settings. Input details and recovery/manual string controls live in Input & calibration. Voice commands do not act behind either modal. Existing note detection and scoring algorithms are unchanged.

Source: chord_painter/index.html, style.css, app.js; local service worker v11. Hosted sites/chord-painter remains unchanged.

Validation: actual PainterView / QWebChannel with generated waveform input, isolated temporary profiles. test_painter_listening checks complete calibration, guided pass, review, dialogs, troubleshooting, commands, normal 1100 x 780 bounds and input shutdown. Screenshots in build/painter-focus-*.png. Automated signals do not verify real guitar or voice accuracy.

Build using build.ps1 with a separate build/painter-focus-release destination, then verify the packaged UI. Ask before closing the user app; installation is not implied by a successful candidate build.

User follow-up: Windows defaults to Play, starting calibration only when Chord Painter is visible. Click remains available in Settings and is retained across mode changes within the session. Hidden Home preload does not acquire audio. Browser-only fallback remains Click.
