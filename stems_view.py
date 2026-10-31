"""Compact stem-container editor and local separation jobs."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

from PySide6.QtCore import QProcess, QProcessEnvironment, QUrl, Signal, QObject, Qt, QSize
from PySide6.QtGui import QDesktopServices, QColor
from PySide6.QtWidgets import (QPushButton, QFileDialog, QComboBox, QListWidget, QListWidgetItem,
                              QProgressBar, QCheckBox, QWidget, QVBoxLayout,
                              QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem,
                              QHeaderView, QAbstractItemView, QDoubleSpinBox, QLabel,
                              QDialog, QDialogButtonBox)

from lab_ui import caption, MINT
from StemSlicer.recipe_spec import PARTS, FORMATS, output_bases, filename_base, song_title, song_slug, suggested_title, validate_stems
from StemSlicer.library import find_song_folder, remember_folder, reports as library_reports
from preview_player import PreviewPlayer, MIDI_SUFFIXES

MIDI_GROUPS = {
    'drums': ['drums'],
    'bass': ['acoustic_bass', 'electric_bass'],
    'guitar': ['acoustic_guitar', 'clean_electric_guitar', 'distorted_electric_guitar'],
    'piano': ['acoustic_piano', 'electric_piano'],
    'vocals': ['voice'],
}


def midi_groups_for_parts(parts):
    if not isinstance(parts, list) or not parts:
        return []
    groups = []
    for part in parts:
        key = 'guitar' if part in ('lead-guitar', 'rhythm-guitar') else part
        if not isinstance(key, str) or key not in MIDI_GROUPS:
            return []
        groups.extend(MIDI_GROUPS[key])
    return list(dict.fromkeys(groups))


class AudioFilePicker(QComboBox):
    requested = Signal()

    def __init__(self):
        super().__init__()
        self.addItem('Choose a File to Be Stemmed')
        self.setAccessibleName('Choose a File to Be Stemmed')
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(22)
        self.setMinimumWidth(0)

    def showPopup(self):
        self.requested.emit()


def project_folder():
    location = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
    for parent in (location, *location.parents):
        candidate = parent / 'StemSlicer'
        if (candidate / 'pyproject.toml').is_file():
            return candidate
    return None


class SliceDestinationDialog(QDialog):
    def __init__(self, parent, suggested):
        super().__init__(parent)
        self.setWindowTitle('Choose slice folder')
        self.setMinimumWidth(540)
        box = QVBoxLayout(self)
        box.addWidget(caption('Choose where to save these slices', 18, MINT, True))
        box.addWidget(QLabel('Folder name'))
        self.folder_name = QLineEdit(suggested.name)
        self.folder_name.setAccessibleName('Slice folder name')
        self.folder_name.setStyleSheet('padding:8px; border:1px solid #43534f;')
        box.addWidget(self.folder_name)
        box.addWidget(QLabel('Inside'))
        parent_row = QHBoxLayout()
        self.parent_path = QLineEdit(str(suggested.parent))
        self.parent_path.setReadOnly(True)
        self.parent_path.setAccessibleName('Parent folder for slices')
        parent_row.addWidget(self.parent_path, 1)
        browse = QPushButton('Browse…')
        browse.clicked.connect(self.browse_parent)
        parent_row.addWidget(browse)
        box.addLayout(parent_row)
        self.preview = caption('', 12)
        box.addWidget(self.preview)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('Use this folder')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        box.addWidget(self.buttons)
        self.folder_name.textChanged.connect(self.validate)
        self.parent_path.textChanged.connect(self.validate)
        self.validate()
        self.folder_name.selectAll()
        self.folder_name.setFocus()

    def destination(self):
        name = self.folder_name.text().strip()
        if song_title(name) != name:
            raise ValueError('Enter a folder name without slashes or special characters (up to 80 characters).')
        parent = Path(self.parent_path.text())
        if not parent.is_dir():
            raise ValueError('Choose an existing parent folder.')
        target = parent / name
        if target.exists() and not target.is_dir():
            raise ValueError('A file already uses that name. Choose a different folder name.')
        return target

    def validate(self):
        try:
            target = self.destination()
            self.preview.setText(('Existing folder — add slices to:\n' if target.is_dir() else 'New folder — will be created at:\n') + str(target))
            valid = True
        except ValueError as error:
            self.preview.setText(str(error))
            valid = False
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(valid)

    def browse_parent(self):
        chosen = QFileDialog.getExistingDirectory(self, 'Choose parent folder', self.parent_path.text())
        if chosen:
            self.parent_path.setText(chosen)


class StemContainer(QObject):
    changed = Signal()
    removed = Signal(object)

    def __init__(self, parent, parts=()):
        super().__init__(parent)
        self.heading = QTableWidgetItem()
        self.filename = QLineEdit()
        self.filename.setStyleSheet('QLineEdit {border:1px solid transparent; padding:5px; font-size:13px;} QLineEdit:hover {border-color:#43534f;} QLineEdit:focus {border-color:#a6dac2; background:#243237;}')
        self.custom_name = ''
        self.filename.textEdited.connect(self.name_edited)
        self.filename.editingFinished.connect(self.changed)
        self.remove = QPushButton('×')
        self.remove.setToolTip('Remove this stem')
        self.remove.setStyleSheet('padding:2px; border:0; font-size:20px; background:transparent;')
        self.remove.clicked.connect(lambda: self.removed.emit(self))
        self.checks = {}
        for name, title, _ in PARTS:
            check = QCheckBox()
            check.setToolTip(title)
            check.setChecked(name in parts)
            check.setStyleSheet('background:transparent;')
            check.toggled.connect(self.changed)
            self.checks[name] = check

    def parts(self):
        return [name for name, check in self.checks.items() if check.isChecked()]

    def name_edited(self, text):
        self.custom_name = text


class StemSlicerPage(QWidget):
    def __init__(self, home_callback, root=None):
        super().__init__()
        self.root = Path(root) if root else project_folder()
        self.source = None
        self.destination_key = None
        self.slice_destination = None
        self.destination_confirmed = False
        self.process = None
        self.running = False
        self.completed = False
        self.cancelled = False
        self.stage = 0
        self.log = None
        self.job_kind = 'stems'
        self.output_buffer = ''
        self.containers = []
        self.midi_queue = []
        self.midi_done = []
        self.midi_total = 0
        self.setStyleSheet('QPushButton {padding:8px 12px; font-size:13px;} QComboBox {padding:7px; font-size:13px;}')
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 12, 16, 12)
        box.setSpacing(8)
        header = QHBoxLayout()
        header.addWidget(caption('One row per stem. Combine any instruments.', 14), 1)
        self.home = QPushButton('← Home')
        self.home.clicked.connect(home_callback)
        header.addWidget(self.home)
        box.addLayout(header)
        box.addWidget(caption('StemSlicer', 18, MINT, True))
        toolbar = QHBoxLayout()
        self.choose = AudioFilePicker()
        self.choose.requested.connect(self.choose_file)
        self.choose.setFixedWidth(470)
        toolbar.addWidget(self.choose, 1)
        toolbar.addStretch(1)
        self.start = QPushButton('Create slices')
        self.start.setObjectName('primary')
        self.start.setEnabled(False)
        self.start.clicked.connect(self.start_separation)
        self.cancel = QPushButton('Cancel')
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self.cancel_separation)
        box.addLayout(toolbar)
        naming = QHBoxLayout()
        naming.addWidget(QLabel('Song title'))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText('Song title for saved files')
        self.title_edit.setFixedWidth(320)
        self.title_edit.setStyleSheet('padding:8px; font-size:14px; border:1px solid #43534f; border-radius:7px;')
        naming.addWidget(self.title_edit, 1)
        self.format_combo = QComboBox()
        for title, value in (('MP3 · 320 kbps', 'mp3'), ('WAV · 24-bit', 'wav'), ('MP3 + WAV', 'both')):
            self.format_combo.addItem(title, value)
        naming.addWidget(self.format_combo)
        naming.addStretch(1)
        box.addLayout(naming)
        self.destination_label = caption('Saved under StemSlicer\\separated\\<song title>', 12)
        destination_row = QHBoxLayout()
        destination_row.addWidget(self.destination_label, 1)
        self.change_destination = QPushButton('Use a different folder…')
        self.change_destination.clicked.connect(lambda: self.choose_destination(override=True))
        destination_row.addWidget(self.change_destination)
        box.addLayout(destination_row)
        status_row = QHBoxLayout()
        self.status = caption('NOT STARTED — choose a file, then define your stems below.', 15, MINT, True)
        status_row.addWidget(self.status, 1)
        self.completed_folder = QPushButton('Open song folder')
        self.completed_folder.setObjectName('primary')
        self.completed_folder.hide()
        self.completed_folder.clicked.connect(lambda: self.open_path(self.output))
        status_row.addWidget(self.completed_folder)
        box.addLayout(status_row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        box.addWidget(self.progress)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(['Stem', 'Vocals', 'Drums', 'Bass', 'Piano', 'Other', 'Lead', 'Rhythm', 'Output file', ''])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setStyleSheet('QTableWidget {border:1px solid #43534f; font-size:13px; gridline-color:#34473e;} QHeaderView::section {background:#243237; padding:5px; border:0; font-size:12px;}')
        for col in range(10):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(col, 58 if col in range(1,8) else 44)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(34)
        self.table.horizontalHeaderItem(6).setToolTip('Lead guitar')
        self.table.horizontalHeaderItem(7).setToolTip('Rhythm guitar')
        box.addWidget(self.table)
        actions = QHBoxLayout()
        self.add_button = QPushButton('+ Add stem')
        self.add_button.clicked.connect(lambda: self.add_stem())
        actions.addWidget(self.add_button)
        self.add_button.setToolTip('Add another stem. An instrument can appear in multiple stems.')
        actions.addStretch(1)
        actions.addWidget(self.start)
        actions.addWidget(self.cancel)
        self.log_button = QPushButton('Processing log')
        self.log_button.setEnabled(False)
        self.log_button.clicked.connect(lambda: self.open_path(self.run_dir / 'processing.log'))
        box.addLayout(actions)
        section = QLabel('MIDIfier')
        section.setStyleSheet('color:#b6e4cc; font-size:18px; font-weight:700; border-top:1px solid #43534f; padding-top:10px;')
        box.addWidget(section)
        saved = QHBoxLayout()
        saved.addWidget(QLabel('Song'))
        self.results = QComboBox()
        self.results.setMinimumWidth(0)
        self.results.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.results.setMinimumContentsLength(12)
        self.results.setFixedWidth(360)
        saved.addWidget(self.results, 1)
        self.open_result = QPushButton('Open folder')
        self.open_result.clicked.connect(self.open_selected)
        saved.addWidget(self.open_result)
        saved.addStretch(1)
        box.addLayout(saved)
        self.files = QListWidget()
        self.files.setStyleSheet('QListWidget {font-size:12px; border:1px solid #34473e;} QListWidget::item {padding:5px;} QListWidget::item:selected {background:#243237; color:#edf3ef;}')
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        box.addWidget(self.files)
        self.preview = PreviewPlayer(self.root, self)
        box.addWidget(self.preview)
        midi_row = QHBoxLayout()
        self.midify = QPushButton('Midify selected')
        self.midify.setObjectName('primary')
        self.midify.clicked.connect(self.start_midify)
        midi_row.addWidget(self.midify)
        midi_row.addWidget(QLabel('Tempo'))
        self.midi_tempo = QDoubleSpinBox()
        self.midi_tempo.setRange(20, 300)
        self.midi_tempo.setDecimals(2)
        self.midi_tempo.setValue(120)
        self.midi_tempo.setSuffix(' BPM')
        self.midi_tempo.setToolTip('Match your Reason project tempo. Timing is preserved; notes are not quantized.')
        midi_row.addWidget(self.midi_tempo)
        self.open_midi = QPushButton('Show MIDI file')
        self.open_midi.hide()
        self.open_midi.clicked.connect(self.reveal_midi)
        midi_row.addWidget(self.open_midi)
        midi_row.addStretch(1)
        midi_row.addWidget(self.log_button)
        midi_row.insertWidget(3, QLabel('Instruments'))
        self.midi_instruments = QComboBox()
        self.midi_instruments.setAccessibleName('MIDI instruments')
        for title, key in (('From stem', 'stem'), ('All instruments', 'all'),
                           ('Drums', 'drums'), ('Bass', 'bass'), ('Guitar', 'guitar'),
                           ('Piano', 'piano'), ('Vocals', 'vocals')):
            self.midi_instruments.addItem(title, key)
        self.midi_instruments.setToolTip('Applies to every checked file. From stem uses saved instrument recipes; originals and unknown recipes use all instruments.')
        self.midi_instruments.setMaximumWidth(160)
        midi_row.insertWidget(4, self.midi_instruments)
        box.addLayout(midi_row)
        box.addWidget(caption('Play checked listens to audio and MIDI together. Midify selected converts checked audio only.', 11))
        box.addWidget(caption('V vocals · D drums · B bass · P piano · O other · L lead guitar · R rhythm guitar   |   Stereo 44.1 kHz input; WAV for Reason.', 11))
        box.addStretch(1)
        self.results.currentIndexChanged.connect(self.show_result)
        self.files.itemChanged.connect(self.update_midi_actions)
        self.title_edit.textChanged.connect(self.definitions_changed)
        self.title_edit.editingFinished.connect(self.select_source_song)
        self.format_combo.currentIndexChanged.connect(self.definitions_changed)
        self.add_stem(['lead-guitar'])
        self.add_stem(['lead-guitar', 'rhythm-guitar'])
        self.refresh_results()
        if self.root is None:
            self.status.setText('SETUP NEEDED — StemSlicer is not installed beside this GuitarHacks project.')
            self.choose.setEnabled(False)

    def add_stem(self, parts=()):
        container = StemContainer(self, parts)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.containers.append(container)
        self.table.setItem(row, 0, container.heading)
        self.table.setCellWidget(row, 8, container.filename)
        self.table.setCellWidget(row, 9, container.remove)
        for col, check in enumerate(container.checks.values(), 1):
            cell = QWidget()
            layout = QHBoxLayout(cell)
            layout.setContentsMargins(0,0,0,0)
            layout.addWidget(check, 0, Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, col, cell)
        container.changed.connect(self.definitions_changed)
        container.removed.connect(self.remove_stem)
        self.definitions_changed()
        self.table.scrollToBottom()
        self.fit_content()
        return container

    def remove_stem(self, container):
        row = self.containers.index(container)
        self.containers.remove(container)
        self.table.removeRow(row)
        container.deleteLater()
        self.definitions_changed()
        self.fit_content()

    def definitions(self):
        return [container.parts() for container in self.containers]

    def destination_for_song(self):
        title = song_title(self.title_edit.text())
        key = (self.source, title)
        if key != self.destination_key:
            existing = find_song_folder(self.root, self.source, title) if self.root else None
            self.slice_destination = existing or (self.root / 'separated' / title if self.root else None)
            self.destination_confirmed = bool(existing)
            self.destination_key = key
        return self.slice_destination

    def choose_destination(self, override=False):
        if self.running or not self.root or not self.source:
            return False
        suggested = self.destination_for_song()
        if override and suggested.exists():
            base = suggested.name
            number = 2
            while suggested.exists():
                suggested = suggested.with_name(f'{base} {number}')
                number += 1
        try:
            (self.root / 'separated').mkdir(exist_ok=True)
        except OSError as error:
            self.status.setText(f'FOLDER UNAVAILABLE — {error}')
            return False
        dialog = SliceDestinationDialog(self, suggested)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self.slice_destination = dialog.destination()
        self.destination_confirmed = True
        self.definitions_changed()
        self.select_source_song()
        return True

    def definitions_changed(self):
        valid = False
        title = ''
        try:
            title = song_title(self.title_edit.text())
            validate_stems(self.definitions())
            valid = True
        except ValueError:
            pass
        directory = self.destination_for_song() if self.root and title else None
        prefix = 'Existing folder · ' if directory and directory.is_dir() else ('New folder · ' if self.destination_confirmed else 'Suggested folder · ')
        self.destination_label.setText(prefix + str(directory) if directory else 'Choose a song to set its slice folder.')
        self.destination_label.setToolTip(str(directory) if directory else '')
        self.change_destination.setEnabled(bool(directory and self.source and not self.running))
        existing = [p.stem for p in directory.iterdir() if p.suffix.lower() in ('.mp3', '.wav')] if directory and directory.is_dir() else []
        nonempty = [container.parts() for container in self.containers if container.parts()]
        custom = [container.custom_name for container in self.containers if container.parts()]
        name_error = ''
        try:
            names = iter(output_bases(title or 'song', nonempty, existing, custom)) if nonempty else iter([])
        except ValueError as error:
            valid = False
            name_error = str(error)
            names = iter(output_bases(title or 'song', nonempty, existing)) if nonempty else iter([])
        for index, container in enumerate(self.containers, 1):
            container.heading.setText(str(index))
            for name, title_text, _ in PARTS:
                container.checks[name].setAccessibleName(f'Stem {index}: {title_text}')
            container.remove.setAccessibleName(f'Remove stem {index}')
            container.filename.setAccessibleName(f'Output filename for stem {index}')
            if container.parts():
                base = next(names)
                if not name_error:
                    extensions = FORMATS[self.format_combo.currentData()]
                    container.filename.setText(base + extensions[0] if len(extensions) == 1 else base)
            else:
                container.filename.setPlaceholderText('Select instruments')
            container.filename.setToolTip(name_error or 'Click to rename. Leave blank for an automatic name. MP3 + WAV uses the same name for both.')
        if name_error:
            self.status.setText('FILENAME — ' + name_error)
        elif self.status.text().startswith('FILENAME —'):
            self.status.setText('NOT STARTED — define your stems, then choose Create slices.')
        self.start.setEnabled(bool(self.root and self.source and self.source.is_file() and valid and not self.running))
        self.update_midi_actions()
        if self.completed:
            self.completed = False
            self.completed_folder.hide()
            self.progress.hide()
            self.status.setText('NOT STARTED — definitions changed. Previous exports are saved.')

    def open_path(self, path):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self.status.setText(f'Could not open {path}')

    def choose_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose a song', str(self.root / 'Originals'),
                                                  'Audio (*.mp3 *.wav *.flac)')
        if filename:
            self.set_source(Path(filename))

    def set_source(self, path):
        self.source = Path(path)
        self.choose.setItemText(0, self.source.name)
        self.choose.setToolTip(str(self.source))
        self.title_edit.setText(suggested_title(self.source.stem))
        self.definitions_changed()
        self.progress.hide()
        self.completed_folder.hide()
        self.status.setText('NOT STARTED — define your stems, then choose Create slices.')
        self.open_midi.hide()
        self.select_source_song()

    def select_source_song(self):
        if self.source and not self.running:
            try:
                self.refresh_results(self.destination_for_song())
            except ValueError:
                pass

    def start_separation(self):
        if self.running or not self.start.isEnabled():
            return
        self.job_kind = 'stems'
        self.plan = {'title': song_title(self.title_edit.text()), 'format': self.format_combo.currentData(),
                     'stems': validate_stems(self.definitions()),
                     'names': [filename_base(c.filename.text()) for c in self.containers]}
        needs_guitars = any(name in ('lead-guitar', 'rhythm-guitar') for stem in self.plan['stems'] for name in stem)
        python = self.root / '.venv/Scripts/python.exe'
        required = [python, *(self.root / name for name in ('separate_instruments.py', 'export_stems.py', 'recipe_spec.py'))]
        if needs_guitars:
            required.extend(self.root / name for name in ('split_guitars.py',
                            'models/lead-rhythm-demucs/model.ckpt', 'models/lead-rhythm-demucs/config.yaml'))
        missing = [str(path) for path in required if not path.is_file()]
        ffmpeg = shutil.which('ffmpeg') or str(Path('C:/Program Files/ffmpeg/bin/ffmpeg.exe'))
        if not Path(ffmpeg).is_file() or not Path(ffmpeg).with_name('ffprobe.exe').is_file():
            missing.append('FFmpeg and ffprobe')
        if missing:
            self.status.setText('SETUP NEEDED — ' + ', '.join(missing))
            return
        destination = self.destination_for_song()
        if not self.destination_confirmed and not destination.is_dir():
            if not self.choose_destination():
                return
        self.output = self.destination_for_song()
        self.destination_confirmed = True
        token = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        self.run_dir = self.root / 'processing' / token
        try:
            self.output.mkdir(parents=True, exist_ok=True)
            remember_folder(self.root, self.source, self.plan['title'], self.output)
            # The destination dialog may have changed collision suffixes.
            self.definitions_changed()
            self.plan['names'] = [filename_base(c.filename.text()) for c in self.containers]
            self.plan['output'] = str(self.output)
            self.run_dir.mkdir(parents=True)
            (self.run_dir / 'plan.json').write_text(json.dumps(self.plan, indent=2), encoding='utf-8')
            self.log = (self.run_dir / 'processing.log').open('wb')
        except OSError as error:
            self.status.setText(f'FAILED — Could not prepare the slice destination or processing folder: {error}')
            return
        instruments, guitars = self.run_dir / 'instruments', self.run_dir / 'guitars'
        self.commands = [['separate_instruments.py', str(self.source), str(instruments)]]
        self.stage_labels = ['Separating vocals and instruments…']
        if needs_guitars:
            self.commands.append(['split_guitars.py', str(instruments / 'guitar.wav'), str(guitars),
                                  '--model', str(self.root / 'models/lead-rhythm-demucs/model.ckpt'),
                                  '--config', str(self.root / 'models/lead-rhythm-demucs/config.yaml')])
            self.stage_labels.append('Separating lead and rhythm guitar…')
        self.commands.append(['export_stems.py', str(self.source), str(instruments), str(guitars), str(self.output),
                              '--plan', str(self.run_dir / 'plan.json'), '--completion', str(self.run_dir / 'completion.json')])
        self.stage_labels.append('Mixing your stems, exporting, and checking files…')
        self.programs = [str(python)] * len(self.commands)
        self.begin_job(ffmpeg)

    def update_midi_actions(self, *_):
        if not hasattr(self, 'midify'):
            return
        count = len(self.checked_audio())
        self.midify.setText(f'Midify selected ({count})' if count else 'Midify selected')
        self.midify.setEnabled(bool(not self.running and self.root and count))
        self.midi_tempo.setEnabled(not self.running)
        self.midi_instruments.setEnabled(not self.running)
        self.preview.set_files([item['audio'] for item in self.checked_items()])

    def checked_items(self):
        return [self.files.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.files.count())
                if self.files.item(i).checkState() == Qt.CheckState.Checked
                and self.files.item(i).data(Qt.ItemDataRole.UserRole)]

    def checked_audio(self):
        return [item for item in self.checked_items() if Path(item['audio']).suffix.lower() not in MIDI_SUFFIXES]

    def start_midify(self):
        if self.running or not self.root:
            return
        requests = self.checked_audio()
        if not requests:
            return
        if any(not Path(request['audio']).is_file() for request in requests):
            self.status.setText('MISSING AUDIO — a checked file is no longer available. Choose the song again.')
            return
        preset = self.midi_instruments.currentData()
        self.midi_queue = []
        for request in requests:
            groups = (midi_groups_for_parts(request.get('parts')) if preset == 'stem'
                      and not request['original'] else [])
            if groups:
                expected = request.get('recipe_sha256')
                try:
                    with Path(request['audio']).open('rb') as stream:
                        actual = hashlib.file_digest(stream, 'sha256').hexdigest() if expected else None
                except OSError as error:
                    self.status.setText(f'FAILED — Could not verify the checked audio: {error}')
                    self.midi_queue.clear()
                    return
                if not expected or actual != expected:
                    groups = []
            if preset not in ('stem', 'all'):
                groups = list(MIDI_GROUPS[preset])
            self.midi_queue.append({**request, 'instruments': groups})
        self.job_kind = 'midi'
        self.midi_total = len(requests)
        self.midi_done = []
        self.batch_bpm = self.midi_tempo.value()
        self.start_next_midi()

    def start_next_midi(self):
        request = self.midi_queue.pop(0)
        if not self.start_midi_item(request):
            self.finish(self.status.text())

    def start_midi_item(self, request):
        audio = Path(request['audio'])
        original = request['original']
        if not audio or not audio.is_file():
            self.status.setText(f'MISSING AUDIO — {audio}')
            return False
        neural = self.root.parent / 'NeuralNote'
        python = self.root.parent / '.venv/Scripts/python.exe'
        engine = neural / 'cli/build/Release/guitarhacks-transcribe.exe'
        model = neural / 'models/muscriptor-large-f16.gguf'
        writer = neural / 'export_midi.py'
        ffmpeg = shutil.which('ffmpeg') or 'C:/Program Files/ffmpeg/bin/ffmpeg.exe'
        missing = [str(p) for p in (python, engine, model, writer, Path(ffmpeg)) if not p.is_file()]
        if missing:
            self.status.setText('SETUP NEEDED — ' + ', '.join(missing))
            return False
        self.output = Path(request['output'])
        title = self.output.name
        self.job_kind = 'midi'
        self.midi_audio = audio
        token = datetime.now().strftime('%Y%m%d-%H%M%S') + '-midi-' + uuid.uuid4().hex[:6]
        self.run_dir = self.root / 'processing' / token
        try:
            self.run_dir.mkdir(parents=True)
            self.log = (self.run_dir / 'processing.log').open('wb')
        except OSError as error:
            self.status.setText(f'FAILED — Could not create the MIDI processing folder: {error}')
            return False
        raw, notes = self.run_dir / 'audio.f32', self.run_dir / 'notes.tsv'
        basename = song_slug(title) + '-original' if original else audio.stem
        self.commands = [
            ['-hide_banner', '-nostdin', '-v', 'error', '-i', str(audio), '-vn', '-ac', '1', '-ar', '16000', '-f', 'f32le', str(raw)],
            [str(model), str(raw), str(notes)],
            [str(writer), str(notes), str(audio), str(raw), str(self.output), '--name', basename,
             '--bpm', str(self.batch_bpm), '--completion', str(self.run_dir / 'completion.json')],
        ]
        groups = ','.join(request.get('instruments', [])) or 'all'
        self.commands[1].extend(['--instruments', groups])
        self.commands[2].extend(['--instruments', groups])
        self.programs = [ffmpeg, str(engine), str(python)]
        self.stage_labels = ['Preparing audio for MIDI…', 'Transcribing with the Large model…', 'Writing and checking MIDI…']
        self.begin_job(ffmpeg)
        return True

    def begin_job(self, ffmpeg):
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.root))
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PATH', str(Path(ffmpeg).parent) + ';' + env.value('PATH'))
        env.insert('PYTHONUNBUFFERED', '1')
        env.insert('PYTHONIOENCODING', 'utf-8')
        self.process.setProcessEnvironment(env)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.stage_finished)
        self.process.errorOccurred.connect(self.process_error)
        self.running, self.completed, self.cancelled, self.stage = True, False, False, 0
        self.output_buffer = ''
        self.open_midi.hide()
        self.completed_folder.hide()
        self.start.setEnabled(False)
        self.set_editable(False)
        self.cancel.setEnabled(True)
        self.log_button.setEnabled(True)
        self.update_midi_actions()
        self.launch_stage()

    def set_editable(self, editable):
        if not editable:
            self.preview.stop()
        self.preview.setEnabled(editable)
        for widget in (self.choose, self.title_edit, self.change_destination, self.format_combo, self.add_button, self.table, self.results, self.files):
            widget.setEnabled(editable)

    def launch_stage(self):
        prefix = f'MIDIfier · {len(self.midi_done) + 1}/{self.midi_total} · {self.midi_audio.name}' if self.job_kind == 'midi' else 'PROCESSING'
        self.status.setText(f'{prefix} — {self.stage_labels[self.stage]}')
        self.progress.show()
        self.progress.setRange(0, 0)
        self.output_buffer = ''
        self.process.setProgram(self.programs[self.stage])
        self.process.setArguments(self.commands[self.stage])
        self.log.write(('\n' + repr(self.commands[self.stage]) + '\n').encode('utf-8'))
        self.log.flush()
        self.process.start()

    def read_output(self):
        if self.process:
            data = bytes(self.process.readAllStandardOutput())
            if self.log:
                self.log.write(data)
                self.log.flush()
            if self.job_kind == 'midi':
                self.output_buffer += data.decode('utf-8', errors='replace')
                lines = self.output_buffer.split('\n')
                self.output_buffer = lines.pop()
                for line in lines:
                    if line.startswith(('MODEL_PROGRESS ', 'MIDI_PROGRESS ')):
                        try:
                            value = int(line.split()[1])
                        except (ValueError, IndexError):
                            continue
                        self.progress.setRange(0, 100)
                        self.progress.setValue(max(0, min(100, value)))
                        label = 'Loading Large model' if line.startswith('MODEL') else 'Transcribing'
                        self.status.setText(f'MIDIfier · {len(self.midi_done) + 1}/{self.midi_total} · {label} {value}% — {self.midi_audio.name}')

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.finish('FAILED — Could not start the local processing tool. ' + self.process.errorString())

    def stage_finished(self, code, status):
        self.read_output()
        if self.cancelled:
            self.finish('CANCELLED — no completed batch. Your original and previous exports are kept.')
        elif code != 0 or status != QProcess.ExitStatus.NormalExit:
            self.finish('FAILED — open the processing log for details.' + (' Requires stereo 44.1 kHz audio and CUDA.' if self.job_kind == 'stems' else ' MIDI conversion did not complete.'))
        else:
            self.stage += 1
            if self.stage < len(self.commands):
                self.launch_stage()
            else:
                try:
                    result = json.loads((self.run_dir / 'completion.json').read_text(encoding='utf-8'))
                    if not result['files'] or not all((self.output / name).is_file() for name in result['files']):
                        raise ValueError('Exported files are missing')
                except (OSError, ValueError, KeyError) as error:
                    self.finish(f'FAILED — could not verify the completed export: {error}')
                    return
                self.refresh_results(self.output)
                if self.job_kind == 'midi':
                    self.last_midi = self.output / result['files'][0]
                    self.midi_done.append(self.last_midi)
                    if self.midi_queue:
                        self.log.close()
                        self.log = None
                        self.process.deleteLater()
                        self.process = None
                        self.start_next_midi()
                        return
                    self.finish(f'MIDI COMPLETE — {len(self.midi_done)} of {self.midi_total} MIDI files saved in {self.output.name}.', success=True)
                    self.open_midi.show()
                else:
                    self.finish(f"COMPLETE — {result['stem_count']} stems saved. Check items in MIDIfier to convert them.", success=True)

    def finish(self, message, success=False):
        if self.job_kind == 'midi' and not success:
            message += f' {len(self.midi_done)} of {self.midi_total} MIDI files saved; remaining items stopped.'
        self.midi_queue.clear()
        self.running = False
        if self.log:
            self.log.close()
            self.log = None
        if self.process:
            self.process.deleteLater()
            self.process = None
        self.set_editable(True)
        self.definitions_changed()
        self.completed = success
        self.status.setText(message)
        self.progress.hide()
        self.completed_folder.setVisible(success)
        self.cancel.setEnabled(False)
        self.start.setText('Create slices')
        self.update_midi_actions()

    def cancel_separation(self):
        if self.running and self.process:
            self.cancelled = True
            self.cancel.setEnabled(False)
            self.status.setText('CANCELLING…')
            self.process.kill()

    def refresh_results(self, selected=None):
        selected = str(selected or self.results.currentData() or '')
        self.results.blockSignals(True)
        self.results.clear()
        self.saved_files = {}
        self.saved_parts = {}
        self.song_sources = {}
        if self.root:
            folders = {}
            for report in library_reports(self.root):
                try:
                    data = json.loads(report.read_text(encoding='utf-8'))
                    names = data['files']
                    if not names or not all(Path(name).name == name and (report.parent / name).is_file() for name in names):
                        continue
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                key = str(report.parent)
                folders[key] = report.parent.name
                self.saved_files.setdefault(key, set()).update(names)
                if isinstance(names, dict):
                    for name, details in names.items():
                        parts = details.get('instruments') if isinstance(details, dict) else None
                        self.saved_parts.setdefault((key, name), {
                            'parts':parts, 'sha256': details.get('sha256') if isinstance(details, dict) else None})
                # Stem manifests identify the original. MIDI manifests for a stem
                # point inside the song folder and must never replace it.
                source = Path(data['source']) if data.get('source') else None
                if source and source.parent != report.parent and key not in self.song_sources:
                    self.song_sources[key] = source
            if self.source:
                try:
                    title = song_title(self.title_edit.text())
                    key = str(self.destination_for_song())
                    folders[key] = Path(key).name
                    existing = self.song_sources.get(key)
                    if not existing or not existing.is_file():
                        self.song_sources[key] = self.source
                except ValueError:
                    pass
            for path, title in folders.items():
                self.results.addItem(title, path)
        index = self.results.findData(selected)
        if index >= 0:
            self.results.setCurrentIndex(index)
        self.results.blockSignals(False)
        self.show_result()

    def show_result(self):
        checked = {item['audio'] for item in self.checked_items()}
        self.files.blockSignals(True)
        self.files.clear()
        directory = self.results.currentData()
        self.open_result.setEnabled(bool(directory and Path(directory).is_dir()))
        original = getattr(self, 'song_sources', {}).get(directory)
        original_text = '1 · ORIGINAL — Whole song\nAll vocals and instruments'
        if original:
            original_text += ' · ' + original.name
        else:
            original_text += ' · Choose the original audio above'
        self.add_midi_choice(original_text, original, directory, True, checked)
        for name in sorted(getattr(self, 'saved_files', {}).get(directory, ())):
            if Path(name).suffix.lower() in ('.mp3', '.wav', '.flac'):
                recipe = self.saved_parts.get((directory, name), {})
                self.add_midi_choice('STEM · ' + name, Path(directory) / name, directory, False, checked,
                                     recipe.get('parts'), recipe.get('sha256'))
        for name in sorted(getattr(self, 'saved_files', {}).get(directory, ())):
            if Path(name).suffix.lower() in MIDI_SUFFIXES:
                self.add_midi_choice('MIDI · ' + name, Path(directory) / name, directory, False, checked)
        self.files.blockSignals(False)
        self.update_midi_actions()
        self.fit_content()

    def add_midi_choice(self, text, audio, directory, original, checked, parts=None, recipe_sha256=None):
        item = QListWidgetItem(text)
        available = bool(audio and directory and audio.is_file())
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | (Qt.ItemFlag.ItemIsEnabled if available else Qt.ItemFlag.NoItemFlags))
        item.setCheckState(Qt.CheckState.Checked if available and str(audio) in checked else Qt.CheckState.Unchecked)
        item.setSizeHint(QSize(0, 48 if original else 30))
        if original:
            item.setBackground(QColor('#243b37'))
            item.setForeground(QColor(MINT))
            font = item.font(); font.setBold(True); item.setFont(font)
        if available:
            item.setData(Qt.ItemDataRole.UserRole, {'audio': str(audio), 'output': str(directory), 'original': original,
                                                  'parts': parts, 'recipe_sha256': recipe_sha256})
        item.setToolTip(str(audio) if audio else 'Choose the original audio file for this song.')
        self.files.addItem(item)

    def fit_content(self):
        # Only allocate space for actual rows; scroll once the screen is full.
        if not hasattr(self, 'files'):
            return
        row_height = self.table.verticalHeader().defaultSectionSize()
        table_height = self.table.horizontalHeader().height() + self.table.rowCount() * row_height + 2 * self.table.frameWidth()
        if self.table.horizontalScrollBar().isVisible():
            table_height += self.table.horizontalScrollBar().sizeHint().height()
        screen_height = self.screen().availableGeometry().height()
        self.table.setFixedHeight(min(table_height, max(180, min(340, screen_height - 550))))
        count = self.files.count()
        self.files.setVisible(count > 0)
        items_height = sum(max(self.files.sizeHintForRow(i), 18) for i in range(count))
        self.files.setFixedHeight(min(items_height + 2 * self.files.frameWidth(), 170))
        # Let rows increase the window's minimum height instead of overlapping controls.
        self.setMinimumHeight(self.layout().minimumSize().height())
        window = self.window()
        if self.isVisible() and window is not self and window.height() < self.minimumHeight():
            window.resize(window.width(), self.minimumHeight())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_content()

    def open_selected(self):
        if self.results.currentData():
            self.open_path(Path(self.results.currentData()))

    def reveal_midi(self):
        if hasattr(self, 'last_midi') and self.last_midi.is_file():
            QProcess.startDetached('explorer.exe', ['/select,', str(self.last_midi)])



