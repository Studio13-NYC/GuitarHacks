# Chord Painter

Source: `D:\Studio13\Lab\Music\GuitarHacks\chord_painter`.
Windows entry: **Chord Painter** on the Home screen, or launch with `--painter`.

## Desktop layout

The main view puts the full fretboard on the left and the chord, current listening instruction, and primary action on the right. **Settings** opens Play/Click, chord family, roots, round length, timing, independent dot labels, round controls, and saved results. **Input & calibration** opens input/voice details, Recalibrate, Stop play, Not detecting a note, Previous string, Mark muted, and the optional extra note check. These panels no longer sit above the fretboard. Spoken commands are ignored while either panel is open.

Calibration hides the quiz prompt and existing painted dots without discarding them, and highlights the string being checked. It returns to the exercise when ready. The native desktop layout is checked at a 1100 by 780 content area; this local bundle is desktop-oriented, with no new phone layout. The separately published ChordLab site is unchanged.

## Using the canvas

**Explorer** opens the unscored Fretboard Explorer reference. Choose Note or Chord, enter a name (for example B, F# or B♭maj7), and choose Show me. The reference lists notes and intervals, highlights all matching positions through fret 12, 14 or 24, and shows string/fret/octave/frequency when a dot is selected. Root tones are gold. It uses Chord Painter's 15 chord types, preserves sharp/flat spelling, and accepts slash bass notes. Unsupported extensions are reported rather than guessed. The map shows available tones, not a complete fingering. In Windows, a note lookup offers **Practice this note · Find Everywhere**; the timed exercise still covers open–14. Lookup does not open audio, save scores, or call GPT. On the Azure site, Explorer opens in a separate tab so the paused game is preserved; the native listening exercise remains Windows-only in this bundle.

Standard tuning, low E at the left, high e at the right. The initial C major chord is a movable E shape at fret 8: `8 10 10 9 8 8`. Root on low E chooses the anchor fret (0–12); changing it transposes every painted dot. Each string has at most one note. Click a fret to place or replace its dot; click the same dot to mute the string. The controls above the nut toggle open/muted. Gold dots are roots. **Show on dots: Note names / Intervals** independently controls the two labels, including open notes and accessible fret labels. Both start on; turn both off for plain dots. Choices persist locally and can change during a round without resetting the question, guesses or timer. Root color, tuning/string names, and the target chord remain visible. Arrow keys move between fret buttons; Enter or Space paints.

The box normally shows two frets above the root toward the headstock: C at fret 8 starts with frets 6–10. **Lower / Higher** scroll the five-fret view without moving the root, changing any notes, or consuming a guess. Notes outside the view are listed below the box and remain in the chord. Arrow Up/Down also scroll when focus reaches an edge. Open strings stay available above the grid; the lowest numbered fret is 1. Loading a preset, transposing, or starting/resetting a question frames the chord again; wider presets such as sus2 fit all their dots. These controls work in Instant Display, Guess, and Paint the chord.

Instant Display names the exact pitch collection and shows common alternatives. The library has major, minor, diminished, dominant seventh, major seventh, minor seventh, half-diminished seventh, diminished seventh, minor-major seventh, sus2, sus4, augmented, major/minor sixth, and power chords. Unrecognized collections are labeled explicitly. Inversions show slash bass notes. The E-root diminished presets are variations, not claims that a six-string barre is the easiest fingering for every chord.

## Games

### Guided guitar input (Windows)

**Play guitar is the Windows default** when Chord Painter opens. Calibration starts when the Painter page becomes visible, not while Home preloads it. Choose **Settings → Answer by → Click** for mouse input; this explicit choice stays selected across practice-mode changes for the current session. The browser-only bundle uses Click because it has no native guitar bridge. Play immediately opens the saved Home/Connection guitar input and starts calibration: mute for the background check, then play each open string from low E to high E, with a brief mute between strings. Detected note, frequency and tuning stay visible throughout calibration. Input level and threshold are available in Input & calibration. The session learns a trigger level and per-string tuning reference from actual input; it does not overwrite Flashcards settings. **Not detecting a note** logs an incident and restarts calibration. **Check another note** optionally verifies a chosen string and fret.

After all six strings pass, the same input stays open. Click or say **Go** to begin the quiz. Each question starts capture automatically: mute briefly, strum once, mute, then pick the highlighted strings in order. The strum is only a cue; the individual picks place the dots. Standard tuning shapes at frets 0–14 are supported. A short unpitched muted pluck may advance automatically; uncertain sounds wait, with **Mark muted** and **Previous string** available. Detection never uses the target chord to force the measured answer.

Review the captured dots, then click **Next — check chord** or say **Next**. A wrong answer starts another guided pass; after a completed question, **Next** advances. **Retry**, by button or speech, keeps the same question and starts a separately scored try. It remains available after the guess limit is exhausted. Earlier wrong results stay in history; a later correct try adds a correct result. Each retry resets the timer and guess allowance. A duplicate Retry before new input is ignored. **Play chord again** is available only in Instant Display. **Quit** by button or speech stops guitar and voice input and discards the unfinished round, preserving earlier saved results. Switching away stops input and pauses a question; Resume recalibrates. The quiz timer pauses during capture and resumes for review. Hidden note/interval choices apply during the quiz; calibration deliberately shows note/tuning feedback.

Voice commands use the installed Windows SAPI recognizer and the default speech microphone (currently **M12 In 1/2 - Mic**), separate from Guitar-DI. A short voice status stays in the exercise; the selected endpoint and full readiness/failure details are in Input & calibration. Accepted final Go/Next/Retry/Quit recognitions are debounced; rejected speech does nothing. If the recognizer is unavailable, the buttons continue working. Recognition is local, with no additional model download or cloud service. Real voice and guitar accuracy still require physical testing; muted-pluck classification is heuristic, not a trained model. No raw audio is saved. Phase, signal summaries, accepted/rejected notes, calibration references and troubleshooting incidents are logged to the normal app log.

The hosted browser ChordLab has not been updated with this feature. Its separate single-note Listen & Play module remains as documented below.

- **Guess:** Switching from Instant Display preserves your painted chord for the first question, if it is recognized. Start round hides its name; type your guess and Submit. Next question generates an E-shape diagram from your chosen family and roots. Changing setup also selects generated questions. Equivalent spellings and other valid names for exactly the same notes count. Slash notation, if entered, must use the actual bass. A slash is optional.
- **Paint the chord:** Start round supplies a chord name and empty grid at the relevant root fret. Paint it and Submit. Every distinct chord tone must be present, with no extra pitches. Any complete voicing counts; it need not reproduce the sample E shape or bass inversion.
- **Questions per round:** Set 1–100 questions in Settings before starting. The default is 10. The progress bar shows the question number and this round's correct/failed totals. Each question has its own guess limit (default 3) and each guess gets its own timer (default 20 seconds). A wrong answer or timeout consumes one guess and restarts the timer. Success or exhausting guesses ends that question; Next question advances. After the final question, the round ends and New round becomes available.
- **Retry:** Available in Guess and Paint the chord after a wrong answer, or when abandoning an entered answer. The previous try is marked failed without counting an already graded miss twice. Retry preserves the chord, voicing target and question number, and shows Try 2, Try 3, etc. There is no retry limit. Results retain both failures and successes, including after the final question was saved. A retry of that final question appends only its new result when completed; existing saved results are never counted twice. Correctly completed questions cannot be retried.
- **Reset round:** Immediately discards all answers, misses, and scores in the unfinished round and starts question 1 with the same settings, unused guesses, and a fresh timer. It works while paused or between questions. It also clears a partially painted answer. Earlier completed rounds stay saved. Reset after a round is already complete starts a new round; it does not delete that saved round.
- Show answer fails the current question and loads the example shape. An answer at the deadline is a timeout. Pausing, hiding the page or switching windows preserves remaining time. Resume is explicit. Settings lock until the round ends. Switching modes, closing, or reloading discards an unfinished round. In Windows, **Home** pauses the current round and returns to the section chooser; reopening Chord Painter keeps it paused until Resume.
- Only a fully completed round adds its unsaved try results and misses to saved history. Retrying the final question after completion preserves its previously saved result even if the new try is abandoned. Later target selection gives more weight to chords with saved misses or failures within the selected family/roots. The totals in Settings are saved results; the bar above the chord box shows the current round. Scores measure these screen exercises, not guitar playing, finger comfort, or audio accuracy.

Windows progress: `<data directory>\chord-painter.json`, saved atomically and separate from the existing SQLite flash-card history. `--data-dir` isolates both for QA. This JSON contains settings, results, comments, preferences and career history. The latest 300 detailed try results are retained, with lifetime totals and compact round summaries retained beyond that. View results shows the latest 30.

The Azure/browser bundle uses a user-selected JSON file in desktop Chrome or Edge. Each visit asks **Open practice file** or **Create new file**, then saves changes automatically. Open the same file to continue; no progress copy is kept in localStorage, IndexedDB or cloud storage. Earlier localStorage results can be explicitly migrated with **Save earlier browser results to JSON**; the old cache is removed only after a valid file is selected or saved. Settings shows save status and **Open a different practice file**. The native Windows app continues using its existing file without a browser picker.

To remove Chord Painter practice, close the app and delete its JSON file. Reopen and create a new file to start fresh. If it is deleted, moved or edited while open, saving stops with an explanation instead of silently recreating or overwriting it. Other tools' files (Flashcards SQLite, recordings, stems, MIDI exports) are separate and are not removed. Existing manual backups and operating-system/cloud-folder backups are outside this app's control. Pick a nonsynced local folder if you want the practice file only on that computer.

Wrong typed guesses and expired guesses clear the entry box automatically. If another guess is available, typing focus stays in the box; blank submission does not consume a guess. Scores and earlier failures are retained.

## Round review and career chart

After a completed Guess or Paint round, the review identifies chord types with recent failures and missed guesses. Each type has a Balanced / Test more / Test less preference and comment field; there is also a general notes box. Analyze comments with GPT sends these notes plus practice summaries (never guitar audio) to OpenAI. The model's bounded suggestions influence the next plan; it cannot change scores, remove types from the selected family, or override the question count. The prepared mix is shown before Start planned round. There is no need for Blob Storage; practice history stays in the local JSON file, with no cross-device sync. Deleting that file does not retract previously submitted GPT requests.

The Career chart separates Guess and Paint. Chord types run vertically; completed rounds run left to right by start time. Green means all clean successes, yellow means at least half the tries succeeded with misses/retries, red means fewer than half succeeded, and gray means untested. Each cell also displays correct / total tries and opens detailed counts and timer/guess settings. Retries update the same round column and retain previous failures. Explicit round IDs and compact summaries are retained across the career; detailed attempt history remains capped at 300. Earlier saved results without round IDs stay in lifetime totals but cannot be honestly assigned to old round columns.

The native app reads the ignored root `.env.local`; configuration is documented in `docs/openai-key-setup.md`. The Azure browser uses `/api/practice-review`, with GitHub sign-in and an allowed-user list. The API key belongs in SWA backend settings. Failed or cancelled reviews leave local analysis and scores intact. Free-text comments are only interpreted after Analyze comments; local planning uses measured results and the structured preferences.

## Run and validate

From `D:\Studio13\Lab\Music\GuitarHacks`:

```powershell
uv sync --group build
uv run --group build python app.py --painter
node --test test_painter.cjs
uv run --group build python -m unittest discover -p 'test_*.py'
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Existing resources are in `FretboardFiend\assets`, `FretboardFiend\lessons`, and `FretboardFiend\tools`; source modules remain at the project root. The build writes `FretboardFiend\release\GuitarHacks.exe` and backs up the previous executable. To build a candidate while that executable is open, run `powershell -ExecutionPolicy Bypass -File .\build.ps1 -OutputDirectory build\release-candidate`; this leaves the installed executable and its data alone. PySide6 WebEngine supplies the embedded view; the JS game is shared across desktop and mobile. Qt 6.12 ships WebEngine as a separate dependency.

## Android / subway use

Live public app: **https://guitarhacks-chord-painter.nickknyc.chatgpt.site**. It now opens **ChordLab**, with **Chord Painter** and **Listen & Play** modules. Listen & Play provides microphone-based single-note flash cards and Find everywhere; see [the browser module guide](sites/chord-painter/CHORDLAB.md). Originally published October 25, 2026 through Sites; changed to public at the owner's request October 27. No sign-in is required.

On Android, open that address in Chrome while online. Wait for **Ready for offline practice**, then tap **Install app** if offered, or use the browser's install menu. Launch the new home-screen icon once online. Switch to airplane mode, reopen it, and try a round before relying on it on the subway. Physical Android offline behavior still needs this check.

For an existing icon that reports `ERR_FAILED`, open the main address in the same browser used to install the icon while online, refresh once, then close and reopen the home-screen app. Version 7 repairs the old `/index.html` launch without clearing practice data. Chrome and Edge have separate app caches, so refreshing in Chrome does not update an icon installed through Edge. The failure and recovery were verified in desktop Chrome; the repaired Android icon awaits user confirmation.

The `chord_painter` folder is a self-contained progressive web app: responsive layout, manifest, local icons, service worker, and no external fonts, APIs or audio dependencies. Cached practice runs offline, including games and saved results. The existing credentialed manifest link also works with the current public hosting. See [MDN's manifest requirements](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest) and [Chrome's installation instructions](https://support.google.com/chrome/answer/9658361?co=GENIE.Platform%3DAndroid).

Hosted checkout: `sites\chord-painter`, identity in `.openai\hosting.json`, static assets in `dist`. It now owns the ChordLab shell and browser listener. **Do not overwrite its entire `dist` with the desktop `chord_painter` folder.** Apply shared Painter changes deliberately, retaining the web navigation hook, manifest and worker. Bump the service-worker cache version when assets change and use the Sites source workflow to publish the existing project. No learner data is uploaded. Windows and phone results remain separate. See `sites\chord-painter\QA.md` for browser checks and `CHORD-PAINTER-QA.md` for the Windows executable's release status.

Local preview (desktop only):

```powershell
uv run python -m http.server 8765 --bind 127.0.0.1 --directory chord_painter
```

Open `http://127.0.0.1:8765/` for local development. A phone cannot use the computer's localhost address; use the live HTTPS address above. Browser data clearing removes phone progress; Windows progress stays in its own JSON file.
