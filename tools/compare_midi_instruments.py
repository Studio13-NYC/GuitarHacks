"""Compare unrestricted and conditioned Large inference on identical short audio clips."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from NeuralNote.export_midi import export


def compare(output, drums, bass, seconds):
    output.mkdir(parents=True, exist_ok=False)
    engine = ROOT/'NeuralNote/cli/build/Release/guitarhacks-transcribe.exe'
    model = ROOT/'NeuralNote/models/muscriptor-large-f16.gguf'
    ffmpeg = shutil.which('ffmpeg') or 'C:/Program Files/ffmpeg/bin/ffmpeg.exe'
    summary = {'seconds_requested': seconds, 'bpm_for_export': 120,
               'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
               'model': model.name, 'runs': [],
               'limits': 'No annotated reference or listening score. Counts do not establish musical accuracy.'}
    for kind, source, selected in (('drums', drums, ['drums']),
                                   ('bass', bass, ['acoustic_bass', 'electric_bass'])):
        raw = output/f'{kind}.f32'
        subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-v', 'error', '-i', str(source),
                        '-t', str(seconds), '-vn', '-ac', '1', '-ar', '16000',
                        '-f', 'f32le', str(raw)], check=True)
        raw_hash = hashlib.sha256(raw.read_bytes()).hexdigest()
        for mode, instruments in (('all', []), ('conditioned', selected)):
            folder = output/f'{kind}-{mode}'; folder.mkdir()
            notes = folder/'notes.tsv'
            command = [str(engine), str(model), str(raw), str(notes),
                       '--instruments', ','.join(instruments) or 'all']
            started = time.monotonic()
            with (folder/'processing.log').open('w', encoding='utf-8') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
            elapsed = time.monotonic()-started
            with notes.open(encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream, delimiter='\t'))
            labels = Counter(row['instrument'] for row in rows)
            if instruments and set(labels)-set(instruments):
                raise RuntimeError(f'Unexpected conditioned instruments: {labels}')
            result = export(notes, source, raw, folder, f'{kind}-{mode}', 120,
                            folder/'completion.json', instruments)
            summary['runs'].append({'input': str(source.resolve()), 'kind':kind, 'mode':mode,
                                    'raw_sha256':raw_hash, 'seconds':elapsed,
                                    'raw_notes_by_instrument':dict(labels), 'export':result})
            (output/'comparison.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
            print(f'{kind} {mode}: {dict(labels)}; {elapsed:.1f}s', flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--drums', type=Path, required=True)
    parser.add_argument('--bass', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=20)
    args = parser.parse_args()
    if not 0 < args.seconds <= 60:
        parser.error('--seconds must be between 0 and 60')
    compare(args.output, args.drums, args.bass, args.seconds)
