"""The same local Chord Painter runs inside Qt and as an offline web app."""
import json
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, QUrl, QSaveFile, QIODevice
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile


class PainterBridge(QObject):
    leave = Signal()
    error = Signal(str)
    suspend = Signal()
    listening = Signal(str)
    voiceStatus = Signal(str)
    voiceCommand = Signal(str)
    reviewReady = Signal(str, str)

    def __init__(self, data_dir, parent=None):
        super().__init__(parent)
        self.path = Path(data_dir) / 'chord-painter.json'
        self.listener = None
        self.coach = None
        self._saved_raw = None

    @Slot(str, str)
    def reviewPractice(self, token, raw):
        if self.coach is None:
            from painter_coach import PracticeCoach
            self.coach = PracticeCoach(self)
            self.coach.ready.connect(self.reviewReady)
        self.coach.review(token, raw)

    @Slot()
    def cancelReview(self):
        if self.coach: self.coach.cancel()

    @Slot()
    def listenStart(self):
        if self.listener: self.listener.start()

    @Slot()
    def listenBegin(self):
        if self.listener: self.listener.begin()

    @Slot(int, int)
    def listenCheck(self, string, fret):
        if self.listener: self.listener.check(string, fret)

    @Slot()
    def listenHelp(self):
        if self.listener: self.listener.help()

    @Slot()
    def listenStop(self):
        if self.listener: self.listener.stop()

    @Slot()
    def listenRetry(self):
        if self.listener: self.listener.retry()

    @Slot()
    def listenMuted(self):
        if self.listener: self.listener.muted()

    @Slot(result=str)
    def load(self):
        if not self.path.exists():
            return ''
        try:
            self._saved_raw = self.path.read_text(encoding='utf-8')
            return self._saved_raw
        except OSError as exc:
            logging.exception('Chord Painter load failed')
            self.error.emit(f'Could not load saved Chord Painter practice: {exc}')
            # Invalid JSON tells the view not to overwrite an unreadable file.
            return '!load failed'

    @Slot(str)
    def save(self, raw):
        try:
            value = json.loads(raw)
            if value.get('version') != 1 or not isinstance(value.get('history'), list) or not isinstance(value.get('stats'), dict):
                raise ValueError('Invalid practice data')
            if self._saved_raw is not None:
                if not self.path.exists():
                    raise ValueError('Practice file was deleted or moved. Close and reopen Chord Painter to start fresh; the file has not been recreated.')
                if self.path.read_text(encoding='utf-8') != self._saved_raw:
                    raise ValueError('Practice file changed outside this window. Close and reopen Chord Painter to load it.')
            elif self.path.exists():
                raise ValueError('A practice file was created by another window. Close and reopen Chord Painter to load it.')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            target = QSaveFile(str(self.path))
            encoded = raw.encode('utf-8')
            if not target.open(QIODevice.OpenModeFlag.WriteOnly):
                raise OSError(target.errorString())
            if target.write(encoded) != len(encoded) or not target.commit():
                raise OSError(target.errorString())
            self._saved_raw = raw
        except (OSError, ValueError) as exc:
            logging.exception('Chord Painter save failed')
            self.error.emit(f'Could not save Chord Painter practice: {exc}')

    @Slot()
    def back(self):
        self.suspend.emit()
        self.leave.emit()


class PainterPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        logging.info('Chord Painter JS %s %s:%s %s', level, source, line, message)

    def acceptNavigationRequest(self, url, kind, main_frame):
        return url.scheme() in ('file', 'qrc', 'about', 'data')


class PainterView(QWidget):
    def __init__(self, data_dir, assets, parent=None, settings=None, capture_factory=None, available=lambda: True, voice_factory=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.web = QWebEngineView(self)
        self.profile = QWebEngineProfile(self)
        self.page = PainterPage(self.profile, self.web)
        self.web.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.bridge = PainterBridge(data_dir, self.channel)
        from chord_listening import ChordListener
        from audio import Capture
        from voice_commands import VoiceCommands
        self.listener = ChordListener(settings or (lambda: {}), capture_factory or Capture, available, self,
                                      VoiceCommands if voice_factory is None else (voice_factory or None))
        self.bridge.listener = self.listener
        self.listener.changed.connect(self.bridge.listening)
        self.listener.voice_status.connect(self.bridge.voiceStatus)
        self.listener.command.connect(self.bridge.voiceCommand)
        self.bridge.suspend.connect(self.listener.stop)
        self.channel.registerObject('painter', self.bridge)
        self.page.setWebChannel(self.channel)
        layout.addWidget(self.web)
        self.web.setUrl(QUrl.fromLocalFile(str(Path(assets) / 'chord_painter' / 'index.html')))

    def hideEvent(self, event):
        self.bridge.cancelReview()
        self.bridge.suspend.emit()
        super().hideEvent(event)

    def shutdown(self):
        self.bridge.cancelReview()
        self.bridge.suspend.emit()
        if not self.listener.shutdown(): return False
        # Qt requires pages to go away before their profile.
        self.web.setPage(None)
        self.page.deleteLater()
        return True
