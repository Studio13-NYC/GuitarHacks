"""Local, synchronized previews of audio stems and Standard MIDI files."""
from pathlib import Path
import shutil
import subprocess
import tempfile

import mido
from PySide6.QtCore import QThread, Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

RATE = 44100
MIDI_SUFFIXES = {'.mid', '.midi'}


class PreviewCancelled(Exception):
    pass


def render_midi(source, destination, soundfont, cancelled=lambda: False):
    """Render each file with its own channels, preserving its tempo map and silence."""
    from tinysoundfont import Synth

    midi = mido.MidiFile(source)
    if midi.type == 2:
        raise ValueError('Type 2 MIDI contains independent sequences; export a Type 0 or 1 MIDI file.')
    if not soundfont.is_file():
        raise FileNotFoundError('MIDI preview sound set is missing. Run tools/setup_preview_soundfont.py.')
    synth = Synth(gain=-6, samplerate=RATE)
    font = synth.sfload(str(soundfont))
    try:
        for channel in range(16):
            synth.program_select(channel, font, 0, 0, is_drums=channel == 9)
        frame = 0
        seconds = 0.0
        with destination.open('wb') as output:
            def advance(target):
                nonlocal frame
                while frame < target:
                    if cancelled():
                        raise PreviewCancelled()
                    count = min(4096, target - frame)
                    output.write(synth.generate_simple(count))
                    frame += count

            for message in midi:
                if cancelled():
                    raise PreviewCancelled()
                seconds += message.time
                advance(round(seconds * RATE))
                channel = getattr(message, 'channel', 0)
                if message.type == 'note_on' and message.velocity:
                    synth.noteon(channel, message.note, message.velocity)
                elif message.type in ('note_on', 'note_off'):
                    synth.noteoff(channel, message.note)
                elif message.type == 'program_change':
                    synth.program_change(channel, message.program, is_drums=channel == 9)
                elif message.type == 'control_change':
                    synth.control_change(channel, message.control, message.value)
                elif message.type == 'pitchwheel':
                    synth.pitchbend(channel, message.pitch + 8192)
            for channel in range(16):
                synth.control_change(channel, 64, 0)
            synth.notes_off()
            advance(frame + RATE)  # Keep release tails, without hanging sustained notes.
        return frame
    finally:
        synth.sfunload(font)


def prepare_mix(paths, directory, soundfont, cancelled=lambda: False):
    """One rendered stream gives every checked file the same playback clock."""
    ffmpeg = shutil.which('ffmpeg') or 'C:/Program Files/ffmpeg/bin/ffmpeg.exe'
    if not Path(ffmpeg).is_file():
        raise FileNotFoundError('FFmpeg is required for previews.')
    if not paths:
        raise ValueError('Check at least one audio or MIDI file.')
    arguments = [ffmpeg, '-hide_banner', '-nostdin', '-y', '-loglevel', 'error']
    for index, path in enumerate(paths):
        if cancelled():
            raise PreviewCancelled()
        if not path.is_file():
            raise FileNotFoundError(f'File is no longer available: {path.name}')
        if path.suffix.lower() in MIDI_SUFFIXES:
            rendered = directory / f'midi-{index}.f32'
            render_midi(path, rendered, soundfont, cancelled)
            arguments.extend(['-f', 'f32le', '-ar', str(RATE), '-ac', '2', '-i', str(rendered)])
        else:
            arguments.extend(['-i', str(path)])
    chains = [f'[{index}:a:0]aresample={RATE},asetpts=PTS-STARTPTS[a{index}]' for index in range(len(paths))]
    inputs = ''.join(f'[a{index}]' for index in range(len(paths)))
    # Fixed averaging prevents clipping and gain jumps when shorter files finish.
    mixer = f'amix=inputs={len(paths)}:duration=longest:dropout_transition=0:normalize=0,volume={1 / len(paths)},'
    chains.append(inputs + mixer + 'alimiter=limit=0.95:level=false:latency=true[out]')
    output = directory / 'preview.wav'
    arguments.extend(['-filter_complex', ';'.join(chains), '-map', '[out]',
                      '-ac', '2', '-ar', str(RATE), '-c:a', 'pcm_s16le', str(output)])
    with subprocess.Popen(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as process:
        while True:
            if cancelled():
                process.kill()
                process.communicate()
                raise PreviewCancelled()
            try:
                _, error = process.communicate(timeout=.1)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise RuntimeError(error.decode('utf-8', errors='replace').strip()[-1200:] or 'Could not prepare preview.')
    return output


class PreparePreview(QThread):
    def __init__(self, paths, root, parent):
        super().__init__(parent)
        self.paths, self.root = paths, root
        self.temporary = None
        self.output = None
        self.error = ''

    def run(self):
        try:
            cache = self.root / 'preview-cache'
            cache.mkdir(exist_ok=True)
            self.temporary = tempfile.TemporaryDirectory(prefix='listen-', dir=cache)
            self.output = prepare_mix(self.paths, Path(self.temporary.name),
                                      self.root / 'playback/FluidR3Mono_GM.sf3', self.isInterruptionRequested)
        except PreviewCancelled:
            pass
        except Exception as error:
            self.error = str(error)

    def cleanup(self):
        if self.temporary:
            self.temporary.cleanup()
            self.temporary = None


def time_label(milliseconds):
    seconds = milliseconds // 1000
    return f'{seconds // 60}:{seconds % 60:02d}'


class PreviewPlayer(QWidget):
    """Compact transport shared by audio and MIDI selections."""
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root, self.paths, self.worker = root, [], None
        self.signature = None
        self.preparing = False
        self.want_play = False
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(.7)
        self.player.setAudioOutput(self.audio)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(3)
        controls = QHBoxLayout()
        self.play = QPushButton('▶ Play checked')
        self.play.setAccessibleName('Play checked audio and MIDI files together')
        self.play.setToolTip('Play all checked files together from the beginning. MIDI uses local General MIDI sounds.')
        self.play.clicked.connect(self.toggle)
        controls.addWidget(self.play)
        self.stop_button = QPushButton('■')
        self.stop_button.setAccessibleName('Stop preview')
        self.stop_button.setToolTip('Stop preview')
        self.stop_button.setFixedWidth(36)
        self.stop_button.clicked.connect(self.stop)
        controls.addWidget(self.stop_button)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setAccessibleName('Preview position')
        self.seek.setRange(0, 0)
        self.seek.valueChanged.connect(self.player.setPosition)
        controls.addWidget(self.seek, 1)
        self.clock = QLabel('0:00 / 0:00')
        self.clock.setMinimumWidth(85)
        controls.addWidget(self.clock)
        box.addLayout(controls)
        self.message = QLabel('Check audio or MIDI files to listen. Multiple checks play together.')
        self.message.setStyleSheet('font-size:11px; color:#a9bdb8;')
        self.message.setWordWrap(True)
        box.addWidget(self.message)
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playbackStateChanged.connect(self.update_controls)
        self.player.mediaStatusChanged.connect(self.media_changed)
        self.player.errorOccurred.connect(lambda _, text: self.failed(text))
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        self.update_controls()

    def set_files(self, paths):
        paths = [Path(path) for path in paths]
        if paths != self.paths:
            self.stop()
            self.paths = paths
            self.message.setText('Checked files play together. MIDI uses local instrument sounds.')
        self.update_controls()

    def toggle(self):
        if self.preparing or not self.paths or not self.root:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            return
        if QMediaDevices.defaultAudioOutput().isNull():
            self.failed('No audio output device is available.')
            return
        try:
            signature = [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in self.paths]
        except OSError as error:
            self.failed(str(error))
            return
        if signature == self.signature and not self.player.source().isEmpty():
            if self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self.player.setPosition(0)
            self.message.setText(f'Playing {len(self.paths)} file(s) together · Windows default audio output')
            self.player.play()
            return
        self.release_preview()
        self.signature = signature
        self.preparing = True
        self.want_play = True
        self.message.setText(f'Preparing {len(self.paths)} checked file(s)…')
        self.worker = PreparePreview(list(self.paths), self.root, self)
        self.worker.finished.connect(self.prepared)
        self.worker.start()
        self.update_controls()

    def prepared(self):
        worker = self.worker
        if worker is None:
            return
        self.preparing = False
        if worker.isInterruptionRequested() or not self.want_play:
            self.release_preview()
        elif worker.error:
            self.failed(worker.error)
            self.release_preview()
        elif worker.output:
            self.message.setText(f'Playing {len(worker.paths)} file(s) together · Windows default audio output')
            self.player.setSource(QUrl.fromLocalFile(str(worker.output)))
            self.player.play()
        self.update_controls()

    def stop(self):
        self.want_play = False
        self.player.stop()
        self.player.setPosition(0)
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.message.setText('Stopping preview…')
        else:
            self.message.setText('Stopped · Check files, then press Play checked.')
        self.update_controls()

    def release_preview(self):
        self.player.setSource(QUrl())
        self.signature = None
        if self.worker:
            self.worker.cleanup()
            self.worker.deleteLater()
            self.worker = None

    def update_controls(self, *_):
        state = self.player.playbackState()
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        paused = state == QMediaPlayer.PlaybackState.PausedState
        self.play.setText('Preparing…' if self.preparing else ('Ⅱ Pause' if playing else ('▶ Resume' if paused else f'▶ Play checked ({len(self.paths)})')))
        self.play.setEnabled(bool(self.paths and self.root and not self.preparing))
        self.stop_button.setEnabled(self.preparing or state != QMediaPlayer.PlaybackState.StoppedState)
        self.seek.setEnabled(not self.preparing and self.player.duration() > 0)

    def position_changed(self, value):
        if not self.seek.isSliderDown():
            self.seek.blockSignals(True)
            self.seek.setValue(value)
            self.seek.blockSignals(False)
        self.clock.setText(f'{time_label(value)} / {time_label(self.player.duration())}')

    def duration_changed(self, value):
        self.seek.setRange(0, value)
        self.position_changed(self.player.position())
        self.update_controls()

    def media_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.message.setText('Preview finished · Press Play checked to replay.')

    def failed(self, text):
        self.player.stop()
        self.message.setText('Preview unavailable — ' + text)
        self.update_controls()

    def hideEvent(self, event):
        self.stop()
        super().hideEvent(event)

    def shutdown(self):
        self.stop()
        if self.worker:
            self.worker.wait()
        self.release_preview()
