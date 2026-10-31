"""Local MIDI take capture; original timing and expression remain in the export."""
from dataclasses import dataclass
from pathlib import Path
import time
import json
import mido


PORT_NAME = 'GuitarHacks Jam Receive'


def resolve_port(names, saved=''):
    """WinMM appends an unstable device index; match only our exact cable name."""
    if saved in names:
        return saved
    matches = [name for name in names if name == PORT_NAME or
               (name.startswith(PORT_NAME + ' ') and name[len(PORT_NAME)+1:].isdigit())]
    return matches[0] if len(matches) == 1 and (not saved or saved.startswith(PORT_NAME)) else None


def note_name(note):
    return ('C', 'C♯', 'D', 'E♭', 'E', 'F', 'F♯', 'G', 'A♭', 'A', 'B♭', 'B')[note % 12] + str(note // 12 - 1)


@dataclass
class PlayedNote:
    note: int
    channel: int
    start: float
    duration: float = 0.0
    group: int = 0


def decode_ump(words):
    """Return group, MIDI-file-compatible message, explicit export limitation.

    Raw UMP words are retained separately. This conversion never asserts that
    MIDI 1.0 export preserves MIDI 2.0 precision or per-note expression.
    """
    first = words[0]
    kind, group = first >> 28, (first >> 24) & 15
    status, index, value = (first >> 16) & 255, (first >> 8) & 127, first & 127
    if kind == 2:
        data = [status, index] if status >> 4 in (12, 13) else [status, index, value]
        return group, mido.Message.from_bytes(data), None
    if kind != 4:
        return group, None, None if kind in (0, 1, 15) else 'SysEx/data packets are retained in the original-data file only.'
    if len(words) != 2:
        raise ValueError('MIDI 2.0 channel message requires two words')
    high, channel, second = status >> 4, status & 15, words[1]
    limitation = 'MIDI 2.0 resolution is reduced in MIDI export; original UMP is preserved.'
    if high in (8, 9):
        velocity = round((second >> 16) * 127 / 65535)
        if high == 9:
            velocity = max(1, velocity)  # MIDI 2 note-on velocity zero is still note-on.
        message = mido.Message('note_on' if high == 9 else 'note_off', channel=channel, note=index, velocity=velocity)
        if first & 255:
            limitation += ' Note attributes are not represented in the MIDI file.'
    elif high == 10:
        message = mido.Message('polytouch', channel=channel, note=index, value=round(second * 127 / 0xffffffff))
    elif high == 11:
        message = mido.Message('control_change', channel=channel, control=index, value=round(second * 127 / 0xffffffff))
    elif high == 13:
        message = mido.Message('aftertouch', channel=channel, value=round(second * 127 / 0xffffffff))
    elif high == 14:
        message = mido.Message('pitchwheel', channel=channel, pitch=(second >> 18) - 8192)
    else:
        return group, None, 'Unsupported MIDI 2.0 expression is retained in the original-data file only.'
    return group, message, limitation


class MidiTake:
    def __init__(self, bpm=120, clock=time.perf_counter):
        self.bpm = bpm
        self.clock = clock
        self.started = clock()
        self.events = []
        self.notes = []
        self.active = {}
        self.duration = 0.0
        self.stopped = False
        self.raw = []
        self.warnings = set()
        self.metadata = {}

    def feed(self, message, timestamp=None, group=0):
        if self.stopped or message.type not in ('note_on', 'note_off', 'pitchwheel', 'control_change', 'aftertouch', 'polytouch'):
            return
        elapsed = max(0.0, (self.clock() if timestamp is None else timestamp) - self.started)
        if elapsed < self.duration:
            self.warnings.add('Out-of-order source timestamp; note view uses arrival order. Original timestamps are retained.')
            elapsed = self.duration
        self.events.append((elapsed, group, message.copy(time=0)))
        self.duration = elapsed
        if message.type in ('note_on', 'note_off'):
            key = (group, message.channel, message.note)
            if key in self.active:
                previous = self.active.pop(key)
                previous.duration = elapsed - previous.start
            if message.type == 'note_on' and message.velocity:
                note = PlayedNote(message.note, message.channel, elapsed, group=group)
                self.notes.append(note)
                self.active[key] = note
        elif message.type == 'control_change' and message.control in (120, 123):
            for key, note in list(self.active.items()):
                if key[:2] == (group, message.channel):
                    note.duration = elapsed - note.start
                    del self.active[key]

    def stop(self, timestamp=None):
        if self.stopped:
            return
        end = max(self.duration, (self.clock() if timestamp is None else timestamp) - self.started)
        for (group, channel, pitch), note in list(self.active.items()):
            note.duration = end - note.start
            self.events.append((end, group, mido.Message('note_off', channel=channel, note=pitch, velocity=0)))
        # Release sustain in exported playback even when recording stopped mid-pedal.
        for group, channel in sorted({(g, m.channel) for _, g, m in self.events}):
            self.events.append((end, group, mido.Message('control_change', channel=channel, control=64, value=0)))
        self.active.clear()
        self.duration = end
        self.stopped = True

    def save(self, path):
        if not self.stopped:
            raise ValueError('Stop the take before saving.')
        tempo = mido.bpm2tempo(self.bpm)
        midi = mido.MidiFile(type=1, ticks_per_beat=480)
        meta = mido.MidiTrack()
        meta.extend([mido.MetaMessage('track_name', name='GuitarHacks take'),
                     mido.MetaMessage('set_tempo', tempo=tempo),
                     mido.MetaMessage('time_signature', numerator=4, denominator=4)])
        midi.tracks.append(meta)
        for group in sorted({g for _, g, _ in self.events}):
            track = mido.MidiTrack([mido.MetaMessage('track_name', name=f'Guitar - group {group + 1}')])
            for channel in sorted({m.channel for _, g, m in self.events if g == group}):
                track.append(mido.Message('program_change', channel=channel, program=27))
            previous = 0
            for seconds, event_group, message in self.events:
                if group != event_group:
                    continue
                tick = max(previous, round(mido.second2tick(seconds, 480, tempo)))
                track.append(message.copy(time=tick - previous))
                previous = tick
            track.append(mido.MetaMessage('end_of_track', time=max(0, round(mido.second2tick(self.duration, 480, tempo))-previous)))
            midi.tracks.append(track)
        midi.save(str(Path(path)))

    def save_original(self, path):
        payload = dict(format='GuitarHacks UMP take', version=1, bpm=self.bpm,
                       duration=self.duration, metadata=self.metadata,
                       warnings=sorted(self.warnings), events=self.raw)
        Path(path).write_text(json.dumps(payload, indent=2), encoding='utf-8')
