"""Mix user-defined stems, verify the audio, and publish into a song folder."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

import numpy as np
from recipe_spec import FORMATS, output_bases, song_title, validate_stems


def decode(path):
    metadata = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'stream=sample_rate,channels,bits_per_sample', '-of', 'json', str(path)
    ]))['streams'][0]
    raw = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
        '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1'
    ])
    return metadata, np.frombuffer(raw, dtype='<f4').reshape(-1, metadata['channels'])


def mix_parts(parts, instruments, guitars, shape, sr, channels):
    mix = np.zeros(shape, dtype=np.float64)
    for name in parts:
        folder = guitars if name in ('lead-guitar', 'rhythm-guitar') else instruments
        meta, audio = decode(folder / f'{name}.wav')
        if (int(meta['sample_rate']), meta['channels']) != (sr, channels) or audio.shape != shape:
            raise ValueError(f'Audio format or length mismatch: {name}')
        if not np.isfinite(audio).all():
            raise ValueError(f'Nonfinite samples: {name}')
        mix += audio
    return mix


def export(source, instruments, guitars, output, plan, completion):
    title = song_title(plan['title'])
    stems = validate_stems(plan['stems'])
    extensions = FORMATS[plan['format']]
    meta, original = decode(source)
    sr, channels, shape = int(meta['sample_rate']), meta['channels'], original.shape
    del original
    peak = 0.0
    for parts in stems:
        mix = mix_parts(parts, instruments, guitars, shape, sr, channels)
        peak = max(peak, float(np.abs(mix).max()))
    gain = min(1.0, 10 ** (-3 / 20) / peak) if peak else 1.0
    output.mkdir(parents=True, exist_ok=True)
    bases = output_bases(title, stems, [p.stem for p in output.iterdir() if p.suffix.lower() in ('.mp3', '.wav')], plan.get('names'))
    report = {
        'title': title, 'source': str(source.resolve()),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'sample_rate': sr, 'channels': channels, 'samples_per_channel': shape[0],
        'duration_seconds': shape[0] / sr, 'start_offset_samples': 0,
        'resampling': False, 'trimming': False, 'format': plan['format'],
        'common_gain_db': 20 * math.log10(gain), 'files': {}, 'stems': stems,
        'note': 'Recipes can overlap. Playing overlapping stems together doubles their shared instruments. MP3 is lossy; use WAV for DAW alignment.'
    }
    # Stage in a new directory within this exact output folder; validate the
    # whole batch before publishing. No existing media file is overwritten.
    with tempfile.TemporaryDirectory(prefix='.pending-', dir=output.resolve()) as staging:
        staged = []
        for parts, base in zip(stems, bases):
            mix = mix_parts(parts, instruments, guitars, shape, sr, channels) * gain
            for ext in extensions:
                target = Path(staging) / (base + ext)
                codec = ['-c:a', 'libmp3lame', '-b:a', '320k'] if ext == '.mp3' else ['-c:a', 'pcm_s24le']
                subprocess.run([
                    'ffmpeg', '-v', 'error', '-n', '-f', 'f64le', '-ar', str(sr), '-ac', str(channels),
                    '-i', 'pipe:0', *codec, str(target)
                ], input=np.ascontiguousarray(mix, dtype='<f8').tobytes(), check=True)
                out_meta, audio = decode(target)
                if audio.shape != shape or int(out_meta['sample_rate']) != sr or not np.isfinite(audio).all():
                    raise ValueError(f'Export verification failed: {target.name}')
                measured_peak = float(np.abs(audio).max())
                if measured_peak >= 1:
                    raise ValueError(f'Export would clip: {target.name}')
                if ext == '.wav' and out_meta['bits_per_sample'] != 24:
                    raise ValueError('WAV bit depth mismatch')
                if ext == '.wav' and float(np.abs(audio.astype(np.float64) - mix).max()) > 2 / 2**23:
                    raise ValueError('Export differs from requested mix')
                report['files'][target.name] = {
                    'instruments': parts, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                    'samples_per_channel': len(audio),
                    'peak_dbfs': 20 * math.log10(measured_peak) if measured_peak else None,
                }
                staged.append(target)
        published = []
        try:
            for target in staged:
                destination = output / target.name
                # Atomic creation refuses name collisions, including simultaneous runs.
                os.link(target, destination)
                published.append(destination)
            manifest = output / f'stem-manifest-{uuid.uuid4().hex}.json'
            manifest.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        except Exception:
            for destination in published:
                destination.unlink()
            raise
    completion.write_text(json.dumps({'output': str(output.resolve()), 'manifest': str(manifest.resolve()),
                                     'files': list(report['files']), 'stem_count': len(stems)}, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'instruments', 'guitars', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--completion', type=Path)
    # Preserve the previous installed app's command during an upgrade. Both
    # interfaces use the same mixing/export implementation.
    parser.add_argument('--stems', nargs='+')
    args = parser.parse_args()
    if args.plan:
        if not args.completion:
            parser.error('--completion is required with --plan')
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
    else:
        if not args.stems:
            parser.error('Provide --plan and --completion')
        plan = {'title': args.source.stem, 'format': 'wav', 'stems': [[name] for name in args.stems]}
    completion = args.completion or args.output / 'completion.json'
    export(args.source, args.instruments, args.guitars, args.output, plan, completion)
    if not args.plan:
        result = json.loads(completion.read_text(encoding='utf-8'))
        (args.output / 'verification.json').write_text(Path(result['manifest']).read_text(encoding='utf-8'), encoding='utf-8')


if __name__ == '__main__':
    main()

