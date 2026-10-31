# Audio and MIDI previews - October 30, 2026

The saved-song checklist includes original audio, audio stems, and exported MIDI.
**Play checked** renders all checked items into one synchronized preview, starting
each at time zero. Pause/resume, stop, seeking, and replay use that same stream.
**Midify selected** converts checked audio only; checking MIDI does not queue it
for transcription. Changing checked files or leaving the page stops playback.
The window remains 800 logical pixels wide and grows vertically to fit controls.

MIDI preview uses TinySoundFont 0.3.7 and FluidR3Mono General MIDI sounds, locally.
It preserves tempo changes, leading silence, polyphony, programs, percussion on
channel 10, supported MIDI controllers, and pitch bend. Each MIDI has a separate
synth instance, so shared channel numbers cannot change another file's sounds.
This is a listening preview, not Reason's instrument patches or a transcription
quality improvement. Type 2 MIDI sequences are rejected; SysEx and aftertouch
are not interpreted. Mixing averages checked files to avoid summation clipping,
with a final limiter; preview gain does not alter exports. MIDI release tails
add up to one second. Long selections need preparation time before playback.

Setup from `D:\Studio13\Lab\Music\GuitarHacks`:
```powershell
uv sync --frozen
.venv\Scripts\python.exe tools\setup_preview_soundfont.py
.venv\Scripts\python.exe -m unittest discover -q
& .\build.ps1 -OutputDirectory build\playback-release
```
The setup script verifies pinned SHA-256 digests and keeps the sound-set license
beside `StemSlicer/playback/FluidR3Mono_GM.sf3`. Previews require this project
folder and FFmpeg. Temporary mixes live in `StemSlicer/preview-cache` and are
removed when replaced or on normal shutdown; original audio/MIDI is never edited.

Validation:
- 87 tests passed, including actual synthesis of overlapping notes with tempo
  changes, mixing three MIDI files and audio, drum output, exact stem alignment,
  fixed gain after a shorter stem ends, cancellation, and fitted window geometry.
- Native source UI played an audio stem plus two MIDI files simultaneously;
  pause, seek from 6 to 16 seconds, resume, completion, replay, and stop verified.
- Native output device: `M12 Out 1/2 (USBAudio2-ACX)` (Windows default).
- Qt decoded-audio buffers and playback transitions recorded in
  `build/playback-qa/native-events.jsonl`; no playback errors were reported.
- UI fixture and inputs: `build/playback-qa/preview.py` and its `library` folder.
- Previous source and executable backup folder: `backups/preview-playback-20261030`.
- Final preview tests: 6 passed after the replay-status adjustment.
- Packaged UI successfully played `mr-jones-B.mp3`, `mr-jones-B.mid`, and
  `mr-jones-D-2.mid` together (4:32 preview), and Stop reset the position to zero.
- Verified candidate: `build/playback-release/GuitarHacks.exe`, SHA-256
  `3d17bd77ed3533b659efe24cbc66aab726916567bb21a21530396fdfaf735e23`.
- Installed after explicit restart approval on October 30. The installed
  `FretboardFiend/release/GuitarHacks.exe` matches the verified candidate hash.
  Playback licenses accompany the release in `playback-licenses`.

# Slice destination workflow - October 30, 2026

The action always reads **Create slices**. Existing song folders are reused;
new songs open a folder-name dialog before processing. **Use a different
folder...** opens the same dialog with an unused sibling name suggested and a
Browse control for changing the parent. Cancel leaves the destination unchanged.
Existing exports are kept and filename collisions receive a numeric suffix.
Chosen destinations are remembered in `StemSlicer/song-folders.json`; folders
outside `StemSlicer/separated` remain available in the saved-song list.

Validation from `D:\Studio13\Lab\Music\GuitarHacks`:
- `.venv\Scripts\python.exe -m unittest discover -q`: 81 tests passed.
- Native desktop UI: entered `Slice folder QA` for a new song and completed a
  real 10-second vocal MP3 export. Run: `StemSlicer/processing/20261030-104352-a730c0`.
- Native desktop UI: used **Use a different folder...**, browsed to
  `build/slice-destination-qa`, accepted `Slice folder QA 2`, and completed
  another real export. Run: `StemSlicer/processing/20261030-104943-a64876`.
- Both runs displayed COMPLETE and retained the **Create slices** label.
- Build: `& .\build.ps1 -OutputDirectory build\slice-destination-release`.
- Candidate SHA-256: `36aeb62eff987b9fc438ebd111feae9846b076fcba0fec60e2a8304c7780d264`.
- Installed `FretboardFiend/release/GuitarHacks.exe` matches that hash. The
  previous executable is in `backups/slice-destination-20261030/GuitarHacks.exe`.
- Test exports are retained under `build/slice-destination-qa/first-export`
  and `build/slice-destination-qa/Slice folder QA 2`; the test-only destination
  registry entry was removed after testing.

MIDI inference and audio separation models are unchanged by this update.
The MIDI accuracy concerns remain unresolved. Earlier validation below is
historical; its executable hashes describe those earlier releases.

# MIDIfier instrument conditioning - October 29, 2026

Current source: Instruments menu defaults to From stem. Verified saved recipes
condition MuScriptor Large inference; originals, unknown or modified stems and
recipes containing other instruments stay unrestricted. Manual family presets
apply to all checked inputs. Polyphony and seconds-based timing remain intact.
Existing exports are preserved. No Reason, Remote, driver or audio-service changes.

Native inference writes actual settings plus a SHA-256 binding to its note TSV.
The writer rejects mismatched requests or stale sidecars before publishing MIDI.
Saved originals beat unrelated same-title picker files; a missing original can
be restored by choosing its replacement. Automatic recipes require audio hashes.

Verification:
- 76 root tests passed: `.venv\Scripts\python.exe -m unittest discover -v`.
- Regression tests failed before the fixes and passed afterward: stale recipe
  detection, missing-original recovery and native-settings/TSV mismatch rejection.
- Native build passed: `& .\NeuralNote\cli\build.ps1`.
- Actual Large GPU inference, same first 20 seconds of each existing Mr Jones
  stem, unrestricted versus conditioned. Evidence:
  `build/midi-instruments-qa/verified-comparison/comparison.json`.
- Bass unrestricted: 27 electric-bass notes plus 34 drum notes. Conditioned:
  47 acoustic-bass notes and no drums. The requested family includes both bass
  types; this does not prove correct timbre, pitches, timing or completeness.
- Drums unrestricted: 119 notes; conditioned: 130 notes. Counts alone cannot
  establish better accuracy. No annotated-reference or listening score claimed.
- All four exports verified native settings digests and preserved timing.
- Large weights, greedy decoding and upstream prelude forcing are unchanged.
  CFG tuning remains deferred because this backend does not expose the control.

Reproduce from `D:\Studio13\Lab\Music\GuitarHacks` using a new output folder:

```powershell
.venv\Scripts\python.exe tools\compare_midi_instruments.py --output build\midi-instruments-qa\new-comparison --drums 'StemSlicer\separated\Mr  Jones\mr-jones-D.mp3' --bass 'StemSlicer\separated\Mr  Jones\mr-jones-B.mp3' --seconds 20
& .\build.ps1 -OutputDirectory build\midifier-instruments-verified
```

Before-task source, executable and native-engine backup:
`backups/midifier-instruments-20261029-150147`.
Installed executable: `FretboardFiend/release/GuitarHacks.exe`.
Candidate: `build/midifier-instruments-verified/GuitarHacks.exe`.
Both SHA-256: `1a206bd867eaee57e8709ccb1557d84f7bedb167fd852a2169e5d32f5cf77355`.
Native engine SHA-256: `be8271afab06991c48b715a1ca5711651922f3fd69cae2154eba4dc7ef925be8`.
Installed native UI verified the compact Instruments selector at 800 logical
pixels wide, with the footer and all MIDI controls visible without overlap.
Packaged UI completed a full 271.542875-second drum-stem conversion using
From stem, `INSTRUMENTS drums`, Vulkan / NVIDIA GeForce RTX 3080. Run:
`StemSlicer/processing/20261029-152239-midi-78bc5d`.
UI reported MIDI COMPLETE - 1 of 1 MIDI files saved. New file:
`StemSlicer/separated/Mr  Jones/mr-jones-D-2.mid`, 1901 notes, one drum track,
120 BPM test metadata. Mido roundtrip verified all note-ons on channel 10,
the note count, TSV digest and MIDI digest. The prior MIDI was not overwritten.
The original 120 BPM test setting was retained, not inferred from the song;
set the project tempo when using these notes in Reason.
The parent GuitarHacks directory is not a Git repository. Upstream NeuralNote
sources were not modified. Earlier sections below describe previous releases.

# StemSlicer / MIDIfier — October 29, 2026

Current release: inline filename editing and a checked
MIDI batch. The two sections are headed StemSlicer and MIDIfier.

- Click an Output file field and type a custom name. Empty text restores the
  automatic name. Format controls the extension; MP3 + WAV shares one basename.
  Names stay inside the song folder, and existing files get numeric suffixes.
- MIDIfier lists the selected song's ORIGINAL first, highlighted and labelled
  Whole song / All vocals and instruments. Audio stems follow. MIDI outputs
  are accessed through Open folder rather than offered as conversion inputs.
- Check any combination and use Midify selected. Conversion runs sequentially
  with a fixed tempo captured when the batch starts. Cancellation/failure stops
  the queue and retains successful files. Original audio comes from the song's
  manifest or its currently chosen input, never another song's picker state.
- An unavailable original remains visible but cannot be checked. Choose its
  input above to restore it. Old manifests without a source need this step.

Verification:
- 70 tests: `.venv\Scripts\python.exe -m unittest discover -q`.
- Two real audio-export tests: from StemSlicer, run
  `.venv\Scripts\python.exe -m unittest test_mix_export -q`.
  Confirmed custom MP3/WAV names, mix contents, and collision protection.
- Native source UI: clicked filename and typed My lead take.mp3 in place.
- Checked original plus lead stem and clicked the single Midify selected button.
  Original: 185 notes / 3 instrument tracks, run `20261029-111118-midi-9ecf27`.
  Lead: 115 notes / 2 instrument tracks, run `20261029-111127-midi-afdab0`.
  UI reported MIDI COMPLETE — 2 of 2 MIDI files saved.
- Repeated the batch and cancelled the second item. The original completed as
  `midifier-qa-original-2.mid`; the second run `20261029-111257-midi-231cb8`
  stopped without a completion manifest. UI reported 1 of 2 files saved.
- Preview stderr was empty. Models/engine remain unchanged.

Build: `& .\build.ps1 -OutputDirectory build\midifier-release`.
Build log: `build/midifier-qa/build.log`.
Packaged UI also completed the two-file batch (185 and 115 notes). Candidate SHA256: `59b571a1f7df4325d25308ae252b2c05457ddc5e4fc941e6b773205e3812b2e8`. Installation was approved by the user. Test exports are preserved in `build/midifier-qa/exports`; historical processing manifests retain their original paths.
Source backup: `backups/stems-midify-20261029`.

Earlier sections below are historical verification of previous UI versions.
# Compact desktop UI — October 29, 2026

Candidate: `build/stems-compact-release/GuitarHacks.exe`.
SHA256: `f90d286418dd724814bad95461a6eb6c3bb9dc986d15ba533c85bac3ec19243a`.
Installed after user approval at `FretboardFiend/release/GuitarHacks.exe`; installed and candidate SHA256 match. Previous executable preserved in `backups/stems-compact-20261029/GuitarHacks.exe`.

- StemSlicer opens at 800 logical pixels wide. Home restores the prior window geometry.
- One dropdown-style audio picker replaces the button and separate filename.
  Initial text: Choose a File to Be Stemmed.
  Native file dialog starts in `D:\Studio13\Lab\Music\GuitarHacks\StemSlicer\Originals`.
- Song title and saved-song selection use compact widths. Create/Cancel are
  below the stem table; Processing log is alongside the MIDI controls.
- Table and saved-file list grow with content, then scroll at their height limits.
- Source native preview verified opening Originals, selecting the existing MP3,
  updating title/output names, and adding a fifth stem row.
- All 68 root tests passed: `.venv\Scripts\python.exe -m unittest discover -q`.
- Build succeeded: `& .\build.ps1 -OutputDirectory build\stems-compact-release`.
  Log: `build/stems-compact-build.log`.
- Packaged native preview verified the five-row layout without overlap, with all MIDI controls and footer visible.
- Source backups: `backups/stems-compact-20261029`.

The older executable information below describes the October 28 installation.
# MIDI workflow — October 28, 2026

Original → MIDI works independently of stem creation. Selected stem → MIDI
uses the chosen saved audio file. Tempo is user-set; the local Large model
generates polyphonic notes and the writer preserves seconds-based timing.
Existing files are preserved with numeric suffixes on reruns.

Validation:
- 68 root tests passed (`.venv\Scripts\python.exe -m unittest discover -q`).
- Native UI Original → MIDI: ten seconds from Wasteland, 185 notes, 3 tracks.
  Run: `StemSlicer/processing/20261028-162651-midi-5a51e8`.
- Native UI Selected stem → MIDI: ten seconds of the lead stem, 115 notes,
  2 tracks. Run: `StemSlicer/processing/20261028-162806-midi-dd3c1b`.
- Both runs reported `DEVICE Vulkan / NVIDIA GeForce RTX 3080`.
- Installed one-file executable also completed Selected stem → MIDI: 115
  notes, 2 tracks, at 120 BPM, confirmed in its native UI and completion
  manifest. Run: `20261028-163209-midi-dbac62`. Both the candidate and installed
  executable have the SHA256 below. Test audio and MIDI outputs were moved
  out of the saved-song list to `build/midi-workflow-qa/exports` afterward;
  historical manifests keep their original paths as provenance.
- Native rerun produced `midi-workflow-qa-original-2.mid` without overwriting.
- Cancellation of the full original stopped the worker at 5%, retained previous
  exports, and produced no completion file. Run: `20261028-162951-midi-8ac9f7`.
- Musical accuracy is not a scored benchmark; instrument leakage and note
  errors may require editing. Velocity is fixed at 96; no bend transcription.

Installed executable: `FretboardFiend/release/GuitarHacks.exe`.
SHA256: `f03d39c5efe01db70b3169e773b00a573a9dfd35a794ed0d304442f74e42b9cf`.
Previous executable: `backups/stems-midi-20261028/GuitarHacks.exe`.
Local engine: `NeuralNote/cli/build/Release/guitarhacks-transcribe.exe`.
Engine SHA256: `00ca771fe3b2ebfd9c160b3244b30f102367ee14c6248b5d186f183fe1488794`.
Model SHA256 matches the upstream Large file after the drive returned:
`35a750fb1ab1e77195cdc2c0b9b4aeea2f4d59f11f729f02af9920c4854ef72e`.

## Drive interruption evidence

D: disappeared during the first build. Windows logged iaStorAC event 129 at
16:08:29 local, followed by disk event 51, delayed-write errors and NTFS event
140 after dismount. The returned CT4000MX500SSD1 drive is online and reports
healthy; this does not establish the cause. One new test file contained only
zeros after recovery; it was preserved as evidence and restored from this
session's source. The native engine was rebuilt in a fresh build directory.
No disk repair, driver change, or storage configuration change was performed.

Evidence is on C: at
`C:\Users\NickKatsivelos\AppData\Local\GuitarHacks\diagnostics\drive-D-20261028-162238`.
Read-only capture helper: `tools/diagnostics/capture-drive.ps1`; a copy is
also in that C: diagnostics parent directory so it remains runnable without D:.

## Historical stem containers and compact layout — October 28, 2026

Current source UI: one table row per output stem; overlapping instrument
selections are allowed. The table fits actual rows, growing until scrolling
is needed. The saved-file list fits actual filenames and is hidden when empty.
Completion is an explicit COMPLETE message plus an Open completed stems button.

Verification:
- 65 app tests passed before the final sizing change; the five Home tests
  passed after it.
- Two exporter tests passed in the StemSlicer environment. They check the
  actual waveforms for lead alone and lead + rhythm, MP3 decoded length and
  correlation, duplicate recipe names, and preservation of existing files.
- An actual Qt page and QProcess pipeline test generated fresh full-song
  MP3s from Originals/06 Letters From The Wasteland.mp3. It verified two rows
  fit in 104 pixels, adding a row grows the table, removing it shrinks it,
  and the two-file list uses 38 pixels. UI status: COMPLETE — 2 stems saved
  (2 files). Evidence: build/stem-container-qa.json and its processing log.
- New outputs: StemSlicer/separated/Letters From The Wasteland/
  letters-from-the-wasteland-L.mp3 and letters-from-the-wasteland-L-R.mp3.
- The Qt execution test used the offscreen platform to avoid disturbing the
  user's current app. Its screenshot cannot assess typography because the
  offscreen font backend rendered missing glyphs; geometry and runtime
  assertions passed. Native visual review of the installed executable passed after the approved restart: the two-row table and two-file list fit their contents, and the new song folder is listed.

Installed after user-approved restart: FretboardFiend/release/GuitarHacks.exe.
SHA256: a1014905f90f6359bdab9a140ace5d3679bcd161e3cd0aad6206c197fa4e2fbf.
Backup: backups/stems-containers-20261028-155257/GuitarHacks.exe.
Candidate and installed hashes match. Earlier module details below are historical.

## Historical initial-module verification

# StemSlicer home module — October 28, 2026

Installed executable:
`D:\Studio13\Lab\Music\GuitarHacks\FretboardFiend\release\GuitarHacks.exe`

SHA256: `bd5fed7fb2f92a1fafcb15191d9929059b5c600dd4712e118226c9e2056b2966`

Prior executable backup:
`D:\Studio13\Lab\Music\GuitarHacks\backups\stems-module-20261028-152553\GuitarHacks.exe`

Home now has a fourth card, StemSlicer. The native page has seven independent
checkboxes: vocals, drums, bass, piano, other instruments, lead guitar, rhythm
guitar. All start checked. Unchecking everything disables the start button.
Choices stay fixed while a run is active. Only selected parts are exported;
the lead/rhythm stage is skipped if neither guitar part is checked.

Verified:
- `uv run --frozen python -m unittest discover -q`: 65 tests passed. Test log
  is `build/stems-tests.log`; expected failure-injection logs are included.
- After isolating the new selection test fixture from installed sample files,
  `uv run --frozen python -m unittest test_home -q`: 5 tests passed.
- Actual source app: used the file chooser and checkboxes to process
  `StemSlicer/Originals/06 Letters From The Wasteland.mp3` with only vocals,
  lead guitar and rhythm guitar selected. The UI completed and showed exactly
  those three outputs. Each WAV has 12,018,720 samples/channel, stereo 44.1 kHz,
  24-bit PCM. Results:
  `StemSlicer/separated/instruments/06 Letters From The Wasteland - 20261028-152125-581498`.
- Processing log: `StemSlicer/processing/20261028-152125-581498/processing.log`.
- Bass-only export succeeded with a nonexistent guitar folder, proving
  unselected guitar files are not required. Evidence:
  `StemSlicer/verification/selected-bass-export/verification.json`.
- `.\build.ps1 -OutputDirectory build\stems-release`: passed. Opened the
  resulting executable normally, clicked Home's StemSlicer card, and verified
  all seven checkboxes and the saved three-stem result in the packaged UI.
- Installed only after verifying the prior installed executable was closed;
  candidate and installed SHA256 hashes match. User data was not moved.

The full processing run was through the source UI; packaged verification
covered navigation, checkboxes, project discovery, and results listing.
Cancellation and the close-during-processing guard were code-reviewed but
not manually exercised. Runtime requires local StemSlicer Python/models,
FFmpeg/ffprobe and CUDA. Stereo 44.1 kHz inputs only; unsupported formats fail
without conversion. No listening-quality claim is made for source separation.








