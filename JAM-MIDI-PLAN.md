# Jam capture: current implementation and remaining checks

Updated October 28, 2026. The Windows MIDI Services integration is built and tested in a separate candidate. The regular executable is unchanged. Jam's live guitar input is still blocked by its blank startup window; licensing is unresolved. Synthetic MIDI tests do not establish guitar tracking accuracy or audio latency.

## Working path

Guitar/Model 12 channel 5 -> existing audio driver -> Jam -> **GuitarHacks Jam Send** -> Microsoft LOOP transport -> **GuitarHacks Jam Receive** -> version-matched SDK receiver -> local MIDI file -> Guitar Pro import.

The portion from the Send endpoint through the packaged recorder and Guitar Pro has passed with a generated phrase and chord. Jam supplies the audio-to-note conversion; MIDI Services transports and timestamps the notes.

- Receiver: `tools/windows-midi/Program.cs`, SDK `1.0.17-rc.4.25`, matching the installed RC4 runtime. The helper uses private process pipes, with no network listener.
- Qt adapter: `windows_midi.py`; recording page: `jam_view.py`; file export: `jam_midi.py`.
- Dedicated transient LOOP pair, association `777f1e41-79b8-4398-8435-15e77c9de7a3`, unique ID `studio13guitarhacksjam`. `loopback.json` stores identity. The helper reuses the pair, creates it only if absent, and errors if the pair is incomplete or renamed. It does not modify the default loopback or hardware ports.
- Pair recreation after service restart is implemented but not tested by restarting the user's service.
- Runtime input uses the Microsoft SDK only. RtMidi is a build/test dependency for synthetic WinMM sending, not a second app receiver. Installed loopMIDI is unused and has not been removed.
- The receiver emits raw UMP words, service timestamps and clock frequency. Start/stop use the same service clock. GUI delivery time does not determine note duration.
- Each recording saves `.mid` plus `.ump.json`. The latter retains original timestamps, groups, raw packets, controller initialization received since connection, and conversion/failure warnings. MIDI 2.0 basic notes/controllers are reduced to MIDI 1.0 resolution for Standard MIDI File export; unsupported expression stays in the original-data file only. MPE/bend interpretation in Guitar Pro needs review.
- Group-separated MIDI tracks retain channels, notes, velocity, sustain and supported bends/controllers. Stop closes held notes and releases sustain. No physical string recognition is claimed.
- Disconnection/helper failure saves a marked partial take. Failed saves retain the take in memory and offer Retry save; app close is blocked until saved. The buffer and take duration have explicit limits. Sudden power loss/process termination during recording is not crash-recoverable.
- Tempo is selectable; initial time signature is 4/4. Original performance timing stays in MIDI. Guitar Pro's import dialog supplies explicit score quantization and fingering refinement, avoiding a second app quantizer.
- Existing practice grading and audio input remain unchanged. A connected MIDI port does not prove Jam is listening, licensed, or tracking accurately.

## Use the candidate

From `D:\Studio13\Lab\Music\GuitarHacks`:

```powershell
.\build\jam-windows-midi-candidate\GuitarHacks.exe --jam
```

1. Click **Connect MIDI**, then **Open Jam**. In Jam choose **GuitarHacks Jam Send** as MIDI output. Select the guitar input on Model 12 physical channel 5 once Jam's startup/audio issue is resolved.
2. Reselect the Jam patch after connecting so controller initialization reaches the recorder. Mute the strings, set BPM, then Record take.
3. **Stop and save** writes both local files. Takes appear below. A trial interruption can leave gaps; MIDI silence alone cannot identify the reason.
4. **Copy take path and open Guitar Pro** copies the selected path. In Guitar Pro choose **File > Import > MIDI**, paste the path, choose quantization, and import. Use RSE sounds for internal guitar playback. Review rhythm, bends and string/fret choices; save a `.gp` file for further editing.

Passing a MIDI path as a Guitar Pro launch argument did not import it in the installed GP 8.1.5. The app therefore uses the supported explicit import workflow.

Recordings are under the selected data directory's `recordings` folder. Normal candidate use defaults to `build/jam-windows-midi-candidate/data`; use `--data-dir` to select another folder. Do not assume the candidate shares the regular release's learner history.

## Verification completed

- 64 unit/widget tests passed: `build/jam-tests.txt`. Includes chords, service timing, group separation, MIDI 2.0 resolution warnings, sustain release, source controller setup, failure retention and Guitar Pro handoff.
- Real Windows service integration passed: `build/windows-midi-qa/live-5dziaepf/result.json`. WinMM -> SDK, simultaneous WinMM/SDK readers, timestamps despite delayed Qt delivery, reconnect reuse, held-note helper failure and partial recording.
- Packaged UI connected, recorded four notes and a three-note chord, stopped and saved both files. Guitar Pro imported the actual file, rendered score/tab, and advanced its playback cursor through the notes. Audible output and bends were not verified.
- Final candidate relaunched October 28, reconnected through the bundled SDK helper, retained the saved take, and displayed the supported Guitar Pro handoff. SHA256: `7B3F21E1DCAC290BD75630259C2D53957ABB0E15DD4583023DAF4BBD95835212`. Build log: `build/jam-package-final.log`; no errors in the isolated app log. The regular release remains the October 25 executable.
- Editable proof: `build/jam-ui-check/recordings/Take-20261027-214833-325974.gp`; original `.mid` and `.ump.json` are alongside it. This is a synthetic test take, not a performance by Nick.
- Source and old builds are preserved under `backups/20261027-213524-windows-midi-build` and build-specific backup folders. GuitarHacks is not a Git checkout.

## Remaining blocker and acceptance

Jam 3.0.75 currently displays a blank white window. Its log stops after loading the INTRODUCTION patch/tracker. It reports Responding, which does not establish readiness. Earlier attempts selecting USB ASIO reported driver initialization failure; Model Mixer ASIO did not deliver input. Root cause is unknown.

A normal close and fresh-settings launch reproduced the blank window. Original settings were backed up and restored byte-for-byte afterward; the test launch was closed normally. Evidence is in `backups/20261027-213524-windows-midi-build`. No reboot or broader preference/plugin reset was attempted.

Jam log: `%APPDATA%\JamOrigin\MIDI Guitar Log Standalone.txt`. License recovery is outstanding. Public 3.0.75 is older than the documented API minimum 3.0.80, so MIDI remains the approved route.

Before promoting the candidate: resolve Jam startup, verify its Send selector and physical channel 5 input, record a real phrase/chord, check note durations and bends in Guitar Pro, and measure tracking delay before any timing-based grading. These checks require actual guitar input. Do not replace the regular executable or describe the complete guitar workflow as verified until they pass.

No audio drivers, hardware bindings, services, control-surface ports or user audio applications were changed/stopped. MIDI multi-client support does not prove simultaneous ASIO audio ownership.

## Driver context

The USB ASIO source is `D:\Studio13\Lab\Music\gear\low latency development\low-latency-audio`, with existing user changes. The MIDI project is the separate `microsoft/MIDI` repository. Keep the Microsoft main audio baseline and naming-only October 12 update. Installed ASIO hash previously verified:
`59952A9D57639BC89F42559742647F4694827241E7E5DA93EFC2798EBE46C183`.

[USB ASIO chat](codex://threads/019efc80-8a82-76a0-b1fa-9de7ad5d8d04) records the SDK/service history. Launch Control's experimental USBMidi2 switch transmitted CC messages but failed a later Reason mapping check and was rolled back. This is not proof of blanket USBMidi2 incompatibility; preserve working bindings. Model 12 audio and MIDI functions are separate. No driver work is required for this recorder.

## Commands and references

```powershell
Set-Location 'D:\Studio13\Lab\Music\GuitarHacks'
uv run --frozen --group build python -m unittest discover
uv run --frozen --group build python tools/windows-midi/test_live.py
.\build.ps1 -OutputDirectory build\jam-windows-midi-candidate
uv run --frozen python app.py --jam --data-dir build\jam-source-check
& 'C:\Program Files\Windows MIDI Services\Tools\Console\midi.exe' enumerate endpoints --show-endpoint-id --verbose
```

Live tests send only to the dedicated GuitarHacks pair. They do not restart services. Helper build prerequisites and protocol are in `tools/windows-midi/README.md`.

- [Windows MIDI Services](https://microsoft.github.io/MIDI/)
- [Matching RC4 release](https://github.com/microsoft/MIDI/releases/tag/rc-4)
- [RC4 C# samples](https://github.com/microsoft/MIDI/tree/rc-4/samples/csharp-net/basics)
- [Jam API version requirement](https://jam.live/developers/)
- [Guitar Pro MIDI import](https://www.guitar-pro.com/docs/gp8/import-export/import/import-midi)
