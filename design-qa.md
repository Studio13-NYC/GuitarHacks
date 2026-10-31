# Design QA — timed practice sets, results and Find everywhere

Date: October 14, 2026
final result: passed

Reference: selected note-above-string storyboard, `C:\Users\NickKatsivelos\.codex\generated_images\01a13ba8-fa18-72f1-8f3b-6e3aae51c799\exec-cdd9a400-68a0-45bb-8168-9bb8b105643c.png`.

Implementation: native PySide6 MainWindow at 1100 × 820 content size, using the isolated `tools/preview_ui.py` harness. This renders the actual product widgets, with generated input and temporary progress. Source board and rendered captures were opened together in the comparison tool call. Windows title bar is outside the app-owned design. Test digits differ from the illustrative reference.

## Results and Find everywhere — October 14 update

- Kept the existing note-above-string flash cards. Added a separate completion page with eight metrics, string summaries, failure breakdown and Again/Quit.
- Inspected actual native widgets at 1100 × 820 and minimum 680 × 640 content sizes. Results remain readable without clipping; fretboard labels, plain red/green dots, latest-position ring and live Misses counter remain clear at both sizes.
- Free-order screen retains the large target note, adds a stopwatch and open–14 remaining count, and places the fretboard below. The dots themselves have no labels.
- 42 tests pass. Added checks for aggregate statistics, comparable fully answered best times, all 90 physical positions across 12 note choices, repeated-pitch quotas, fresh-mute gating, preserved misses on Quit, high F♯5 detection, and generated audio through actual dots/counters/completion widgets.
- Position assignment is an explicit estimate from pitch and quota order. Physical string recognition and live-guitar accuracy are not established by these checks. Free-order reports do not invent string-specific performance.

## Findings and corrections from the earlier timed-set pass

- P2, first inspection: setup panel collapsed to a narrow natural width and radio indicators were nearly invisible. Added a 580-pixel minimum panel width and contrasting native radio indicator styling. Reopened the native preview and verified the corrected four-option setup, note/string fields and controls.
- P2, second inspection: customized numeric-button background suppressed native arrow rendering. Removed that override and applied a consistent dark Fusion palette. Reopened and verified native numeric controls; keyboard input remains available.
- Increased asterisk fitting limit after inspecting transition sizing. The transition clearly shows only the asterisk, remaining count, Total and Quit.

## Verified surfaces and behaviors

- Splash: mint asterisk and GuitarHacks wordmark, then automatic setup.
- Native selector interactions: clicked Any note, one string; only String remained. Clicked One note, any string; only Note remained. Both selectors show for One note, one string.
- Card: note above string, unlabelled countdown upper left, attempts upper right, Quit lower right. No Total or remaining counter on letter cards.
- Warning: timer and letter orange at 00:03; string remains white. Capture `build/qa/warning.png`.
- Correct: green glow on note; target and counter stay readable. Generated-input widget test verifies counted attempts and frozen countdown.
- Transition: remaining cards and Total, with countdown and attempt indicator hidden. Capture `build/qa/gap.png`.
- Automated real-widget integration exercises all six open strings, retry, success, result hold, transition, new-card mute, warning, resize, full screen, Quit and settings persistence.
- 36 tests pass, including deadline boundaries, completion at 12, adaptive weighting and legacy database migration.

## Practical limits / P3 differences

Native numeric arrows are smaller than the illustrative mockup. Native title bars and setup-only Connection/plug-in controls are retained. Letter-to-string spacing is more generous at this viewport; both remain large and clear. None blocks the requested flow. Generated input checks do not establish live-guitar accuracy with the learner's new limits. No new P0/P1/P2 issue remained after the corrected captures.
