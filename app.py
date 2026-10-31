"""Windows practice home, audio exercises, and the embedded Chord Painter."""
from __future__ import annotations
import argparse
import logging
import math
from pathlib import Path
import shutil
import sys
import time
from collections import deque
from PySide6.QtCore import Qt, QTimer, QUrl, QSize, Signal
from PySide6.QtGui import QFont, QFontMetrics, QKeySequence, QShortcut, QDesktopServices, QColor, QPalette, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QComboBox, QSpinBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDialogButtonBox, QProgressBar, QMessageBox, QSizePolicy, QCheckBox, QStackedWidget, QButtonGroup, QRadioButton, QGraphicsDropShadowEffect, QGridLayout)
from audio import Capture, input_devices, DEFAULT_GATE_DB
from calibration import Calibration
from detection_help import DetectionHelp, LiveHearing
from cues import CuePlayer
from lessons import load_lessons
from practice import Store
from session import Session
from everywhere import EverywhereSession
from fretboard import Fretboard
from exercises import MODES, NOTES, STRINGS, make_exercise
from home_view import HomePage
from lab_ui import LabPage, caption, MINT, INK, GOLD

STYLE = """
QWidget { background:#121b1f; color:#f4f2e9; font-family:'Segoe UI'; }
QLabel { background:transparent; }
QPushButton { background:#243237; border:1px solid #43534f; border-radius:10px; padding:12px 16px; font-size:14px; }
QPushButton:hover { background:#30444b; }
QPushButton:focus, QComboBox:focus { border:2px solid #a6dac2; }
QPushButton:disabled { color:#71817c; border-color:#2a383d; }
QPushButton#primary { background:#a6dac2; color:#10251c; font-weight:600; }
QPushButton#quiet { background:transparent; color:#b0bcb7; font-size:12px; padding:10px 12px; }
QComboBox, QSpinBox { background:#122024; border:1px solid #43534f; border-radius:8px; padding:9px; font-size:14px; }
QComboBox QAbstractItemView { background:#243239; selection-background-color:#3b5c50; }
QRadioButton::indicator { width:22px; height:22px; border:2px solid #a7b8b1; border-radius:12px; background:#141b20; }
QRadioButton::indicator:checked { border:2px solid #a6dac2; background:#a6dac2; }
QRadioButton::indicator:disabled { border-color:#42545c; background:#243239; }
QSpinBox { font-size:20px; }
QProgressBar { border:0; background:#2a373b; border-radius:3px; max-height:6px; }
QProgressBar::chunk { background:#a6dac2; border-radius:3px; }
QToolTip { background:#edf3ef; color:#141b20; }
"""


def apply_theme(app):
    app.setStyle('Fusion')
    palette=QPalette()
    for role in (QPalette.ColorRole.WindowText,QPalette.ColorRole.Text,QPalette.ColorRole.ButtonText):
        palette.setColor(role,QColor('#edf3ef'))
    for role in (QPalette.ColorRole.Window,QPalette.ColorRole.Base,QPalette.ColorRole.Button):
        palette.setColor(role,QColor('#202d33'))
    palette.setColor(QPalette.ColorRole.Highlight,QColor('#a6dac2'))
    palette.setColor(QPalette.ColorRole.HighlightedText,QColor('#10251c'))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)


def text_label(text="", color="#a7b8b1"):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{color}; font-size:16px;")
    return label


class FitLabel(QLabel):
    """Fit words to the available area, including when maximized."""
    def __init__(self, maximum, minimum=18, bold=False):
        super().__init__()
        self.maximum, self.minimum, self.bold = maximum, minimum, bold
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(minimum+16)

    def minimumSizeHint(self):
        return QSize(0, self.minimum+16)

    def sizeHint(self):
        return QSize(100,self.minimum+16)

    def heightForWidth(self,width):
        # The font follows the space allocated by the layout, not vice versa.
        # QLabel's default would grow a scroll page to fit the previous font.
        return self.minimum+16

    def setText(self, text):
        super().setText(text)
        self.fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def fit(self):
        area = self.contentsRect().adjusted(12, 5, -12, -5)
        flags = Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter
        for size in range(self.maximum, self.minimum-1, -2):
            font = QFont("Segoe UI")
            font.setPixelSize(size)
            font.setBold(self.bold)
            bounds = QFontMetrics(font).boundingRect(area, flags, self.text())
            if bounds.width() <= area.width() and bounds.height() <= area.height():
                break
        self.setFont(font)


class SettingsPanel(QWidget):
    finished=Signal(bool)

    def __init__(self, settings, lesson_dir, parent=None):
        super().__init__(parent)
        self.selected = settings
        box = QVBoxLayout(self)
        box.setSpacing(18)
        box.addWidget(text_label("Connect once. Every lesson uses this input.", "#edf3ef"))
        self.device = QComboBox()
        self.device.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.device.setMinimumContentsLength(20)
        self.channel = QComboBox()
        self.gate = QSpinBox()
        self.gate.setRange(-75, -15)
        self.gate.setSuffix(" dBFS")
        self.gate.setValue(settings.get("gate", DEFAULT_GATE_DB))
        form = QFormLayout()
        form.addRow("Guitar input", self.device)
        form.addRow("Channel", self.channel)
        form.addRow("Minimum note volume", self.gate)
        self.gate.setToolTip("Less negative means less sensitive: -30 ignores more quiet sound than -40. Setup can raise this above the background.")
        box.addLayout(form)
        self.cues = QCheckBox("Gentle sound between steps")
        self.cues.setChecked(settings.get("cues", True))
        box.addWidget(self.cues)
        self.message = text_label()
        box.addWidget(self.message)
        self.device.currentIndexChanged.connect(self.channels)
        refresh = QPushButton("Refresh inputs")
        refresh.clicked.connect(self.refresh)
        box.addWidget(refresh)
        box.addWidget(text_label("For the Model 12 main mix, select M12 In 11/12 – Main Mix. "
                                 "Use Main mix left with the guitar panned center. "
                                 "Pick one clean note and mute briefly between answers. "
                                 "A microphone can be selected here too."))
        open_lessons = QPushButton("Open lesson folder")
        open_lessons.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(lesson_dir))))
        box.addWidget(open_lessons)
        box.addWidget(text_label("Add a lesson JSON file there, then close this panel to reload lessons."))
        box.addStretch()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        box.addWidget(self.buttons)
        self.refresh()

    def accept(self):
        self.finished.emit(True)

    def reject(self):
        self.finished.emit(False)

    def refresh(self):
        previous = self.device.currentData()
        name = previous["name"] if previous else self.selected.get("input")
        self.device.blockSignals(True)
        self.device.clear()
        try:
            devices = input_devices()
            for device in devices:
                self.device.addItem(device["name"], device)
            index = next((i for i, d in enumerate(devices) if d["name"] == name), -1)
            if name and index < 0:
                self.device.insertItem(0, f"Unavailable: {name}", None)
                index = 0
            elif not name:
                matches = [i for i, d in enumerate(devices) if "M12 In 11/12" in d["name"]]
                index = matches[0] if len(matches) == 1 else -1
            self.device.setCurrentIndex(index)
            self.message.setText("Input changes take effect when you press Start.")
        except Exception as error:
            self.message.setText(f"Could not list inputs: {error}")
        finally:
            self.device.blockSignals(False)
        self.channels()

    def channels(self):
        device = self.device.currentData()
        self.channel.clear()
        if device:
            for index in range(device["max_input_channels"]):
                label = f"Channel {index+1}"
                if "M12 In 11/12" in device["name"] and index < 2:
                    label = ("Main mix left", "Main mix right")[index]
                elif "M12 In 5/6" in device["name"]:
                    label += f" · Model 12 channel {index+5}"
                self.channel.addItem(label, index)
            self.channel.setCurrentIndex(min(self.selected.get("channel", 0), self.channel.count()-1))
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(bool(device))

    def values(self):
        return dict(input=self.device.currentData()["name"], channel=self.channel.currentData(), gate=self.gate.value(), cues=self.cues.isChecked())


class MainWindow(QMainWindow):
    """Setup stays off the card; capture and grading remain shared by all lessons."""
    def __init__(self, data_dir, lesson_dir, capture_factory=Capture):
        super().__init__()
        self.store = Store(data_dir)
        self.painter = None
        self.explorer = None
        self.jam = None
        self.stems = None
        self.settings = self.store.settings()
        self.lesson_dir = Path(lesson_dir)
        self.session = Session(self.store)
        self.capture_factory = capture_factory
        self.capture = self.calibration = None
        self.detection_dialog = None
        self.diagnose_on_open = False
        self.recent_input = deque(maxlen=60)
        self.hearing = LiveHearing()
        self.stopping = self.closing = False
        self.closed = False
        self.transition = None
        self.pending = None
        self.flash_until = 0
        self.cue = CuePlayer(data_dir)
        self.setWindowTitle('GuitarHacks · Home')
        self.resize(1100,820)
        self.setMinimumSize(680,640)
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self.build_splash()
        self.build_setup()
        self.build_card()
        self.build_results()
        self.home_page=HomePage()
        self.home_page.notes.connect(self.show_notes)
        self.home_page.everywhere.connect(self.show_explorer)
        self.home_page.painter.connect(self.show_painter)
        self.home_page.connection.connect(self.connection_settings)
        self.home_page.jam.connect(self.show_jam)
        self.home_page.stems.connect(self.show_stems)
        self.pages.addWidget(self.home_page)
        self.next_timer = QTimer(self)
        self.next_timer.setSingleShot(True)
        self.next_timer.timeout.connect(self.advance_step)
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(50)
        self.clock_timer.timeout.connect(self.tick)
        self.clock_timer.start()
        self.shortcuts = []
        for key,callback in [('F11',self.full_screen),('Escape',self.exit_full_screen)]:
            shortcut=QShortcut(QKeySequence(key),self)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        self.detect_default_input()
        self.pages.setCurrentWidget(self.splash)
        self.splash_timer=QTimer(self)
        self.splash_timer.setSingleShot(True)
        self.splash_timer.timeout.connect(self.show_home)
        self.splash_timer.start(1500)

    def build_splash(self):
        self.splash=QWidget()
        box=QVBoxLayout(self.splash)
        box.setContentsMargins(70,70,70,70)
        box.addStretch(2)
        mark=FitLabel(180,50,True)
        mark.setText('*')
        mark.setStyleSheet('color:#a6dac2;')
        box.addWidget(mark,3)
        title=FitLabel(100,35,True)
        title.setText('GuitarHacks')
        box.addWidget(title,2)
        caption=text_label('A little practice. A familiar fretboard.')
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(caption)
        box.addStretch(3)
        self.pages.addWidget(self.splash)

    def build_setup(self):
        self.setup_page=LabPage('The note lab','Note flash cards',
            'A note. A string.\nA little more familiarity.',self.show_home)
        self.setup_title=self.setup_page.title
        box=self.setup_page.control_box
        box.addWidget(caption('Make it yours',18,INK,True))
        self.mode_panel=QWidget()
        self.mode_panel.setStyleSheet('background:transparent;')
        modes=QGridLayout(self.mode_panel);modes.setContentsMargins(0,0,0,0);modes.setSpacing(8)
        self.mode_group=QButtonGroup(self)
        self.mode_buttons=[]
        for index,name in enumerate(MODES):
            button=QRadioButton(name.replace(', ','\n'))
            button.setAccessibleName(name)
            button.setStyleSheet('font-size:12px; padding:4px 0;')
            self.mode_group.addButton(button,index)
            self.mode_buttons.append(button)
            if index<4:modes.addWidget(button,index//2,index%2)
            else:button.setParent(self.mode_panel);button.hide()
        box.addWidget(self.mode_panel)
        mode=self.settings.get('mode',0)
        self.mode_buttons[mode if mode in range(len(MODES)) else 0].setChecked(True)
        selection=QHBoxLayout()
        self.note_box,self.note_combo=self.combo_field('Note',selection)
        for pc,name in enumerate(NOTES):self.note_combo.addItem(name,pc)
        self.note_combo.setCurrentIndex(max(0,min(11,self.settings.get('note',0))))
        self.string_box,self.string_combo=self.combo_field('String',selection)
        for number,(_,name) in STRINGS.items():self.string_combo.addItem(name,number)
        self.string_combo.setCurrentIndex(max(0,self.string_combo.findData(self.settings.get('string',5))))
        box.addLayout(selection)
        limits=QHBoxLayout()
        self.seconds_spin=self.spin_field('Seconds per card',limits,5,120,self.settings.get('seconds_limit',20))
        self.attempts_spin=self.spin_field('Attempts per card',limits,1,20,self.settings.get('attempt_limit',3))
        box.addLayout(limits)
        self.lesson_label=caption('Lesson',12)
        box.addWidget(self.lesson_label)
        self.lesson_combo=QComboBox()
        self.lesson_combo.setMinimumContentsLength(12)
        self.lesson_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.lesson_combo.setAccessibleName('Lesson')
        self.lesson_combo.addItem('Fretboard notes',None)
        lessons,errors=load_lessons(self.lesson_dir)
        for lesson in lessons:self.lesson_combo.addItem(lesson.title,lesson)
        selected=next((i for i in range(1,self.lesson_combo.count())
                       if self.lesson_combo.itemData(i).id==self.settings.get('plugin')),0)
        self.lesson_combo.setCurrentIndex(selected)
        box.addWidget(self.lesson_combo)
        self.settings_button=QPushButton('Connection settings')
        self.settings_button.setObjectName('quiet')
        self.settings_button.clicked.connect(self.connection_settings)
        box.addWidget(self.settings_button)
        self.connection=caption('',11)
        box.addWidget(self.connection)
        work=self.setup_page.work
        self.exercise_caption=caption('12 CARDS · FRETS 1–12',11,MINT,True)
        work.addWidget(self.exercise_caption)
        self.preview_note=FitLabel(240,60,True)
        self.preview_note.setStyleSheet('color:#b6e4cc;')
        work.addWidget(self.preview_note,3)
        self.preview_string=caption('Find the note. Play it back.',26,INK,True)
        self.preview_string.setAlignment(Qt.AlignmentFlag.AlignCenter)
        work.addWidget(self.preview_string)
        self.preview_board=Fretboard();self.preview_board.setMaximumHeight(240);work.addWidget(self.preview_board,2)
        self.preview_help=caption('',14);self.preview_help.setAlignment(Qt.AlignmentFlag.AlignCenter)
        work.addWidget(self.preview_help)
        self.setup_error=caption('',14,'#ffaaa2')
        self.setup_error.setAccessibleName('Practice message')
        self.setup_error.hide();work.addWidget(self.setup_error)
        self.start_button=QPushButton('Start practice  →');self.start_button.setMinimumHeight(54)
        self.start_button.setObjectName('primary');self.start_button.clicked.connect(self.toggle)
        work.addWidget(self.start_button)
        self.setup_detection_help = QPushButton('Report detection problem')
        self.setup_detection_help.clicked.connect(self.report_detection)
        box.addWidget(self.setup_detection_help)
        self.pages.addWidget(self.setup_page)
        self.mode_group.idClicked.connect(self.config_changed)
        for combo in (self.note_combo,self.string_combo,self.lesson_combo):
            combo.currentIndexChanged.connect(self.config_changed)
        self.seconds_spin.valueChanged.connect(self.config_changed)
        self.attempts_spin.valueChanged.connect(self.config_changed)
        self.update_selectors()
        if errors:
            logging.warning('Lesson errors: %s',errors)
            self.show_practice_message('Lesson files: '+'\n'.join(errors))

    def combo_field(self,label,row):
        widget=QWidget()
        widget.setObjectName('formField');widget.setStyleSheet('QWidget#formField {background:transparent;}')
        layout=QVBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(caption(label,11))
        combo=QComboBox()
        combo.setMinimumContentsLength(3)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setAccessibleName(label)
        layout.addWidget(combo)
        row.addWidget(widget)
        return widget,combo

    def prepare_painter(self):
        from painter_view import PainterView
        if self.painter is None:
            assets=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
            self.painter=PainterView(self.store.directory,assets,self,settings=self.store.settings,
                capture_factory=self.capture_factory,available=lambda: self.capture is None and not self.stopping)
            self.painter.bridge.leave.connect(self.show_home)
            self.painter.bridge.exploreRequested.connect(self.show_explorer)
            self.pages.addWidget(self.painter)

    def show_painter(self):
        self.splash_timer.stop()
        self.pause()
        self.prepare_painter()
        self.setWindowTitle('GuitarHacks · Chord Painter')
        self.pages.setCurrentWidget(self.painter)

    def show_explorer(self):
        self.splash_timer.stop()
        self.pause()
        if self.explorer is None:
            from painter_view import ExplorerView
            assets=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
            self.explorer=ExplorerView(assets,self)
            self.explorer.bridge.leave.connect(self.show_home)
            self.explorer.bridge.practice.connect(self.explore_practice)
            self.pages.addWidget(self.explorer)
        self.setWindowTitle('GuitarHacks · Fretboard Explorer')
        self.pages.setCurrentWidget(self.explorer)

    def explore_practice(self,note):
        self.show_everywhere()
        self.note_combo.setCurrentIndex(self.note_combo.findData(note))

    def show_jam(self):
        self.splash_timer.stop()
        self.pause()
        if self.jam is None:
            from jam_view import JamPage
            self.jam=JamPage(self.store,self.show_home)
            self.pages.addWidget(self.jam)
        self.setWindowTitle('GuitarHacks · Record with Jam')
        self.pages.setCurrentWidget(self.jam)

    def show_stems(self):
        self.splash_timer.stop()
        self.pause()
        if self.stems is None:
            from stems_view import StemSlicerPage
            self.stems=StemSlicerPage(self.show_home)
            self.pages.addWidget(self.stems)
        self.setWindowTitle('GuitarHacks · StemSlicer')
        self.pages.setCurrentWidget(self.stems)
        if not hasattr(self, 'before_stems_geometry'):
            self.before_stems_geometry = self.saveGeometry()
        self.showNormal()
        self.setMaximumWidth(800)
        self.resize(800, max(740, self.stems.minimumHeight()))

    def show_home(self):
        if self.closing:return
        if hasattr(self, 'before_stems_geometry'):
            self.setMaximumWidth(16777215)
            self.restoreGeometry(self.before_stems_geometry)
            del self.before_stems_geometry
        if self.jam:
            self.jam.disconnect()
            self.settings.update({k:v for k,v in self.store.settings().items() if k.startswith('jam_')})
        self.splash_timer.stop()
        self.pause()
        self.setWindowTitle('GuitarHacks · Home')
        self.connection_text()
        self.pages.setCurrentWidget(self.home_page)

    def show_notes(self):
        if self.mode_group.checkedId()==4:
            mode=self.settings.get('note_mode',0)
            self.mode_buttons[mode if mode in range(4) else 0].setChecked(True)
            plugin=self.settings.get('note_plugin')
            self.lesson_combo.blockSignals(True)
            self.lesson_combo.setCurrentIndex(next((i for i in range(1,self.lesson_combo.count())
                if self.lesson_combo.itemData(i).id==plugin),0))
            self.lesson_combo.blockSignals(False)
            self.config_changed()
        self.show_setup()

    def show_everywhere(self):
        if self.mode_group.checkedId() in range(4):self.save_config()
        self.lesson_combo.blockSignals(True)
        self.lesson_combo.setCurrentIndex(0)
        self.lesson_combo.blockSignals(False)
        self.mode_buttons[4].setChecked(True)
        self.config_changed()
        self.show_setup()

    def spin_field(self,label,row,minimum,maximum,value):
        widget=QWidget()
        widget.setObjectName('formField');widget.setStyleSheet('QWidget#formField {background:transparent;}')
        layout=QVBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(caption(label,11))
        spin=QSpinBox()
        spin.setAccessibleName(label)
        spin.setRange(minimum,maximum)
        spin.setValue(value)
        layout.addWidget(spin)
        row.addWidget(widget)
        return spin

    def build_card(self):
        self.card_page=LabPage('The note lab','Note flash cards',
            'Find the note.\nLet your ears and fingers connect.',self.show_home)
        box=self.card_page.work
        self.card_home=self.card_page.home
        self.card_home.setText('End run · Home')
        self.card_home.setToolTip('End this run and return home. Remaining cards are saved as skipped.')
        tips=self.card_page.control_box
        tips.addWidget(caption('Your practice',18,INK,True))
        self.run_phase=caption('CONNECT YOUR GUITAR',10,GOLD,True);tips.addWidget(self.run_phase)
        self.run_help=caption('First, mute the strings. Then play each open string when prompted. Setup is not scored.',14)
        tips.addWidget(self.run_help)
        self.run_input=caption('',11);tips.addWidget(self.run_input)
        self.live_heard=caption('Hearing: —',18,MINT,True)
        self.live_heard.setAccessibleName('Live detected note and tuning')
        tips.addWidget(self.live_heard)
        self.detection_help_button=QPushButton('Report detection problem')
        self.detection_help_button.clicked.connect(self.report_detection)
        tips.addWidget(self.detection_help_button)
        header=QHBoxLayout()
        self.countdown=QLabel('00:20')
        self.countdown.setStyleSheet('font-size:52px; font-weight:600;')
        header.addWidget(self.countdown,1,Qt.AlignmentFlag.AlignTop)
        self.attempt_display=QLabel('Attempts\n0/3')
        self.attempt_display.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTop)
        self.attempt_display.setStyleSheet('font-size:30px;')
        header.addWidget(self.attempt_display,1)
        box.addLayout(header)
        self.prompt=FitLabel(440,40,True)
        self.prompt.setAccessibleName('Target note')
        self.glow=QGraphicsDropShadowEffect(self.prompt)
        self.glow.setOffset(0,0)
        self.glow.setBlurRadius(36)
        self.glow.setEnabled(False)
        self.prompt.setGraphicsEffect(self.glow)
        box.addWidget(self.prompt,7)
        self.instruction=FitLabel(80,24,True)
        self.instruction.setAccessibleName('Target string')
        box.addWidget(self.instruction,2)
        self.fretboard=Fretboard()
        box.addWidget(self.fretboard,3)
        self.fretboard.hide()
        footer=QHBoxLayout()
        self.progress=QLabel()
        self.progress.setStyleSheet('font-size:22px; color:#b6e4cc;')
        footer.addWidget(self.progress,1)
        self.total=QLabel()
        self.total.setStyleSheet('font-size:22px;')
        self.total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.addWidget(self.total,1)
        self.again_button=QPushButton('Again')
        self.again_button.clicked.connect(self.show_setup)
        tips.addWidget(self.again_button)
        self.quit_button=QPushButton('Quit')
        self.quit_button.clicked.connect(self.close)
        self.quit_button.setObjectName('quiet')
        tips.addWidget(self.quit_button)
        box.addLayout(footer)
        self.pages.addWidget(self.card_page)

    def update_selectors(self):
        mode=self.mode_group.checkedId()
        standard=self.lesson_combo.currentData() is None
        self.note_box.setVisible(standard and mode in (2,3,4))
        self.string_box.setVisible(standard and mode in (1,3))
        race=standard and mode==4
        self.setup_title.setText('Find everywhere' if race else 'Note flash cards')
        self.setup_page.brand.setText('GUITARHACKS   /   '+('THE FRETBOARD LAB' if race else 'THE NOTE LAB'))
        self.setup_page.description.setText('One note. The whole neck.\nFind every place it belongs.' if race else 'A note. A string.\nA little more familiarity.')
        self.mode_panel.setVisible(not race)
        self.lesson_combo.setVisible(not race);self.lesson_label.setVisible(not race)
        self.seconds_spin.parentWidget().setVisible(not race)
        self.attempts_spin.parentWidget().setVisible(not race)
        self.exercise_caption.setText('Open–14 · any order · stopwatch · unlimited tries' if race else '12 cards · frets 1–12')
        self.preview_note.setText(NOTES[self.note_combo.currentData()] if mode in (2,3,4) and standard else '?')
        self.preview_note.setMaximumHeight(140 if race else 16777215)
        self.preview_board.setVisible(race)
        self.preview_string.setText('Every place. Any order.' if race else
            (STRINGS[self.string_combo.currentData()][1]+' string' if mode in (1,3) and standard else 'Find the note. Play it back.'))
        self.preview_help.setText('Find this note from open strings through fret 14. The stopwatch starts after guitar setup.' if race else
            'Your target appears here. First, a quick guitar setup; then 12 cards at your pace.')
        self.start_button.setText('Start finding  →' if race else 'Start flash cards  →')
        for button in self.mode_buttons:button.setEnabled(standard)

    def config_changed(self,*args):
        self.update_selectors()
        self.save_config()

    def save_config(self):
        plugin=self.lesson_combo.currentData()
        if self.mode_group.checkedId() in range(4):
            self.settings.update(note_mode=self.mode_group.checkedId(),note_plugin=plugin.id if plugin else None)
        self.settings.update(mode=self.mode_group.checkedId(),note=self.note_combo.currentData(),
            string=self.string_combo.currentData(),seconds_limit=self.seconds_spin.value(),
            attempt_limit=self.attempts_spin.value(),plugin=plugin.id if plugin else None)
        self.store.set_settings(self.settings)

    def selected_lesson(self):
        return self.lesson_combo.currentData() or make_exercise(self.mode_group.checkedId(),
            self.note_combo.currentData(),self.string_combo.currentData())

    def show_setup(self):
        if self.closing:return
        self.splash_timer.stop()
        self.setWindowTitle('GuitarHacks · '+self.setup_title.text())
        self.pages.setCurrentWidget(self.setup_page)
        self.start_button.setEnabled(not self.stopping)
        self.connection_text()

    def detect_default_input(self):
        if not self.settings.get('input'):
            try:
                matches=[d for d in input_devices() if 'M12 In 11/12' in d['name']]
                if len(matches)==1:self.settings.update(input=matches[0]['name'],channel=0)
            except Exception:logging.exception('Input discovery')
        self.connection_text()

    def connection_text(self):
        name=self.settings.get('input','Choose an input in Connection')
        if 'M12 In 11/12' in name:
            name='Model 12 · main mix · '+('left' if self.settings.get('channel',0)==0 else 'right')
        self.connection.setText(name)
        if hasattr(self,'home_page'):self.home_page.input_label.setText(name)
        if hasattr(self,'run_input'):self.run_input.setText(name)

    def toggle(self):
        if self.capture or self.stopping:return
        if self.painter and self.painter.listener.capture is not None:
            self.show_practice_message('Chord listening is still stopping. Try Start again in a moment.')
            return
        self.setup_error.hide()
        if not self.settings.get('input'):
            self.connection_settings()
            return
        self.save_config()
        self.run_lesson=self.selected_lesson()
        self.session=(EverywhereSession if self.run_lesson.id=='everywhere-v1' else Session)(self.store)
        self.style_run()
        self.splash_timer.stop()
        self.pages.setCurrentWidget(self.card_page)
        self.reset_surface()
        self.prompt.setText('Connecting')
        self.instruction.setText('')
        self.capture=self.capture_factory(self.settings['input'],self.settings.get('channel',0),
            self.settings.get('gate',DEFAULT_GATE_DB),self)
        if hasattr(self.capture, 'set_hold_seconds'):
            self.capture.set_hold_seconds(self.settings.get('hold_seconds', .5))
        self.recent_input.clear()
        self.capture.opened.connect(self.opened)
        self.capture.frame.connect(self.audio_frame)
        self.capture.note.connect(self.audio_note)
        self.capture.failed.connect(self.audio_failed)
        self.capture.finished.connect(self.capture_finished)
        self.capture.start()

    def reset_surface(self):
        self.detection_help_button.setVisible(self.calibration is not None)
        self.live_heard.setVisible(True)
        self.card_home.setText('End run · Home' if self.session.active else '← Home')
        self.prompt.maximum=440
        self.fretboard.hide()
        for widget in (self.countdown,self.attempt_display,self.progress,self.total,self.again_button):
            widget.hide()
        self.instruction.show()
        self.paint_note('#edf3ef')

    def style_run(self):
        race=isinstance(self.session,EverywhereSession)
        self.card_page.title.setText('Find everywhere' if race else 'Note flash cards')
        self.card_page.brand.setText('GUITARHACKS   /   '+('THE FRETBOARD LAB' if race else 'THE NOTE LAB'))
        self.card_page.description.setText('One note. The whole neck.\nFind every place it belongs.' if race else 'A note. A string.\nA little more familiarity.')

    def opened(self,name):
        if self.stopping:return
        self.calibration=Calibration(self.settings.get('gate',DEFAULT_GATE_DB))
        self.show_calibration()
        logging.info('Input opened: %s channel=%s',name,self.settings.get('channel',0))
        if self.diagnose_on_open:
            self.diagnose_on_open=False
            self.report_detection()

    def show_calibration(self):
        self.reset_surface()
        self.hearing.clear()
        self.live_heard.setText('Hearing: — · waiting for a clear note')
        self.run_phase.setText('GUITAR SETUP · NOT SCORED')
        self.run_help.setText('Mute the strings, then play each open string when prompted. Take your time.')
        c=self.calibration
        if c.stage=='noise':
            self.prompt.setText('Mute strings')
            self.instruction.setText('Measuring background')
        else:
            string,midi,name,_=c.current
            self.countdown.setText(f'Setup {c.index+1}/6')
            self.countdown.setStyleSheet('font-size:28px; color:#a7b8b1;')
            self.countdown.show()
            self.prompt.setText(NOTES[midi%12])
            self.instruction.setText(f'{name} string · open (fret 0)')
            self.capture.reset_detection()
            c.started,c.armed=time.monotonic(),False

    def report_detection(self):
        if self.detection_dialog or self.stopping or self.closing:
            return
        if not self.capture:
            if not self.settings.get('input'):
                self.connection_settings()
                return
            self.diagnose_on_open=True
            self.toggle()
            return
        if not self.calibration:
            return
        self.next_timer.stop()
        self.transition=None
        self.detection_dialog=DetectionHelp(self)
        self.detection_dialog.finished.connect(self.finish_detection_help)
        self.detection_dialog.open()

    def finish_detection_help(self, *_):
        dialog=self.detection_dialog
        self.detection_dialog=None
        if dialog:dialog.deleteLater()
        if self.calibration and self.capture and not self.stopping and not self.closing:
            self.show_calibration()

    def show_card(self):
        self.reset_surface()
        self.hearing.clear()
        self.live_heard.setText('Hearing: — · waiting for a clear note')
        self.style_run()
        self.run_phase.setText('PLAY & LISTEN')
        self.run_help.setText('Find the note on the requested string. Mute briefly, then pick one clean note.')
        self.pages.setCurrentWidget(self.card_page)
        card=self.session.card
        self.prompt.setText(card.prompt.removeprefix('Play ').split('\non the ')[0])
        self.instruction.setText(card.instruction)
        if card.lesson_id != 'fretboard-v2' and card.string:
            label=STRINGS[card.string][1]
            octave=' · octave up' if card.midi-STRINGS[card.string][0]>=12 else ''
            self.instruction.setText(f'{label} string{octave}')
        self.countdown.show()
        self.attempt_display.show()
        self.flash_until=0
        self.capture.reset_detection()
        self.session.begin_card()
        if isinstance(self.session,EverywhereSession):
            self.prompt.maximum=150
            self.prompt.fit()
            self.run_phase.setText('EXPLORE THE NECK')
            self.run_help.setText('Find this note anywhere from open strings to fret 14. Mint dots mark credited positions; red dots mark misses. The ring marks your latest match.')
            self.fretboard.set_found(self.session.found,self.session.mistakes)
            self.fretboard.show()
            self.instruction.setText(f'Open–14 · {self.session.remaining} left')
        self.tick()

    def paint_note(self,color,glow=False):
        self.prompt.setStyleSheet(f'color:{color};')
        self.glow.setColor(QColor(color))
        self.glow.setEnabled(glow)

    @staticmethod
    def format_time(seconds):
        seconds=max(0,int(seconds))
        return f'{seconds//60:02d}:{seconds%60:02d}'

    def tick(self):
        if self.closing:return
        if self.transition=='gap':
            if not self.calibration:self.total.setText('Total\n'+self.format_time(self.session.elapsed))
            return
        if self.pages.currentWidget()!=self.card_page or self.calibration or self.transition:
            return
        if not self.session.active:return
        if isinstance(self.session,EverywhereSession):
            self.countdown.setText(self.format_time(self.session.elapsed))
            self.countdown.setStyleSheet('font-size:52px; font-weight:600; color:#edf3ef;')
            self.attempt_display.setText(f'Misses\n{self.session.misses}')
            if time.monotonic()>=self.flash_until:
                self.paint_note('#edf3ef')
                self.instruction.setText(f'Open–14 · {self.session.remaining} left')
            return
        if self.session.tick():
            self.finish_card('timeout')
            return
        left=math.ceil(self.session.countdown)
        color='#ff9f32' if left<=3 else '#edf3ef'
        self.countdown.setText(self.format_time(left))
        self.countdown.setStyleSheet(f'font-size:52px; font-weight:600; color:{color};')
        self.attempt_display.setText(f'Attempts\n{self.session.attempts}/{self.session.attempt_limit}')
        if time.monotonic()>=self.flash_until:self.paint_note(color)

    def finish_card(self,result):
        self.transition='result'
        self.pending='practice'
        self.countdown.setText(self.format_time(math.ceil(self.session.countdown)))
        self.attempt_display.setText(f'Attempts\n{self.session.attempts}/{self.session.attempt_limit}')
        self.paint_note('#83ed9e' if result=='correct' else '#ff606b',True)
        if result=='correct':self.play_cue()
        self.next_timer.start(1000)

    def play_cue(self):
        if self.settings.get('cues',True):
            try:self.cue.play()
            except (OSError,RuntimeError):logging.exception('Completion cue unavailable')

    def advance_step(self):
        if self.closing:return
        if self.transition=='race_done':
            self.transition=None
            self.show_complete()
            return
        if self.transition=='result':
            self.transition='gap'
            self.reset_surface()
            self.prompt.maximum=800
            self.prompt.setText('*')
            self.paint_note('#a6dac2')
            self.instruction.hide()
            if not self.calibration:
                self.progress.setText(f'{self.session.remaining}/12 Left')
                self.progress.show()
                self.total.setText('Total\n'+self.format_time(self.session.elapsed))
                self.total.show()
            self.next_timer.start(2000)
            return
        if self.transition!='gap':return
        self.transition=None
        if self.pending=='calibration':self.show_calibration()
        elif self.pending=='start_practice':
            c=self.calibration
            logging.info('Guitar references: %s; note gate %.1f dBFS',c.readings,c.gate)
            self.capture.set_gate(c.gate)
            self.session.start(self.run_lesson,reference_cents=c.reference_cents,
                seconds_limit=self.seconds_spin.value(),attempt_limit=self.attempts_spin.value())
            self.calibration=None
            self.show_card()
        elif self.session.remaining:
            self.session.next()
            self.show_card()
        else:self.show_complete()

    def show_complete(self):
        stats=self.store.run_stats(self.session.run_id)
        race=isinstance(self.session,EverywhereSession)
        self.results_subtitle.setText(self.session.lesson.title)
        values=dict(total=self.precise_time(stats['total']),solved=f"{stats['solved']}/{stats['size']}",
                    missed=str(stats['missed']),red=str(stats['red']),
                    first=f"{stats['first_try']}/{stats['size']}",attempts=str(stats['attempts']),
                    average=f"{stats['average']:.1f}s" if stats['average'] is not None else '—',
                    best=self.precise_time(stats['best']) if stats['best'] is not None else '—')
        for key,value in values.items():self.result_values[key].setText(value)
        groups=stats['strings']
        if race:
            slow='Not measured in free order'
            missed='Not measured in free order'
        elif groups:
            maximum=max(g['average'] for g in groups.values())
            names=' / '.join(STRINGS[s][1] for s,g in groups.items() if abs(g['average']-maximum)<.05)
            slow=f'{names} · {maximum:.1f}s average'
            maximum=max(g['missed'] for g in groups.values())
            names=' / '.join(STRINGS[s][1] for s,g in groups.items() if g['missed']==maximum)
            missed=f'{names} · {maximum} missed' if maximum else 'None · all answered'
        else:slow=missed='No string data'
        self.slowest_string.setText('Slowest string\n'+slow)
        self.missed_string.setText('Most missed string\n'+missed)
        detail=(f"{stats['timed_out']} timed out · {stats['exhausted']} attempt limit · {stats['skipped']} skipped")
        self.results_detail.setText('Pitch matches credited; physical locations are not verified.' if race else detail)
        self.best_caption.setText(f"Best total: {stats['best_runs']} fully answered run(s) with the same exercise and settings.")
        self.pages.setCurrentWidget(self.results_page)
        self.stop_capture()

    @staticmethod
    def precise_time(seconds):
        tenths=max(0,round(seconds*10))
        return f'{tenths//600:02d}:{(tenths//10)%60:02d}.{tenths%10}'

    def build_results(self):
        self.results_page=LabPage('Your practice','Set complete',
            'A little progress.\nAnother step toward a familiar fretboard.',self.show_home)
        self.results_page.eyebrow.setText('PLAY. REFLECT. REPEAT.')
        box=self.results_page.work
        self.results_subtitle=text_label()
        box.addWidget(self.results_subtitle)
        grid=QGridLayout()
        grid.setSpacing(20)
        self.result_values={}
        for index,(key,label) in enumerate([('total','Total time'),('best','Best total'),
                ('solved','Answered'),('missed','Missed'),('red','Red attempts'),('first','First try'),
                ('attempts','Total attempts'),('average','Average response')]):
            tile=QWidget()
            tile.setObjectName('resultTile')
            tile.setStyleSheet('QWidget#resultTile {background:#122024; border:1px solid #3a5146; border-radius:12px;}')
            layout=QVBoxLayout(tile)
            layout.setContentsMargins(14,16,14,16)
            value=QLabel('—')
            value.setStyleSheet('font-size:30px; font-weight:700; color:#b6e4cc;')
            value.setAccessibleName(label)
            layout.addWidget(value)
            layout.addWidget(caption(label,12))
            grid.addWidget(tile,index//2,index%2)
            self.result_values[key]=value
        box.addLayout(grid,2)
        strings=self.results_page.control_box
        strings.addWidget(caption('What to work on',18,INK,True))
        self.slowest_string=text_label()
        self.missed_string=text_label()
        for label in (self.slowest_string,self.missed_string):
            label.setStyleSheet('font-size:14px; color:#f4f2e9; background:transparent;')
            strings.addWidget(label)
        self.results_detail=text_label()
        self.best_caption=text_label()
        box.addWidget(self.results_detail)
        box.addWidget(self.best_caption)
        controls=QHBoxLayout()
        again=QPushButton('Again')
        again.setObjectName('primary')
        again.clicked.connect(self.show_setup)
        controls.addWidget(again,3)
        quit_button=QPushButton('Quit')
        quit_button.clicked.connect(self.close)
        controls.addWidget(quit_button,1)
        box.addLayout(controls)
        self.pages.addWidget(self.results_page)

    def audio_frame(self,frame):
        if self.stopping or self.closing:return
        self.recent_input.append(frame)
        if self.detection_dialog:
            self.detection_dialog.frame(frame)
            return
        self.live_heard.setText(self.hearing.update(frame))
        if self.transition:return
        if self.calibration:
            if self.calibration.frame(frame):
                self.capture.set_gate(self.calibration.gate)
                self.show_calibration()
            return
        self.session.frame(frame)

    def audio_note(self,pitch):
        if self.stopping or self.transition or self.closing:return
        if self.detection_dialog:
            self.detection_dialog.note(pitch)
            return
        self.live_heard.setText(self.hearing.update({'raw_pitch':pitch, 'db':pitch['db'],
                                                     'gate':self.calibration.gate if self.calibration else self.settings.get('gate',DEFAULT_GATE_DB)}))
        if self.calibration:
            result=self.calibration.note(pitch)
            if result in ('accepted','done'):
                self.paint_note('#83ed9e',True)
                self.play_cue()
                self.transition='result'
                self.pending='start_practice' if result=='done' else 'calibration'
                self.next_timer.start(1000)
            elif result=='wrong':
                self.paint_note('#ff606b',True)
                _, expected, name, _ = self.calibration.current
                direction='flat' if pitch['cents'] < 0 else 'sharp'
                tuning='in tune' if abs(pitch['cents'])<=5 else f'{abs(pitch["cents"]):.0f} cents {direction}'
                self.run_help.setText(f'Heard {pitch["note"]} at {pitch["hz"]:.1f} Hz '
                    f'({tuning}). '
                    f'Expected {NOTES[expected%12]}{expected//12-1} on the {name} string. Mute, then try again.')
            return
        result=self.session.note(pitch)
        logging.info('Pitch %s, result=%s attempts=%s',pitch,result,self.session.attempts)
        if isinstance(self.session,EverywhereSession):
            if result in ('correct','retry','duplicate'):
                self.fretboard.set_found(self.session.found,self.session.mistakes)
                self.flash_until=time.monotonic()+.5
                self.paint_note({'correct':'#83ed9e','retry':'#ff606b','duplicate':'#a7b8b1'}[result],True)
                self.instruction.setText('Pitch already filled' if result=='duplicate' else f'Open–14 · {self.session.remaining} left')
                self.attempt_display.setText(f'Misses\n{self.session.misses}')
                if result=='correct' and not self.session.active:
                    self.countdown.setText(self.format_time(self.session.elapsed))
                    self.play_cue()
                    self.transition='race_done'
                    self.next_timer.start(800)
            return
        if result in ('correct','timeout','exhausted'):
            self.finish_card(result)
        elif result=='retry':
            self.flash_until=time.monotonic()+.6
            self.paint_note('#ff606b',True)
            self.tick()

    def stop_capture(self):
        if self.capture:
            self.stopping=True
            self.capture.stop()

    def capture_finished(self):
        if self.capture:self.capture.deleteLater()
        self.capture=None
        self.stopping=False
        self.start_button.setEnabled(True)
        if self.closing:
            QTimer.singleShot(0,self.close)
        elif self.session.active or self.calibration:
            self.next_timer.stop()
            self.transition=None
            self.calibration=None
            self.session.quit()
            self.show_setup()
            self.connection.setText('Input stopped · check Connection')

    def pause(self):
        self.diagnose_on_open=False
        if self.detection_dialog:
            self.detection_dialog.reject()
        self.next_timer.stop()
        self.transition=None
        self.calibration=None
        self.session.quit()
        self.stop_capture()

    def audio_failed(self,message):
        logging.error('Input failed: %s',message)
        if self.detection_dialog:
            self.detection_dialog.attention('Input failed: '+message)
        self.pause()
        if not self.closing:
            self.show_setup()
            self.show_practice_message(message)

    def show_practice_message(self,message):
        self.setup_error.setText(message)
        self.setup_error.show()

    def connection_settings(self):
        if getattr(self,'connection_page',None):return
        self.connection_return=self.pages.currentWidget()
        page=LabPage('Guitar connection','Your guitar.',
            'One connection.\nReady for every audio exercise.',lambda:self.connection_dialog.reject())
        page.eyebrow.setText('CONNECT. CHECK. PLAY.')
        page.home.setText('← Back')
        page.control_box.addWidget(caption('One shared input',18,INK,True))
        page.control_box.addWidget(caption('These settings apply to Flash cards and Find everywhere. Chord Painter works without audio.',14))
        dialog=SettingsPanel(self.settings,self.lesson_dir,self)
        page.work.addWidget(dialog)
        self.connection_page,self.connection_dialog=page,dialog
        dialog.finished.connect(self.finish_connection_settings)
        self.pages.addWidget(page);self.pages.setCurrentWidget(page)
        dialog.show()
        self.setWindowTitle('GuitarHacks · Connection')

    def finish_connection_settings(self,result):
        if result:
            self.settings.update(self.connection_dialog.values())
            self.store.set_settings(self.settings)
        page=self.connection_page
        self.pages.setCurrentWidget(self.connection_return)
        self.pages.removeWidget(page);page.deleteLater()
        self.connection_page=self.connection_dialog=None
        self.setWindowTitle('GuitarHacks · '+('Home' if self.connection_return is self.home_page else self.setup_title.text()))
        self.connection_text()
        # Reload plug-ins without changing the learner's current selection.
        previous=self.lesson_combo.currentData()
        ident=previous.id if previous else None
        lessons,errors=load_lessons(self.lesson_dir)
        self.lesson_combo.blockSignals(True)
        self.lesson_combo.clear()
        self.lesson_combo.addItem('Fretboard notes',None)
        for lesson in lessons:self.lesson_combo.addItem(lesson.title,lesson)
        self.lesson_combo.setCurrentIndex(next((i for i in range(1,self.lesson_combo.count())
            if self.lesson_combo.itemData(i).id==ident),0))
        self.lesson_combo.blockSignals(False)
        self.config_changed()
        if errors:
            self.show_setup()
            self.show_practice_message('Lesson files: '+'\n'.join(errors))

    def full_screen(self):
        if self.isFullScreen():self.exit_full_screen()
        else:
            self.was_maximized=self.isMaximized()
            self.showFullScreen()

    def exit_full_screen(self):
        if self.isFullScreen():
            self.showMaximized() if getattr(self,'was_maximized',False) else self.showNormal()

    def activate_existing(self):
        if self.isMinimized():self.showNormal()
        self.raise_();self.activateWindow()

    def closeEvent(self,event):
        if self.stems and self.stems.running:
            self.pages.setCurrentWidget(self.stems)
            self.setWindowTitle('GuitarHacks · StemSlicer')
            self.stems.status.setText('Processing is running. Wait for it to finish, or choose Cancel before closing.')
            event.ignore()
            return
        if self.closed:
            event.accept()
            return
        if self.jam:
            self.jam.disconnect()
            if self.jam.pending_save:
                self.pages.setCurrentWidget(self.jam)
                event.ignore()
                return
        self.closing=True
        if self.painter:
            if not self.painter.shutdown():
                self.closing=False
                event.ignore()
                return
        self.splash_timer.stop()
        self.clock_timer.stop()
        self.pause()
        if self.capture and not self.capture.wait(3000):
            event.ignore()
            return
        if self.explorer:
            self.explorer.shutdown()
        self.store.close()
        self.closed=True
        event.accept()


def install_lessons(base):
    folder = base / "lessons" if getattr(sys,'frozen',False) else base / "FretboardFiend" / "lessons"
    folder.mkdir(parents=True, exist_ok=True)
    if getattr(sys, "frozen", False):
        for source in (Path(sys._MEIPASS) / "bundled_lessons").glob("*.json"):
            target = folder / source.name
            if not target.exists():
                shutil.copy2(source, target)
    return folder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, help="Isolated settings and progress folder")
    parser.add_argument("--lesson-dir", type=Path, help="Use this lesson folder instead of the default")
    parser.add_argument("--painter", action="store_true", help="Open Chord Painter directly")
    parser.add_argument("--jam", action="store_true", help="Open local Jam MIDI recording")
    parser.add_argument("--stems", action="store_true", help="Open StemSlicer")
    args = parser.parse_args()
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    data = args.data_dir or base / "data"
    app = QApplication(sys.argv[:1])
    app.setApplicationName("GuitarHacks")
    resources=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    icon=resources/'assets/guitarhacks.ico' if getattr(sys,'frozen',False) else resources/'FretboardFiend/assets/guitarhacks.ico'
    app.setWindowIcon(QIcon(str(icon)))
    apply_theme(app)
    from single_instance import SingleInstance
    instance=SingleInstance(data,app)
    try:
        if not instance.acquire():return 0
        data.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=data/"app.log", level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
        window = MainWindow(data, args.lesson_dir or install_lessons(base))
        # Prepare WebEngine before the native window is shown, so visiting
        # Painter does not recreate the visible Windows handle/taskbar entry.
        window.prepare_painter()
        instance.activated.connect(window.activate_existing)
        app.aboutToQuit.connect(instance.close)
        if sys.platform=='win32':
            from windows_shell import configure_taskbar
            configure_taskbar(window)
        window.show()
        if args.painter:
            window.show_painter()
        elif args.jam:
            window.show_jam()
        elif args.stems:
            window.show_stems()
    except Exception as error:
        logging.exception("Startup failed")
        QMessageBox.critical(None, "GuitarHacks could not start", f"{error}\n\nKeep the app in a writable folder.")
        return 1

    def exception_hook(typ, value, tb):
        logging.error("Unexpected error", exc_info=(typ, value, tb))
        window.pause()
        window.show_setup()
        window.show_practice_message(f"Practice paused: {value}\nDetails are in {data/'app.log'}")

    sys.excepthook = exception_hook
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
