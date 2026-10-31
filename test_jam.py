"""MIDI round trips and real recording widgets with isolated learner data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import mido
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QObject, Signal
from jam_midi import MidiTake, resolve_port, decode_ump
from jam_view import JamPage
from practice import Store


class TakeTests(unittest.TestCase):
    def test_chord_timing_expression_and_stop_release_survive_midi_round_trip(self):
        take = MidiTake(90, clock=lambda: 100)
        for note in (48, 52, 55):
            take.feed(mido.Message('note_on', note=note, velocity=80), 100.5)
        take.feed(mido.Message('pitchwheel', pitch=512), 100.7)
        take.feed(mido.Message('note_on', note=48, velocity=0), 101)
        take.stop(101.5)
        self.assertEqual([n.duration for n in take.notes], [.5, 1, 1])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'take.mid'
            take.save(path)
            midi = mido.MidiFile(path)
            self.assertAlmostEqual(midi.length, 1.5, places=2)
            onsets = [m for m in midi.tracks[1] if m.type == 'note_on' and m.velocity]
            self.assertEqual([m.note for m in onsets], [48, 52, 55])
            self.assertEqual([m.time for m in onsets], [360, 0, 0])
            self.assertTrue(any(m.type == 'pitchwheel' and m.pitch == 512 for m in midi.tracks[1]))
            self.assertEqual(len([m for m in midi.tracks[1] if m.type == 'note_off']), 2)

    def test_repeated_pitch_and_panic_release(self):
        take = MidiTake(clock=lambda: 0)
        take.feed(mido.Message('note_on', note=60), .1)
        take.feed(mido.Message('note_on', note=60), .3)
        take.feed(mido.Message('control_change', control=123), .5)
        take.stop(1)
        self.assertEqual(len(take.active), 0)
        self.assertAlmostEqual(take.notes[0].duration, .2)
        self.assertAlmostEqual(take.notes[1].duration, .2)

    def test_only_exact_or_unique_named_port_is_selected(self):
        self.assertEqual(resolve_port(['GuitarHacks Jam Receive 8']), 'GuitarHacks Jam Receive 8')
        self.assertIsNone(resolve_port(['Model 12 MIDI 0']))
        self.assertIsNone(resolve_port(['GuitarHacks Jam 8'], 'My saved input'))
        self.assertIsNone(resolve_port(['GuitarHacks Jam 8', 'GuitarHacks Jam 9']))

    def test_midi2_preserves_note_on_zero_velocity_and_reports_loss(self):
        group, message, warning = decode_ump([0x41903c00, 0])
        self.assertEqual(group, 1)
        self.assertEqual(message.type, 'note_on')
        self.assertEqual(message.velocity, 1)
        self.assertIn('resolution', warning)
        self.assertIsNone(decode_ump([0x40603c00, 0x80000000])[1])
        self.assertIn('original-data', decode_ump([0x40603c00, 0x80000000])[2])

    def test_groups_stay_separate_and_stop_releases_sustain(self):
        take = MidiTake(clock=lambda: 0)
        for group in (0, 1):
            take.feed(mido.Message('note_on', note=60), .1, group)
        for group in (0, 1):
            take.feed(mido.Message('control_change', control=64, value=127), .2, group)
        take.feed(mido.Message('note_off', note=60), .4, 0)
        take.stop(.6)
        self.assertAlmostEqual(take.notes[1].duration, .5)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'group.mid'
            take.save(path)
            tracks = mido.MidiFile(path).tracks
            self.assertEqual(len(tracks), 3)
            for track in tracks[1:]:
                self.assertTrue(any(m.type == 'control_change' and m.control == 64 and m.value == 0 for m in track))


class FakePort(QObject):
    event = Signal(dict)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.closed = False
        self.now = 1000000

    def start(self):
        self.event.emit(dict(type='ready', timestamp=self.now, frequency=10000, endpoint='test'))

    def send(self, command):
        self.event.emit(dict(type=command, timestamp=self.now))

    def message(self, message, ticks=100):
        self.now += ticks
        data = message.bytes() + [0, 0]
        word = 0x20000000 | (data[0] << 16) | (data[1] << 8) | data[2]
        self.event.emit(dict(type='midi', timestamp=self.now, words=[word]))

    def close(self):
        self.send('stop')
        self.closed = True


class JamWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(self.folder.name)
        self.backend = patch('jam_view.WindowsMidiInput', FakePort)
        self.backend.start()
        self.page = JamPage(self.store, lambda: None)
        self.page.show()

    def tearDown(self):
        self.page.disconnect()
        self.page.close()
        self.store.close()
        self.backend.stop()
        self.folder.cleanup()

    def connect(self):
        QTest.mouseClick(self.page.connect_button, Qt.MouseButton.LeftButton)
        self.port = self.page.port

    def test_record_notes_stop_and_reopen_saved_take(self):
        self.connect()
        QTest.mouseClick(self.page.record_button, Qt.MouseButton.LeftButton)
        self.port.message(mido.Message('note_on', note=64, velocity=90))
        QTest.qWait(35)
        self.assertIn('E4', self.page.live.text())
        self.port.message(mido.Message('note_off', note=64))
        QTest.mouseClick(self.page.record_button, Qt.MouseButton.LeftButton)
        path = Path(self.page.takes.currentData())
        self.assertTrue(path.is_file())
        self.assertEqual(len([m for m in mido.MidiFile(path).tracks[1] if m.type=='note_on']), 1)
        self.assertTrue(self.page.open_gp.isEnabled())
        self.assertIsNone(self.page.take)

    def test_disconnect_closes_held_notes_and_saves(self):
        self.connect()
        self.page.toggle_recording()
        self.port.message(mido.Message('note_on', note=40))
        self.page.poll()
        self.page.disconnect()
        self.assertTrue(self.port.closed)
        self.assertTrue(Path(self.page.takes.currentData()).is_file())
        self.assertFalse(self.page.record_button.isEnabled())

    def test_no_notes_creates_no_take_and_save_failure_retains_take(self):
        self.connect()
        self.page.toggle_recording()
        self.page.toggle_recording()
        self.assertEqual(self.page.takes.count(), 0)
        self.page.toggle_recording()
        self.port.message(mido.Message('note_on', note=55))
        self.page.poll()
        with patch.object(MidiTake, 'save', side_effect=OSError('disk full')):
            self.page.toggle_recording()
        self.assertIsNotNone(self.page.pending_save)
        self.assertEqual(self.page.record_button.text(), 'Retry save')
        self.page.disconnect()
        self.assertEqual(self.page.record_button.text(), 'Retry save')
        self.assertTrue(self.page.record_button.isEnabled())
        self.page.toggle_recording()
        self.assertIsNone(self.page.pending_save)
        self.assertEqual(self.page.takes.count(), 1)

    def test_guitar_pro_handoff_copies_path_for_supported_import(self):
        path = self.page.directory / 'test take.mid'
        path.touch()
        self.page.refresh_takes(path)
        with patch('jam_view.Path.is_file', return_value=True), patch('jam_view.subprocess.Popen') as launch:
            self.page.open_in_guitar_pro()
        self.assertEqual(QApplication.clipboard().text(), str(path.resolve()))
        self.assertEqual(len(launch.call_args.args[0]), 1)
        self.assertIn('File → Import → MIDI', self.page.status.text())

    def test_source_clock_and_original_data_survive_delayed_delivery(self):
        self.connect()
        self.page.toggle_recording()
        self.port.message(mido.Message('note_on', note=60), ticks=2500)
        self.port.message(mido.Message('pitchwheel', pitch=400), ticks=1000)
        self.port.message(mido.Message('note_off', note=60), ticks=4000)
        self.page.toggle_recording()
        path = Path(self.page.takes.currentData())
        self.assertAlmostEqual(mido.MidiFile(path).length, .75, places=2)
        raw = json.loads(path.with_suffix('.ump.json').read_text())
        self.assertEqual(raw['metadata']['startTimestamp'], 1000000)
        self.assertEqual(raw['events'][0]['timestamp'], 1002500)
        self.assertEqual(len(raw['events']), 3)

    def test_controller_setup_retained_and_receiver_failure_marks_partial_take(self):
        self.connect()
        for control, value in ((101, 0), (100, 0), (6, 12)):
            self.port.message(mido.Message('control_change', control=control, value=value))
        self.page.toggle_recording()
        self.port.message(mido.Message('note_on', note=60))
        self.port.failed.emit('test disconnection')
        QTest.qWait(20)
        path = Path(self.page.takes.currentData())
        raw = json.loads(path.with_suffix('.ump.json').read_text())
        self.assertEqual(sum(e.get('initialState', False) for e in raw['events']), 3)
        self.assertTrue(any('Incomplete' in w for w in raw['warnings']))
        self.assertIsNone(self.page.port)
        self.assertFalse(self.page.record_button.isEnabled())


if __name__ == '__main__':
    unittest.main()
