"""Qt process adapter for the version-matched Windows MIDI Services receiver."""
import json
from pathlib import Path
import sys
from PySide6.QtCore import QObject, QProcess, QTimer, Signal


class WindowsMidiInput(QObject):
    event = Signal(dict)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).parent
        self.root = root / ('windows-midi' if getattr(sys, 'frozen', False) else 'tools/windows-midi/publish')
        self.process = QProcess(self)
        self.buffer = bytearray()
        self.closing = False
        self.ready = False
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.error)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.setInterval(15000)
        self.timeout.timeout.connect(lambda: self.failed.emit('MIDI connection timed out. Check Windows MIDI Services.'))

    def start(self):
        executable = self.root / 'GuitarHacks.Midi.exe'
        if not executable.is_file():
            self.failed.emit('The Windows MIDI receiver is missing. Rebuild GuitarHacks with its MIDI companion.')
            return
        self.timeout.start()
        self.process.start(str(executable), [str(self.root / 'loopback.json')])

    def send(self, command):
        if self.process.state() != QProcess.ProcessState.Running:
            self.failed.emit('Windows MIDI receiver is not running.')
            return
        self.process.write((command + '\n').encode('ascii'))

    def read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        if len(self.buffer) > 4 * 1024 * 1024:
            self.buffer.clear()
            self.failed.emit('MIDI input overflow. The partial take needs review.')
            return
        while b'\n' in self.buffer:
            line, _, rest = self.buffer.partition(b'\n')
            self.buffer = bytearray(rest)
            try:
                event = json.loads(line)
                if not isinstance(event, dict) or 'type' not in event:
                    raise ValueError('missing event type')
                if event['type'] == 'ready':
                    self.ready = True
                    self.timeout.stop()
                if event['type'] == 'error':
                    self.failed.emit(event.get('message', 'MIDI receiver error'))
                else:
                    self.event.emit(event)
            except (ValueError, TypeError) as error:
                self.failed.emit(f'Invalid MIDI receiver data: {error}')
                return

    def error(self, error):
        if not self.closing:
            self.timeout.stop()
            self.failed.emit(self.process.errorString())

    def finished(self, code, status):
        self.timeout.stop()
        self.read()
        if not self.closing:
            detail = bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace')[-1000:]
            self.failed.emit(f'MIDI receiver stopped ({code}). {detail}'.strip())

    def close(self):
        self.closing = True
        self.timeout.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.write(b'stop\nquit\n')
            if not self.process.waitForFinished(2000):
                self.process.kill()  # Only the helper this instance owns.
                self.process.waitForFinished(1000)
            self.read()

