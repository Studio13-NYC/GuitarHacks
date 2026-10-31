"""Local Jam recording via the installed Windows MIDI Services SDK."""
from datetime import datetime
from pathlib import Path
import logging
import os
import subprocess
import time
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QPushButton, QComboBox, QSpinBox
from jam_midi import MidiTake, decode_ump, note_name
from windows_midi import WindowsMidiInput
from lab_ui import LabPage, caption, MINT, INK

JAM_EXE = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Jam Origin/MIDI Guitar 3/MIDI Guitar 3.exe'


class JamPage(LabPage):
    def __init__(self, store, home_callback):
        super().__init__('Record with Jam', 'Play it.\nKeep it.',
                         'Capture your notes and chords. Refine the score in Guitar Pro.', home_callback)
        self.store = store
        self.directory = store.directory / 'recordings'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.port = self.take = self.pending_save = self.pending_command = None
        self.connection = {}
        self.last_timestamp = 0
        self.held = set()
        self.closing = False
        self.failure = None
        self.setup_events = []
        self.setup_truncated = False
        self.eyebrow.setText('LISTEN. RECORD. REFINE.')
        self.foot.setText('Saved locally. Jam trial interruptions may leave gaps. No automatic practice grading.')
        self.status = caption('Connect MIDI, then choose GuitarHacks Jam Send as Jam’s MIDI output.', 16, MINT)
        self.work.addWidget(self.status)
        self.live = caption('—', 46, INK, True)
        self.work.addWidget(self.live)
        self.count = caption('Ready for a new take.', 16)
        self.work.addWidget(self.count)
        self.work.addWidget(caption('Mute the strings before recording. The MIDI file keeps your timing; refine rhythm and fingering in Guitar Pro.', 14))
        self.work.addStretch()
        self.work.addWidget(caption('SAVED TAKES', 11, MINT, True))
        self.takes = QComboBox()
        self.takes.setMinimumHeight(44)
        self.work.addWidget(self.takes)
        self.open_gp = QPushButton('Copy take path and open Guitar Pro')
        self.open_gp.clicked.connect(self.open_in_guitar_pro)
        self.work.addWidget(self.open_gp)
        self.folder_button = QPushButton('Open recordings folder')
        self.folder_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.directory))))
        self.work.addWidget(self.folder_button)
        self.work.addWidget(caption('Each take includes a MIDI file and its original timestamped data. MIDI cannot prove which guitar string you played.', 13))
        self.jam_button = QPushButton('Open Jam')
        self.jam_button.clicked.connect(self.launch_jam)
        self.control_box.addWidget(self.jam_button)
        self.control_box.addWidget(caption('Jam MIDI output\nGuitarHacks Jam Send', 14))
        self.connect_button = QPushButton('Connect MIDI')
        self.connect_button.clicked.connect(self.toggle_connection)
        self.control_box.addWidget(self.connect_button)
        self.control_box.addWidget(caption('Recording tempo · BPM', 12))
        self.bpm = QSpinBox()
        self.bpm.setRange(30, 300)
        self.bpm.setValue(int(store.settings().get('jam_bpm', 120)))
        self.control_box.addWidget(self.bpm)
        self.record_button = QPushButton('Record take')
        self.record_button.setObjectName('primary')
        self.record_button.setEnabled(False)
        self.record_button.clicked.connect(self.toggle_recording)
        self.control_box.addWidget(self.record_button)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll)
        self.refresh_takes()

    def refresh_takes(self, selected=None):
        current = selected or self.takes.currentData()
        self.takes.clear()
        for path in sorted(self.directory.glob('*.mid'), reverse=True):
            self.takes.addItem(path.stem, str(path))
        index = self.takes.findData(str(current))
        if index >= 0:
            self.takes.setCurrentIndex(index)
        self.open_gp.setEnabled(self.takes.count() > 0)

    def launch_jam(self):
        try:
            if not JAM_EXE.is_file():
                raise FileNotFoundError('Install Jam Origin MIDI Guitar 3 first.')
            subprocess.Popen([str(JAM_EXE)])
            self.status.setText('In Jam, choose MIDI Output → GuitarHacks Jam Send. Use your guitar input on channel 5.')
        except OSError as error:
            self.status.setText(str(error))

    def toggle_connection(self):
        if self.port:
            self.disconnect()
            return
        self.failure = None
        self.connection = {}
        self.setup_events.clear()
        self.setup_truncated = False
        self.last_timestamp = 0
        self.port = WindowsMidiInput(self)
        self.port.event.connect(self.receive_event)
        self.port.failed.connect(self.input_failed)
        self.connect_button.setEnabled(False)
        self.status.setText('Connecting to Windows MIDI Services…')
        self.port.start()

    def receive_event(self, event):
        kind = event['type']
        timestamp = event.get('timestamp', self.last_timestamp)
        self.last_timestamp = max(self.last_timestamp, timestamp)
        if kind == 'ready':
            if not event.get('frequency'):
                self.input_failed('MIDI service returned an invalid clock frequency.')
                return
            self.connection = event
            self.connect_button.setEnabled(True)
            self.connect_button.setText('Disconnect MIDI')
            self.record_button.setEnabled(True)
            self.status.setText('MIDI connected. In Jam, select GuitarHacks Jam Send and play a note.')
            self.timer.start()
        elif kind == 'start' and self.pending_command == 'start':
            self.take = MidiTake(self.bpm.value(), clock=lambda: timestamp / self.connection['frequency'])
            self.take.metadata = dict(self.connection, startTimestamp=timestamp,
                                      source='Selected Jam MIDI port; audio source not verified', timeSignature=[4, 4])
            for setup in self.setup_events:
                self.capture_event(setup, initial=True)
            if self.setup_truncated:
                self.take.warnings.add('Earlier controller setup exceeded the cache; reselect the Jam patch after connecting to capture complete initialization.')
            self.take.warnings.add('Only controller setup received since connecting is available. Guitar Pro interpretation of MPE/bends requires review.')
            self.pending_command = None
            self.record_started = time.perf_counter()
            self.record_button.setText('Stop and save')
            self.record_button.setEnabled(True)
            self.status.setText('Recording notes locally…')
        elif kind == 'stop':
            self.finish_take(timestamp)
        elif kind == 'midi':
            try:
                group, message, warning = decode_ump(event['words'])
            except (ValueError, IndexError, TypeError) as error:
                self.input_failed(f'Invalid MIDI packet: {error}')
                return
            if message and message.type in ('note_on', 'note_off'):
                key = (group, message.channel, message.note)
                if message.type == 'note_on' and message.velocity:
                    self.held.add(key)
                else:
                    self.held.discard(key)
                self.update_live()
                if not self.take and not self.pending_command:
                    self.status.setText('Receiving MIDI notes. Ready to record.')
            elif message and message.type == 'control_change' and message.control in (120, 123):
                self.held = {k for k in self.held if k[:2] != (group, message.channel)}
                self.update_live()
            if message and message.type in ('control_change', 'pitchwheel', 'aftertouch'):
                self.setup_events.append(event.copy())
                if len(self.setup_events) > 4096:
                    self.setup_events.pop(0)
                    self.setup_truncated = True
            if self.take and timestamp >= self.take.metadata['startTimestamp']:
                self.capture_event(event)
                if len(self.take.raw) >= 250000 and not self.pending_command:
                    self.take.warnings.add('Event limit reached; recording stopped.')
                    self.toggle_recording()

    def capture_event(self, event, initial=False):
        raw = dict(event)
        if initial:
            raw['initialState'] = True
        self.take.raw.append(raw)
        group, message, warning = decode_ump(event['words'])
        if warning:
            self.take.warnings.add(warning)
        if message:
            seconds = self.take.started if initial else event['timestamp'] / self.connection['frequency']
            self.take.feed(message, seconds, group)

    def update_live(self):
        self.live.setText('  '.join(note_name(n) for n in sorted({k[2] for k in self.held})) or '—')

    def poll(self):
        if self.take:
            seconds = time.perf_counter() - self.record_started
            self.count.setText(f'{int(seconds)//60}:{int(seconds)%60:02d}  ·  {len(self.take.notes)} notes captured')
            if seconds >= 1200 and not self.pending_command:
                self.toggle_recording()

    def toggle_recording(self):
        if self.pending_save:
            self.save_pending()
        elif self.port and self.connection and not self.pending_command:
            self.pending_command = 'stop' if self.take else 'start'
            self.record_button.setEnabled(False)
            self.bpm.setEnabled(False)
            self.store.set_settings({'jam_bpm': self.bpm.value()})
            self.port.send(self.pending_command)

    def finish_take(self, timestamp):
        self.pending_command = None
        self.bpm.setEnabled(True)
        if self.pending_save and not self.take:
            self.record_button.setText('Retry save')
            self.record_button.setEnabled(True)
            return
        self.record_button.setText('Record take')
        self.record_button.setEnabled(bool(self.port and self.connection))
        if not self.take:
            return
        self.take.stop(timestamp / self.connection['frequency'])
        self.take.metadata['stopTimestamp'] = timestamp
        take, self.take = self.take, None
        if not take.notes and not take.raw:
            self.status.setText('No notes received. Check Jam’s MIDI output and trial prompt.')
            return
        self.count.setText(f'{take.duration:.1f} seconds  ·  {len(take.notes)} notes captured')
        path = self.directory / (datetime.now().strftime('Take-%Y%m%d-%H%M%S-%f') + '.mid')
        self.pending_save = (take, path)
        self.save_pending()

    def save_pending(self):
        if not self.pending_save:
            return
        take, path = self.pending_save
        try:
            original = path.with_suffix('.ump.json')
            original_tmp = original.with_suffix('.json.tmp')
            temporary = path.with_suffix('.mid.tmp')
            take.save_original(original_tmp)
            take.save(temporary)
            original_tmp.replace(original)
            temporary.replace(path)
            self.pending_save = None
            self.refresh_takes(path)
            self.status.setText(f'Saved {len(take.notes)} notes and original data. Review rhythm and expression in Guitar Pro.')
            self.record_button.setText('Record take')
            self.record_button.setEnabled(bool(self.port and self.connection))
        except (OSError, ValueError) as error:
            logging.exception('Could not save Jam take')
            self.status.setText(f'Take remains in memory. Retry save: {error}')
            self.record_button.setText('Retry save')
            self.record_button.setEnabled(True)

    def input_failed(self, reason):
        if self.closing or self.failure:
            return
        self.failure = reason
        if self.take:
            self.take.warnings.add('Incomplete take: ' + reason)
        QTimer.singleShot(0, self.disconnect)

    def disconnect(self):
        if self.closing:
            return
        self.closing = True
        if self.port:
            self.port.close()
            self.port.deleteLater()
            self.port = None
        if self.take:
            self.take.warnings.add('Receiver ended without a stop timestamp; take ends at the last received event.')
            self.finish_take(self.last_timestamp)
        self.pending_command = None
        self.connection = {}
        self.timer.stop()
        self.held.clear()
        self.update_live()
        self.connect_button.setText('Connect MIDI')
        self.connect_button.setEnabled(True)
        self.record_button.setEnabled(self.pending_save is not None)
        self.bpm.setEnabled(True)
        if not self.pending_save:
            self.status.setText(self.failure or 'Disconnected. Your saved takes are below.')
        self.closing = False

    def open_in_guitar_pro(self):
        path = self.takes.currentData()
        if not path:
            return
        QApplication.clipboard().setText(str(Path(path).resolve()))
        base = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Arobas Music/Guitar Pro 8'
        executable = next((base/name for name in ('GuitarPro.exe', 'GuitarPro8.exe') if (base/name).is_file()), None)
        if executable:
            try:
                subprocess.Popen([str(executable)])
                self.status.setText('Path copied. In Guitar Pro: File → Import → MIDI, paste the path, then review quantization and import.')
            except OSError as error:
                self.status.setText(f'Could not open Guitar Pro: {error}')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.directory)))
            self.status.setText('Path copied. In Guitar Pro: File → Import → MIDI, then paste the path.')
