# Local MIDI conversion engine

This host uses NeuralNote's existing muscriptor.cpp submodule and
`NeuralNote/models/muscriptor-large-f16.gguf`. Upstream sources are unchanged.
Audio stays local. StemSlicer runs FFmpeg to decode 16 kHz mono float32, this
executable to predict polyphonic notes, and `NeuralNote/export_midi.py` to write
and verify a standard Type 1 MIDI file with named instrument tracks.

Set the UI tempo to match Reason. Timing is relative to the audio's start and
is not quantized. GM programs and drum channel 10 are included. The model does
not predict dynamics, so velocity is fixed at 96. Notes may need editing;
lyrics, string/fret choices, and expressive bends are not recovered.

## Instrument conditioning

MIDIfier defaults to **From stem**. It reads the saved export recipe and
verifies the audio file's SHA-256 before selecting instrument families. A
drum stem requests drums; bass requests both acoustic and electric bass;
lead/rhythm guitar requests acoustic, clean electric and distorted electric
guitar. Piano and vocals have their corresponding groups. Combined recipes
request the union. Originals, unknown recipes, changed files and recipes
containing other instruments remain unrestricted. Names alone are not evidence.

The Instruments menu can override this for every checked file in a batch:
All instruments, Drums, Bass, Guitar, Piano or Vocals. The setting is captured
when the batch starts. This conditions model inference, not a post-export
filter; note timing and polyphony are retained. It does not guarantee accuracy.

Native command, after decoding mono 16 kHz float32 audio:

```powershell
& NeuralNote\cli\build\Release\guitarhacks-transcribe.exe --list-instruments
& NeuralNote\cli\build\Release\guitarhacks-transcribe.exe NeuralNote\models\muscriptor-large-f16.gguf input.f32 notes.tsv --instruments drums
```

Use `--instruments all` for unrestricted inference. Omitting the option is
also unrestricted. Invalid names fail before loading audio or model weights.
Large weights and greedy decoding are unchanged. Prelude forcing was already
enabled upstream. CFG tuning is not exposed by this C++ backend and is deferred.

## Build

From `D:\Studio13\Lab\Music\GuitarHacks` in PowerShell:

```powershell
uv venv --python 3.12 NeuralNote\tools\.build-venv
uv pip install --python NeuralNote\tools\.build-venv\Scripts\python.exe cmake==3.31.6 ninja==1.13.0
# Signature-verified official LunarG 1.4.363.0 SDK installer:
& NeuralNote\tools\vulkan-sdk-installer.exe --root D:\Studio13\Lab\Music\GuitarHacks\NeuralNote\tools\VulkanSDK --accept-licenses --default-answer --confirm-command install copy_only=1
& NeuralNote\cli\build.ps1
```

Requires Visual Studio 2022 C++ tools. CMake fetches the exact ggml revision
pinned by muscriptor.cpp. The SDK uses LunarG's documented copy-only mode:
https://vulkan.lunarg.com/doc/view/1.3.296.0/windows/getting_started.html

Runtime path: `cli/build/Release/guitarhacks-transcribe.exe`. Auto selects an
available GPU or falls back to CPU. The log records the device actually used.
GPU operation depends on the system display driver's `vulkan-1.dll`; CPU can
be much slower. The Python writer uses the main GuitarHacks `.venv`, where
mido is already a locked dependency. Keep NeuralNote and StemSlicer beside the
app; its one-file executable does not bundle the 2.7 GB model.

## Outputs

Original: `StemSlicer/separated/<song title>/<song-slug>-original.mid`.
Stem: beside the selected audio, with its basename and `.mid` extension.
Reruns append `-2`, `-3`, etc.; existing files are never overwritten.
Each export has `midi-manifest-<id>.json` recording source, duration, tempo,
note/track counts, model, and SHA-256. Processing logs and note events live in
`StemSlicer/processing/<run>-midi-<id>`. Cancellation stops the current process.
The UI reports completion only after verifying the completion file and MIDI.

The native host also writes `notes.settings.json` beside `notes.tsv`, recording
the actual instrument groups, decoder, prelude forcing and TSV SHA-256. Windows
CNG computes the hash. The writer verifies that digest and the requested groups
before publishing MIDI, then copies the settings into the manifest. Legacy TSV
exports without a sidecar still work only when no explicit groups were requested;
they do not claim unverified inference settings.

Model provenance and licensing remain documented in `NeuralNote/README.md`.
