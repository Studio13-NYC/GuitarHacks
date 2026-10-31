# StemSlicer

GuitarHacks subproject for audio stem separation and practice backing tracks.
Available from the desktop GuitarHacks **Home → StemSlicer** module. Choose a
file and create one table row per output stem. Each row has independent
instrument checkboxes; the same instrument can be included in multiple rows.
The module runs locally and never overwrites previous exports. MP3 is the
default; WAV or both formats are available. New files are saved directly in
`separated/<song title>` with instrument codes in their names.
Moved from `D:\Studio13\Lab\Music\gear\tools\demucs` on October 28, 2026.
The old location is now a directory junction to this folder so existing
Reason audio references and older commands continue to resolve.

## Audio to MIDI

In Home → StemSlicer, set **Tempo** to match the Reason project, then:

- In **MIDIfier**, choose a saved song and check its ORIGINAL, any stems, or both.
- Leave **Instruments** at **From stem** to use verified saved stem recipes.
  Originals, unknown/changed files and recipes containing other instruments
  use all instruments. There is no filename-based guessing.
- Or select All instruments, Drums, Bass, Guitar, Piano or Vocals manually;
  the override applies to every checked file in that batch.
- Click **Midify selected**. Files run sequentially with tempo and instrument
  selections captured when the batch starts. No stem creation is required
  when transcribing an available original.
- **Show MIDI file** selects the finished `.mid` file in Explorer for importing into Reason or Guitar Pro.

Conversion uses the local NeuralNote Large model and supports polyphonic notes.
MIDI files are saved alongside the song's stems: `<song>-original.mid` for the
original, or `<stem filename>.mid` for a stem. Reruns add numeric suffixes and
preserve previous files. Progress, cancellation, and processing logs use the
same controls as separation. Each MIDI file has named tracks for the instruments
detected, with notes at their original times. Notes are not quantized; velocity
is fixed because this model does not predict dynamics. Review/edit the result.
Conditioning guides inference rather than deleting predicted notes afterward.
The manifest records native inference settings verified against the note events.
Existing MIDI files are not changed; rerun conversion to use the new settings.
See `../NeuralNote/cli/README.md` for build details and runtime dependencies.

## Existing outputs

- `separated/instruments/06 Letters From The Wasteland/`: October 28 fresh
  seven-stem set: vocals, drums, bass, piano, other, lead guitar, rhythm guitar.
  All generated locally from the MP3 in `Originals/`; no older stems reused.
- `separated/htdemucs/`: drums, bass and rhythm-section mix.
- `separated/htdemucs_6s/`: combined guitar extraction.
- `separated/mvsep-lead-rhythm/`: MVSep rhythm-guitar outputs.
- `separated/backing-track/`: finished Wasteland backing mix and processing sources.
- `separated/backing-track/06 Letters From The Wasteland/aligned-drums-and-backing/`:
  sample-aligned drums and backing-without-drums WAVs for Reason.

MVSep outputs are retained here; MVSep itself is an external service, not an
installed local engine. Demucs runs locally. Model downloads use the existing
PyTorch cache; shared caches and the original music library were not moved.

Historical logs and `alignment-check.json` retain the original paths as
provenance. Those paths resolve through the compatibility junction. Current
usage instructions use StemSlicer. See `verification/migration-manifest-20261028.json`
for file hashes recorded before the move, prior to documentation updates.

Local Windows x64 setup managed by uv. Python 3.11, Demucs 4.1.0,
and CUDA-enabled PyTorch are installed in `.venv`. Exact dependency versions
are recorded in `uv.lock`. FFmpeg and ffprobe must be available on PATH;
this machine uses `C:\Program Files\ffmpeg\bin`.

## Separate a track

Open PowerShell and run:

```powershell
Set-Location 'D:\Studio13\Lab\Music\GuitarHacks\StemSlicer'
uv run --locked demucs -d cuda -n htdemucs --int24 'D:\Music\song.wav'
```

Replace the example input path with your track. This writes four stereo
24-bit WAV files at 44.1 kHz: `vocals.wav`, `drums.wav`, `bass.wav`, and
`other.wav`, in `separated\htdemucs\song\` under this directory.
Model weights download on first use and are cached for later runs.
The original input file is preserved.

### Custom stem mixes including lead and rhythm guitar

The desktop module writes a plan for each run under `processing/<run>/plan.json`.
For example, this plan creates two stems with an overlapping lead part:

```json
{"title":"Wasteland","format":"mp3","stems":[["lead-guitar"],["lead-guitar","rhythm-guitar"]]}
```

Run from `D:\Studio13\Lab\Music\GuitarHacks\StemSlicer`. Use a fresh processing
directory for each run and save the plan there before running these commands:

```powershell
uv run --locked python separate_instruments.py 'Originals\06 Letters From The Wasteland.mp3' 'processing\wasteland-fresh\instruments'
uv run --locked python split_guitars.py 'processing\wasteland-fresh\instruments\guitar.wav' 'processing\wasteland-fresh\guitars' --model 'models\lead-rhythm-demucs\model.ckpt' --config 'models\lead-rhythm-demucs\config.yaml'
uv run --locked python export_stems.py 'Originals\06 Letters From The Wasteland.mp3' 'processing\wasteland-fresh\instruments' 'processing\wasteland-fresh\guitars' 'separated\Wasteland' --plan 'processing\wasteland-fresh\plan.json' --completion 'processing\wasteland-fresh\completion.json'
```

If no stem contains a guitar part, skip `split_guitars.py`; the export script
does not read the guitar folder in that case. Formats: `mp3`, `wav`, `both`.
Names encode contents (e.g. `wasteland-L.mp3`, `wasteland-L-R.mp3`), with numeric
suffixes for collisions. Every completed batch has a `stem-manifest-*.json`
in the song folder, including definitions, source hash and measurements.
The legacy `--stems` argument is retained for the previous installed UI during
upgrades; new work should use plans. It maps each instrument to a separate WAV.

This route uses local CUDA inference: Demucs `htdemucs_6s`, followed by the
Dry Paint Dealer Undr lead/rhythm HTDemucs model. Model provenance is in
`models/lead-rhythm-demucs/README.md`. It requires stereo 44.1 kHz input;
unsupported formats fail rather than silently resampling. FFmpeg decodes
the source with MP3 padding excluded, then preserves floating-point estimates
without the clamping performed by Demucs 4.1.0's own WAV writer. Final exports
share one headroom adjustment and preserve sample count and start position.

These are estimated parts, not original studio multitracks. Lead/rhythm
crossover is possible. The piano stem is quiet; other may include keyboards
and effects. Listening is needed to judge musical isolation. Fresh-run
logs and plans are kept in `processing/<run>`. Each song folder includes
`stem-manifest-*.json` with measured format, sample counts, peaks, hashes,
and the instrument contents of each output.

For a basic Demucs CLI vocals/instrumental split, add `--two-stems vocals`
to the `demucs` command in the earlier section.
For the fine-tuned model, replace `htdemucs` with `htdemucs_ft`; it runs four
models and takes longer. This also downloads additional model weights.

To choose an output directory, add `-o 'D:\Music\Stems'`.
Tracks with the same filename stem share the same output folder, so choose
a different output directory when processing identically named tracks.

## Restore the environment

The environment was rebuilt at the new path on October 28, 2026. The previous
environment is retained as `.venv-before-move/` because automatic approval review
blocked its cleanup. It is a backup, not the active environment.

```powershell
Set-Location 'D:\Studio13\Lab\Music\GuitarHacks\StemSlicer'
uv sync --locked
uv run --locked demucs --help
uv run --locked python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

No environment activation is needed. If the GPU runs out of memory, add
`--segment 5` to reduce the processing window, or replace `-d cuda` with
`-d cpu` to process on the CPU.

## Verified setup (October 3, 2026)

- Python 3.11.9, Demucs 4.1.0, PyTorch 2.14.1+cu126, NumPy 2.4.6.
- CUDA 12.6 is available and uses the NVIDIA GeForce RTX 3080.
- NumPy is an explicit dependency here because Demucs 4.1.0 imports it but
  does not declare it for Windows in its package metadata.
- The actual CLI loaded `htdemucs`, performed GPU inference on an eight-second
  synthetic stereo WAV, and exported all four stems. Each was checked as
  stereo, 44.1 kHz, 24-bit, and eight seconds long.
- This test verifies installation and processing, not separation quality on
  a music recording. `htdemucs_ft` and the vocals-only mode have not been tested.

The verification command was:

```powershell
uv run --locked demucs -d cuda -n htdemucs --int24 -o verification\stems verification\setup-test.wav
```

Evidence is kept in `verification\separation.log`, `verification\runtime.txt`,
and `verification\output-check.json`. The `verification` directory is ignored
by Git. The GuitarHacks parent is not currently a Git repository.

## Sources

- [Current Demucs package](https://pypi.org/project/demucs/)
- [Maintainer repository](https://github.com/adefossez/demucs)
- [PyTorch CUDA wheels](https://download.pytorch.org/whl/cu126/torch/)

