# GuitarHacks

## Source repository

This repository contains the Windows app, local Chord Painter, StemSlicer and NeuralNote integration code, tests, build scripts, lessons, and app assets. It excludes installed executables, local environments, model weights, soundfonts, recordings, exported stems/MIDI, logs, and saved practice data. The independently managed `sites/chord-painter` and `NeuralNote/source` checkouts are not part of this repository; see their module setup guides. Clone/build setup still requires these local dependencies where applicable.

## Stem separation subproject

[StemSlicer](StemSlicer/README.md) contains the local Demucs environment,
stem-separation script, MVSep outputs, and Wasteland practice backing tracks.
Its working directory is `D:\Studio13\Lab\Music\GuitarHacks\StemSlicer`.

A Windows guitar practice app. Open `D:\Studio13\Lab\Music\GuitarHacks\FretboardFiend\release\GuitarHacks.exe`. The short splash leads to **Home**, with four section cards: **Note flash cards**, **Fretboard Explorer**, **Chord Painter**, and **StemSlicer**. Practice works without a separate Python installation or account; StemSlicer uses its installed local Python environment and models.

Choose **Chord Painter** from Home. Paint a six-string chord box, see note names and intervals, identify the chord, or play either timed guessing game. It starts with a C major E shape at fret 8. Results stay local. See [CHORD-PAINTER.md](CHORD-PAINTER.md) for controls, scoring, build commands and the offline Android home-screen version. The two audio sections open their setup screens before listening starts. **Connection settings** is available on Home. **Home** returns from section setup and results; **End run · Home** stops an audio run and saves unfinished cards as skipped. Chord Painter pauses when you return Home and retains the round for your return during the same app session.

The mint guitar-pick icon is embedded in the executable and shown on the window/taskbar. While the app is open, right-click its taskbar icon and choose **Pin to taskbar**. Windows receives an explicit `Studio13.GuitarHacks` identity, display name, embedded icon location and relaunch command pointing to the executable, preserving any launch arguments. Pinning remains your choice. Keep the executable at its current path after pinning; if you move it, unpin the old shortcut and pin the app from its new location.

## Record with Jam (candidate)

The separate candidate at `build\jam-windows-midi-candidate\GuitarHacks.exe` adds local MIDI capture through the installed Windows MIDI Services SDK. It saves MIDI and original timestamped data for Guitar Pro import. The regular release has not been replaced. Jam's blank startup window and live guitar input remain unresolved; generated notes have passed the packaged recording and Guitar Pro score/tab checks. See [current setup and verification](JAM-MIDI-PLAN.md) for exact steps, prerequisites and limitations.

## A practice run

Choose Note flash cards from Home, or Fretboard Explorer to look up a note/chord. A note result offers Practice this note to enter Find Everywhere. The Flash cards setup card offers four modes. In flash-card modes the app names the target note and string; “any” means that the app varies that part of the prompt.

| Mode | Select |
| --- | --- |
| Any note, any string | Nothing |
| Any note, one string | String |
| One note, any string | Note |
| One note, one string | Note and string |
| Find everywhere | Note |

Flash-card runs have 12 cards. The initial limits are **20 seconds** and **3 attempts** per card. Time can be set from 5 to 120 seconds, attempts from 1 to 20. Limits, mode, note and string are saved as soon as they change and become the defaults next time. Find everywhere uses a stopwatch and unlimited retries instead; it preserves your flash-card limits.

Press Start. First mute the guitar for a short background measurement, then play low E, A, D, G, B and high E open when requested. Setup shows the note and `open (fret 0)` and does not count toward the 12 cards or run clock. There is no setup timeout. A wrong open string stays on the same setup step.

During practice:

- The note sits above the string. Find the note on frets 1–12. A target at the octave above the open string explicitly says `octave up`.
- The countdown is upper left; attempts used / allowed are upper right. A fresh mute of at least 0.3 seconds and a stable picked note are needed for each counted attempt.
- A wrong detected note flashes red for 0.6 seconds. Try again while time and attempts remain. The clock does not reset.
- At three displayed seconds remaining, the timer and note turn orange. A red retry flash briefly takes priority; a correct answer takes priority and glows green.
- A correct answer freezes the countdown. Timeout or exhausting attempts ends the card in red. The result holds for one second, then `*` appears for two seconds before the next card.
- Only the `*` screen shows `X/12 Left` and **Total** elapsed run time. Audio in either transition is ignored, and the detector requires a fresh mute for the next card.
- The gentle success ping can be disabled in Connection. It uses the Windows default playback output.
- After card 12, Set complete shows the run statistics. Again returns to setup; Home returns to the section chooser. Quit closes the app. F11 toggles full screen; Escape leaves full screen.

Quit, including closing the window, saves the current unfinished card and all remaining planned cards as skipped. Cards never shown have zero elapsed time, zero attempts and `shown=0`; they are excluded from difficulty estimates. Quitting during calibration saves no practice answers because the run has not started. Input failure ends the current run and returns to setup.

## Connection and accuracy

Connection selects the shared input for every lesson. For the Model 12 board main mix use `M12 In 11/12 - Main Mix`, Main mix left, guitar panned center. Saved inputs are preserved; an unavailable saved input is not silently replaced. Keep other pitched sources out of the mix.

Capture uses shared WASAPI with COM initialized on its worker thread. The app changes no drivers, audio services, routing or other apps. The original missing worker COM initialization was fixed and has a regression test.

Input requires a quiet interval, a note above the volume threshold, and roughly half a second of stable pitch. Minimum note volume defaults to -36 dBFS. Setup raises it when needed above the measured background and uses open-string levels and pitch references. Answers allow **±25 cents from the measured reference**. Setup accepts modest detuning within 80 cents of standard tuning; alternate tuning is not supported.

Only reliable in-tolerance notes count as attempts. Unclear pitch, clipping, overflow, out-of-tolerance tuning and exact-card octave-only differences do not consume attempts. The countdown continues, so unresolved input can still produce a timeout. Octave differences can be harmonics. The app detects pitch, not the physical string or finger, and cannot separate guitar from a loud voice or another instrument. Use clean single notes, E2–F♯5. The detector's 70–850 Hz analysis range accommodates fret 14 on the high E string and modest detuning.

## Fretboard Explorer and Find Everywhere

From Home, open **Fretboard Explorer**. Choose Note or Chord, enter a name, and select **Show me**. See notes, intervals and all matching positions through fret 12, 14 or 24. Select a dot for string, fret, octave and frequency. Lookup is unscored and requires no audio connection. Chords use the same 15 types as Chord Painter; the map shows available chord tones rather than a full fingering. To practice a note, choose **Practice this note · Find Everywhere**.

Select a note and find every occurrence from open strings through fret 14, in any order. Each pitch has a quota equal to the number of physical positions that produce it. The stopwatch starts after calibration; the race ends when all quotas are filled. There are no forced gaps between successful answers. Mute briefly and pick again for each attempt.

The large note sits above a fretboard. Green dots show credited positions; a white ring identifies the latest green dot. Plain red dots show estimated wrong-note positions, and the upper-right Misses counter counts reliable wrong notes, including repeated mistakes at the same position. Dots contain no labels. A wrong pitch outside the displayed fretboard still counts as a miss but has no placeable dot. A target pitch whose quota is already filled briefly shows “Pitch already filled” and does not count as another miss.

Positions are estimates, not string recognition. For matching pitches, the app credits the first remaining matching position in low-E-to-high-E string order. For a wrong note it prefers the last credited string and nearby fret when possible; otherwise it uses the lowest possible fret. Playing the same physical position again can fill another equal-pitch position. The display makes this assignment visible for a live trial; it cannot prove that all physical locations were played. String-specific statistics are deliberately unavailable for this game. Calibration uses the median open-string tuning reference because the played string is unknown.

## Finished-set statistics

The completion screen shows total elapsed time, answered and missed targets, red wrong-note attempts, first-try answers, total attempts, average response time, and the fastest fully answered comparable run. Flash-card reports also show the slowest requested string by mean response time and the string with the most unanswered cards. Ties are shown together. Missed cards include timeout, attempt-limit failure and skipped cards; their individual counts appear below. Red attempts count wrong detected notes, not timeout flashes. Average response includes all shown targets, including failures; unseen skipped targets are excluded.

Best total includes the current run and earlier fully answered completed runs with the same target pool, card count and limits. Retries are allowed; a faster failed or quit run cannot become the best. Find everywhere compares the same note and fret range. Prior runs without the new comparison metadata remain untouched and are not used for personal bests. A dash means no qualifying run yet. Historical detailed statistics remain in SQLite; the UI displays the just-finished set.

## Scoring and adaptive practice

`data\progress.sqlite3` beside the executable stores settings, runs and attempts. Existing rows are preserved by an additive schema migration. Each new shown card records elapsed seconds, detected attempt count, wrong-note count, outcome, chosen limits, and run ID. Outcomes include independent, assisted, exhausted, timeout and skipped. Unseen skipped cards are explicitly distinguished. Total run time includes gaps between cards, ends on the final answer/timeout or Quit, and excludes calibration and the final completion display.

The four modes share the same identity for each note/string combination. Before a run, 12 cards are sampled using up to eight recent shown outcomes per combination. Weight increases with timeouts, exhausted attempts, shown skips, retries, and elapsed time relative to the selected limit. Recent evidence weighs more. New combinations retain exploratory weight, and the last two selected cards are avoided when the pool permits. This is weighted review, not a calendar-based spaced-repetition algorithm. Fixed one-note/one-string mode necessarily repeats its single target.

Earlier lesson history remains in the database. The four-mode note pool uses `fretboard-v2` keys, so its adaptive evidence begins with these runs; older plug-ins retain their own identities. Find everywhere uses separate `everywhere-v1` identities and visits every location instead of adaptive sampling. Raw guitar audio is not recorded.

## Lesson plug-ins

The setup lesson dropdown offers the four-mode fretboard practice plus the existing 557 JSON cards for natural notes, all notes, anywhere notes, triads and sevenths. Plug-in lessons use the same calibration, 12-card limits, timers, capture, grading and storage. Connection → Open lesson folder opens the directory; closing Connection reloads it. See `LESSONS.md` for the schema. JSON plug-ins supply single-note targets, not executable code or simultaneous-chord grading. Hint text is retained in the schema but the minimal practice screen does not reveal hints.

## StemSlicer

Open **StemSlicer** from Home. Choose an audio file and edit the song title if
needed. Each table row defines one output stem: check any combination of
vocals, drums, bass, piano, other instruments, lead guitar, and rhythm guitar.
**+ Add stem** adds a row; **×** removes it. Instruments may appear in multiple
rows (for example, lead alone and lead + rhythm). Each row previews its file
name. Every row must contain at least one instrument before **Create stems**
is enabled. The table and saved-file list fit their content and grow with it,
then scroll when screen space is exhausted.

The default output is 320 kbps MP3; choose 24-bit WAV for Reason, or both.
Files go directly into `StemSlicer/separated/<song title>`, for example
`Letters From The Wasteland/letters-from-the-wasteland-L-R.mp3`. Codes are
V (vocals), D (drums), B (bass), P (piano), O (other), L (lead), R (rhythm).
Existing names get numeric suffixes; previous files are never replaced.
The guitar split is skipped if no row includes either guitar part.

The status explicitly says **NOT STARTED**, **PROCESSING**, **COMPLETE**,
**FAILED**, or **CANCELLED**. Completion shows the saved stem/file count and
an **Open completed stems** button. Saved songs list actual output filenames.
Older exports remain available in their previous folders. Processing logs,
plans, and float intermediates are in `StemSlicer/processing`.
You can return Home while a job runs; closing requires finishing or cancelling
it first. Each stem mix is verified before the batch is published. A shared
gain keeps the batch below clipping. Overlapping stems are alternative mixes:
playing them together doubles instruments they share.

Requires the local `StemSlicer` subproject, its Python environment and model
files, FFmpeg/ffprobe, and CUDA. Currently accepts stereo 44.1 kHz MP3/WAV/FLAC
without resampling. Other formats report a failure in the processing log.
The packaged app locates StemSlicer by walking upward from its executable;
keep it within the GuitarHacks project tree. It is not a self-contained portable
separator. CLI entry: `uv run --frozen python app.py --stems`.

## Development and verification

```powershell
Set-Location 'D:\Studio13\Lab\Music\GuitarHacks'
uv run --frozen python app.py
uv run --frozen python -m unittest discover -v
uv run --frozen python app.py --painter --data-dir build\painter-preview
.\build.ps1
```

The Chord Painter preview uses isolated data and opens no audio input. Close the window to exit. Older diagnostic scripts remain under `FretboardFiend\tools`; their source-import paths predate the folder move, so the commands above are the supported source entry points.

Close GuitarHacks before replacing the installed executable. The default build backs up the prior executable under `backups`, then writes `FretboardFiend\release\GuitarHacks.exe`. To build while the app is open, use `.\build.ps1 -OutputDirectory build\release-candidate` and install the tested candidate after closing it. Dependency scanning uses the project runtime and Windows folders to avoid incompatible third-party DLLs in PATH. The personal executable is unsigned and is not an installer.

The editable icon is `FretboardFiend\assets\guitarhacks.svg`. `FretboardFiend\tools\build_icon.py` renders nine ICO sizes from 16 to 256 pixels; `build.ps1` runs it and embeds the icon plus `FretboardFiend\assets\windows-version.txt`. Taskbar relaunch metadata uses the Windows window property store described in [Microsoft's RelaunchCommand documentation](https://learn.microsoft.com/en-us/windows/win32/properties/props-system-appusermodel-relaunchcommand).

CLI options `--data-dir <path>` and `--lesson-dir <path>` isolate data or select a lesson directory. Back up and move `data` and `lessons` together with the executable.

October 14, 2026: 42 tests cover generated audio through the actual widgets, six-string calibration, gates, tuning tolerance, deadline boundaries, third-attempt success, timeout versus attempt exhaustion, full 12-card completion, Quit during cards and gaps, database migration, saved settings, weighted selection, report totals, comparable best times, every open–14 position, free-order quotas, red/green dots and the results screen. Generated audio proves application behavior, not real-guitar accuracy or inferred finger position; Find everywhere is ready for the learner's live trial.

## Home screen

The Windows app opens at Home after its short splash. The four cards open Note flash cards, Fretboard Explorer, Chord Painter, and StemSlicer. Each card describes its module; the Connection settings button below them opens the existing input settings. At narrower window sizes the cards stack vertically and Home scrolls. Keyboard users can Tab through the cards and press Space to open one.

Flash-card note/string choices, lesson, timer, and attempt limit are preserved when visiting Find everywhere. Returning Home from an audio exercise stops capture. Returning Home from Chord Painter pauses its timer without clearing its in-memory round; Resume is explicit when you return. Closing the app still discards an unfinished Painter round. `--painter` continues to open that section directly for an intentional shortcut.

The hosted Android/offline web app now opens **ChordLab**, with **Chord Painter** and **Listen & Play** alongside one another. Listen & Play contains the four note flash-card modes and Find everywhere, using the browser microphone. See [the browser module guide](sites/chord-painter/CHORDLAB.md) for calibration, permissions, data, tests and known differences. The Windows app and its input routing remain separate; practice history does not sync between devices.

## Consistent practice screens and one window

Flash cards, Find everywhere, calibration, and results use Chord Painter's dark panels, mint accents, large type, and lower-left controls. At narrower widths the panels stack and scroll. The live note and string stay visible together at the default window size. Connection settings opens as a page inside the same window, with Back, Save, and Cancel. Audio input failures and recoverable practice errors appear inline on the setup page.

All sections are pages in one main window. Chord Painter is prepared before the window appears, preserving the Windows handle and taskbar entry when switching sections. Reopening the executable for the same data folder focuses the existing window without changing its section or active round. This uses a local socket and a process-aware lock; no network service or account is involved. Closing the app releases the lock. Explicit `--data-dir` profiles remain independent for isolated testing. PyInstaller and Qt WebEngine may use helper processes; these do not create additional practice windows.

See `UNIFIED-UI-QA.md` for the October 25 UI and executable verification.
