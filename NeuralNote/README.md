# NeuralNote in GuitarHacks

Installed on 2026-10-28 for local, polyphonic audio-to-MIDI transcription. Start with the upstream application and customize its source as needs become concrete. Synth routing in Reason is deferred.

## Open and use

Open `Launch NeuralNote.lnk`, or run:

```powershell
& 'D:\Studio13\Lab\Music\GuitarHacks\NeuralNote\app\NeuralNote.exe'
```

Load an audio file, or configure an audio input and record a take. Choose the instruments present, click Transcribe, then export MIDI. Transcription happens after audio capture. This is not a live guitar-to-MIDI tracker. For guitar recording, use the actual guitar input (Nick's usual Model 12 channel 5); recording-channel setup and live guitar accuracy have not yet been validated here.

The installer placed the VST3 at `C:\Program Files\Common Files\VST3\NeuralNote.vst3`. Let Reason scan plugins, insert NeuralNote as an audio effect, capture track audio, then export/import the resulting MIDI. The VST3 is now verified open in Reason and recognizes the Large model after the AppData repair described below. Transcription within Reason is still untested. No synth routing is configured.

## Layout

- `app/`: upstream 2.1.0 standalone executable and uninstaller.
- `source/`: independent Git checkout, including JUCE and muscriptor.cpp submodules.
- `models/`: verified MuScriptor Large FP16 download retained with the project. A runtime copy is installed in normal Windows AppData for Reason and ordinary standalone launches.
- `downloads/`: retained official installer.
- `verification/`: installation log and runtime verification evidence.

The normal runtime model location is `C:\Users\NickKatsivelos\AppData\Roaming\NeuralNote\models\muscriptor-large-f16.gguf`. It contains a copy installed through Windows Explorer. The initial setup from Codex created a junction inside Codex's redirected package AppData (`C:\Users\NickKatsivelos\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Roaming\NeuralNote\models`), which Reason could not see. Do not use a successful file listing from a Codex child process alone to prove the normal AppData install exists; verify in Explorer and in Reason. Global preferences, logs and captured recordings normally live in `%APPDATA%\NeuralNote`; Codex-launched processes may see the redirected copy. Temporary dragged MIDI uses `%TEMP%\neuralnote`. During uninstall, decline deletion of user data if you want to retain the model and recordings.

## Customization starting point

Upstream: https://github.com/DamRsn/NeuralNote

Release: `v2.1.0`; commit `7734729a2d54cecfb4e5a6ea5d981689bfecb6be`.

Local branch: `guitarhacks/customizations`. No engine or UI source changes have been made. The installed binaries are the official release, not a local build. The GuitarHacks parent folder is not currently a Git repository, so this is an independent nested repository, not a Git submodule of GuitarHacks.

```powershell
git -C 'D:\Studio13\Lab\Music\GuitarHacks\NeuralNote\source' status --short
git -C 'D:\Studio13\Lab\Music\GuitarHacks\NeuralNote\source' submodule status
```

Upstream's build requirements and commands are in `source/README.md`. Windows GPU builds need a C++23 toolchain, CMake, Python and the Vulkan SDK. Local source compilation has not been configured or validated in this installation; the release already includes Vulkan support. Keep future customized builds separate until validated, then replace the installed app/plugin deliberately.

## Sources and integrity

Installer: https://github.com/DamRsn/NeuralNote/releases/download/v2.1.0/NeuralNote_Installer_Windows_x64.exe

Installer SHA256: `74e2e22c20e9c9b832c8208b9e596cc44689ab17b3fdb6ed97548e6e911723f2`, checked against GitHub release metadata before installation. Installer completed with exit code 0.

Large model: https://huggingface.co/DamRsn/muscriptor-gguf/resolve/d7045f94e8b19427f4ff9542975035e66596e51c/v1/muscriptor-large-f16.gguf

Expected size: 2,739,142,176 bytes. Expected SHA256: `35a750fb1ab1e77195cdc2c0b9b4aeea2f4d59f11f729f02af9920c4854ef72e`. Both values are pinned in the checked-out upstream `Lib/Model/ModelManifest.h`. See `verification/RESULTS.md` for the final verification outcome.

## License and limits

NeuralNote code is Apache-2.0; MuScriptor weights are CC BY-NC 4.0 (noncommercial). Dependencies have separate notices in `source/Installers/license.txt`; do not assume the application's Apache license covers all dependencies or the weights. Review those terms before distributing a customized product.

The model does not estimate velocity, tempo, time signature or key. Set the MIDI export tempo intentionally. Polyphonic transcription quality on Nick's guitar still needs testing with real chords, strums, repeated notes and overlapping notes. A successful sample transcription proves the installation works, not performance accuracy on every guitar take.


