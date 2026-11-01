# GuitarHacks Windows desktop download

Release: `v0.1.0-alpha.1` (Windows x64 portable preview).

1. Download `GuitarHacks-Windows-x64.zip` from the GitHub release.
2. Extract the entire ZIP into a writable folder you control, such as `Documents\GuitarHacks`. Do not run from inside the ZIP or put it under Program Files.
3. Open `GuitarHacks.exe`. Python is not required for the core practice app.

The executable is not code-signed. This is an alpha release. No personal data, API keys, audio recordings, model weights or preconfigured audio device settings are included.

## Included

- Home, note flash cards, Find Everywhere, Chord Painter and Fretboard Explorer.
- Note/chord lookup and selectable C/A/G/E/D movable shapes. E/A patterns cover all supported chord qualities; C/G/D have a smaller explicit library. The app explains unavailable patterns and fret-range limits.
- Click-based games, retries, local round review and the career chart.
- Native guitar input/calibration and Windows speech-command integration. Choose your own audio input; accuracy depends on your signal and setup. Windows speech recognition and a microphone are needed for voice commands.
- Entry points for the local StemSlicer, MIDIfier and Jam tools; their additional dependencies are not installed by this ZIP.

## Additional setup

- StemSlicer: clone the repository, follow `StemSlicer/README.md`, and place the extracted executable folder inside that checkout so it can find the `StemSlicer` project in its parent directories. Separation needs its Python environment, model weights and FFmpeg. The standalone ZIP displays Setup needed without that installation.
- MIDIfier: additionally follow `NeuralNote/README.md` for the local transcription components and model. Conversion is an estimate and needs musical review.
- Jam recording: install/configure Jam Origin, an audio interface and the Windows MIDI prerequisites described in `JAM-MIDI-PLAN.md`. Jam is separate software; no license is included.
- MIDI preview uses additional synthesis resources; see `StemSlicer/README.md` and the included playback notices.
- GPT review: optional. Configure your own local OpenAI API access using `docs/openai-key-setup.md`. The hosted app only enables GPT for accounts approved by its owner. No shared API key is included in the desktop download.

Saved settings, logs and results are created under `data` beside the executable. Chord Painter's practice history is `data/chord-painter.json`; the other native exercises use `data/progress.sqlite3`. Back up this folder before replacing an older executable. The browser can import the Chord Painter JSON; it does not import the native SQLite exercise history.

## Web edition

The web edition provides Explorer and click-based Chord Painter. Native audio, voice, separation and recording are visibly marked Desktop app required. Direct JSON saving is available in supported desktop browsers; other browsers can use session mode with JSON import/export. Session data disappears when the page closes unless exported.
