"""Write a standard multitrack MIDI file from local MuScriptor note events."""
import argparse
import csv
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import uuid

import mido


def make_midi(rows, bpm, duration):
    if not 20 <= bpm <= 300 or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid tempo or audio duration')
    tempo = mido.bpm2tempo(bpm)
    midi = mido.MidiFile(type=1, ticks_per_beat=960)
    conductor = mido.MidiTrack()
    midi.tracks.append(conductor)
    conductor.append(mido.MetaMessage('track_name', name='Tempo'))
    conductor.append(mido.MetaMessage('set_tempo', tempo=tempo))
    ticks = lambda seconds: round(mido.second2tick(seconds, midi.ticks_per_beat, tempo))
    conductor.append(mido.MetaMessage('end_of_track', time=ticks(duration)))
    groups = defaultdict(list)
    for row in rows:
        start, end = float(row['onset']), float(row['offset'])
        pitch, program, drum = int(row['pitch']), int(row['program']), bool(int(row['is_drum']))
        if not all(map(math.isfinite, (start, end))) or not 0 <= pitch <= 127 or not 0 <= program <= 128:
            raise ValueError('Invalid model note event')
        start, end = max(0, start), min(duration, end)
        if end <= start:
            continue
        groups[(drum, program, row['instrument'])].append((ticks(start), max(ticks(start)+1, ticks(end)), pitch))
    channels = [channel for channel in range(16) if channel != 9]
    melodic = 0
    count = 0
    for (drum, program, label), notes in sorted(groups.items()):
        port, channel = (0, 9) if drum else (melodic // 15, channels[melodic % 15])
        if not drum:
            melodic += 1
        track = mido.MidiTrack()
        midi.tracks.append(track)
        track.append(mido.MetaMessage('track_name', name=label.replace('_', ' ').title()))
        track.append(mido.MetaMessage('midi_port', port=port))
        if not drum:
            if program > 127:
                raise ValueError('Invalid melodic program')
            track.append(mido.Message('program_change', channel=channel, program=program))
        events = []
        for start, end, pitch in notes:
            events.extend([(start, 1, pitch), (end, 0, pitch)])
        previous = 0
        for tick, on, pitch in sorted(events):
            track.append(mido.Message('note_on' if on else 'note_off', channel=channel,
                                      note=pitch, velocity=96 if on else 0, time=tick-previous))
            previous = tick
        track.append(mido.MetaMessage('end_of_track', time=max(0, ticks(duration)-previous)))
        count += len(notes)
    return midi, count, len(groups)


def export(notes, audio, raw, directory, basename, bpm, completion, instruments=None):
    settings = {}
    settings_path = notes.with_suffix('.settings.json')
    if settings_path.is_file():
        settings = json.loads(settings_path.read_text(encoding='utf-8'))
        if (not isinstance(settings, dict) or not isinstance(settings.get('instruments'), list)
                or not all(isinstance(name, str) and name for name in settings['instruments'])
                or settings.get('decoder') != 'greedy' or settings.get('prelude_forcing') is not True):
            raise ValueError('Invalid native transcription settings')
        with notes.open('rb') as stream:
            notes_sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
        if settings.get('notes_sha256') != notes_sha256:
            raise ValueError('Native transcription settings do not match the note events')
        settings = {key: settings[key] for key in ('instruments', 'decoder', 'prelude_forcing', 'notes_sha256')}
    if instruments is not None and (not settings or settings['instruments'] != list(dict.fromkeys(instruments))):
        raise ValueError('Native transcription settings do not match the requested instruments')
    directory.mkdir(parents=True, exist_ok=True)
    if Path(basename).name != basename or not basename or basename in ('.', '..'):
        raise ValueError('Invalid MIDI filename')
    with notes.open(encoding='utf-8') as stream:
        midi, count, tracks = make_midi(csv.DictReader(stream, delimiter='\t'), bpm, raw.stat().st_size / 64000)
    if not count:
        raise ValueError('No notes detected. Try a clearer recording or a different stem.')
    token = uuid.uuid4().hex
    temporary = directory / f'.midi-{token}.tmp'
    target = None
    manifest = directory / f'midi-manifest-{token}.json'
    try:
        midi.save(temporary)
        checked = mido.MidiFile(temporary)
        if sum(msg.type == 'note_on' and msg.velocity > 0 for track in checked.tracks for msg in track) != count:
            raise ValueError('MIDI verification failed')
        index = 1
        while True:
            candidate = directory / f'{basename}{"" if index == 1 else "-"+str(index)}.mid'
            try:
                os.link(temporary, candidate)  # Atomic, never overwrite an existing performance.
                target = candidate
                break
            except FileExistsError:
                index += 1
        result = {'files': [target.name], 'note_count': count, 'track_count': tracks, 'bpm': bpm,
                  'source': str(audio.resolve()), 'duration_seconds': raw.stat().st_size / 64000,
                  'model': 'muscriptor-large-f16.gguf', 'velocity': 96,
                  **settings,
                  'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
        manifest.write_text(json.dumps(result, indent=2), encoding='utf-8')
        completion.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f'Saved {target}: {count} notes in {tracks} instrument tracks', flush=True)
        return result
    except Exception:
        if target:
            target.unlink(missing_ok=True)
        manifest.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('notes', type=Path)
    parser.add_argument('audio', type=Path)
    parser.add_argument('raw', type=Path)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--name', required=True)
    parser.add_argument('--bpm', type=float, default=120)
    parser.add_argument('--completion', type=Path, required=True)
    parser.add_argument('--instruments')
    args = parser.parse_args()
    instruments = None if args.instruments is None else ([] if args.instruments == 'all' else args.instruments.split(','))
    export(args.notes, args.audio, args.raw, args.directory, args.name, args.bpm, args.completion, instruments)
