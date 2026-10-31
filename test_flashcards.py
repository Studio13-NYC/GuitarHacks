"""Integration tests use generated audio and an isolated learner database."""
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import threading
import ctypes

import numpy as np
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from app import MainWindow, SettingsPanel, STYLE
from audio import Capture, PitchTracker
from lessons import Card, Lesson, load_lessons
from practice import Store
from session import Session
from cues import CuePlayer

ROOT = Path(__file__).resolve().parent
CARD = dict(id="c-on-a", prompt="C", instruction="A string · frets 1–12",
            hint="A string, fret 3", midi=48, match="exact")


def document(**changes):
    doc = dict(version=1, id="test-notes", title="Test notes", description="Test signal only", cards=[CARD.copy()])
    doc.update(changes)
    return doc


def wave(midi, cents=0):
    t = np.arange(4096)/48000
    hz = 440*2**((midi-69+cents/100)/12)
    return .18*(np.sin(2*np.pi*hz*t)+.35*np.sin(4*np.pi*hz*t))


class LessonTests(unittest.TestCase):
    def test_builtin_note_targets_match_physical_frets(self):
        lessons, errors = load_lessons(ROOT/"FretboardFiend"/"lessons")
        self.assertEqual(errors, [])
        self.assertEqual([len(l.cards) for l in lessons], [42,102,17,108,288])
        opens = {6:40,5:45,4:50,3:55,2:59,1:64}
        pcs = {"C":0,"C♯":1,"D♭":1,"D":2,"D♯":3,"E♭":3,"E":4,"F":5,
               "F♯":6,"G♭":6,"G":7,"G♯":8,"A♭":8,"A":9,"A♯":10,"B♭":10,"B":11}
        for lesson in lessons[:2]:
            for card in lesson.cards:
                string = int(card.id.rsplit("-",1)[1])
                self.assertEqual(card.midi%12, pcs[card.prompt.splitlines()[0].removeprefix("Play ")])
                self.assertEqual(card.string,string)
                self.assertTrue(1 <= card.midi-opens[string] <= 12)
                if card.midi-opens[string] == 12:
                    self.assertIn("One octave above",card.instruction)
        for lesson in lessons[3:]:
            for card in lesson.cards:
                higher = card.midi-opens[card.string] >= 12
                self.assertEqual("One octave above" in card.instruction,higher)
        self.assertEqual(len({c.key for l in lessons for c in l.cards}), 557)

    def test_custom_lesson_loads_without_core_changes_and_bad_files_reported(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"build") as folder:
            path = Path(folder)
            (path/"custom.json").write_text(json.dumps(document()), encoding="utf-8")
            (path/"broken.json").write_text('{"version": 2}', encoding="utf-8")
            lessons, errors = load_lessons(path)
            self.assertEqual(len(lessons), 1)
            self.assertEqual(len(errors), 1)
            for bad in [True,39,77,"48"]:
                card = dict(CARD, midi=bad)
                (path/"custom.json").write_text(json.dumps(document(cards=[card])), encoding="utf-8")
                self.assertEqual(len(load_lessons(path)[0]), 0)
            (path/"custom.json").write_text(json.dumps(document(cards=[CARD,CARD])), encoding="utf-8")
            self.assertIn("Duplicate card", " ".join(load_lessons(path)[1]))


class AudioTests(unittest.TestCase):
    def test_quiet_pitched_noise_and_short_loud_bursts_are_not_answers(self):
        tracker = PitchTracker()
        for _ in range(4): tracker.process(np.zeros(4096),48000)
        # The live tuner may observe a quiet tone, but it must not become an answer.
        tone = wave(48)
        weak = tone / np.sqrt(np.mean(tone*tone)) * 10**(-40/20)
        for _ in range(12):
            frame, pitch = tracker.process(weak,48000)
            self.assertIsNone(pitch)
            self.assertFalse(frame['analyzing'])
            self.assertEqual(frame['raw_pitch']['midi'], 48)
        for _ in range(4): tracker.process(np.zeros(4096),48000)
        for _ in range(5):
            self.assertIsNone(tracker.process(tone,48000)[1])
        for _ in range(4): tracker.process(np.zeros(4096),48000)
        emitted = [tracker.process(tone,48000)[1] for _ in range(8)]
        self.assertEqual(len([p for p in emitted if p]),1)

    def test_note_must_follow_quiet_and_can_vary_inside_quarter_semitone(self):
        tracker = PitchTracker()
        for _ in range(10):
            self.assertIsNone(tracker.process(wave(48),48000)[1])
        for _ in range(4): tracker.process(np.zeros(4096),48000)
        emitted=[]
        for cents in [-20,20,-20,20,-20,20,0,0]:
            _, pitch=tracker.process(wave(48,cents),48000)
            if pitch:emitted.append(pitch)
        self.assertEqual(len(emitted),1)
        self.assertEqual(emitted[0]['midi'],48)

    def test_stability_silence_noise_overflow_and_retrigger(self):
        tracker = PitchTracker()
        for _ in range(4):
            tracker.process(np.zeros(4096),48000)
        for _ in range(5):
            self.assertIsNone(tracker.process(wave(48),48000)[1])
        self.assertEqual(tracker.process(wave(48),48000)[1]["midi"],48)
        self.assertIsNone(tracker.process(wave(48),48000)[1])
        for _ in range(4):
            frame, _ = tracker.process(np.zeros(4096),48000)
        self.assertTrue(frame["quiet"])
        for _ in range(5):
            self.assertIsNone(tracker.process(wave(48),48000)[1])
        self.assertIsNotNone(tracker.process(wave(48),48000)[1])
        for samples, overflow in [(np.ones(4096),False), (wave(50),True),
                                   (np.random.default_rng(3).normal(0,.1,4096),False)]:
            for _ in range(8):
                self.assertIsNone(tracker.process(samples,48000,overflow)[1])

    def test_full_supported_range_and_strong_harmonic(self):
        t = np.arange(4096)/48000
        for midi in range(40,79):
            f = 440*2**((midi-69)/12)
            signal = .1*(.25*np.sin(2*np.pi*f*t)+np.sin(4*np.pi*f*t)+.4*np.sin(6*np.pi*f*t))
            tracker = PitchTracker()
            for _ in range(4): tracker.process(np.zeros(4096),48000)
            for _ in range(6):
                _, pitch = tracker.process(signal,48000)
            self.assertIsNotNone(pitch, midi)
            self.assertEqual(pitch["midi"], midi)


class SessionTests(unittest.TestCase):
    def test_string_reference_moves_answer_center_but_not_tolerance(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"build") as folder:
            store=Store(folder)
            c=Card("test","ref-c","C","A string","fret 3",48,string=5)
            s=Session(store,clock=lambda:14)
            lesson=Lesson("test","Test","",(c,))
            s.start(lesson,now=10,reference_cents={5:40,6:-20},size=1)
            s.frame(dict(quiet=True,monotonic=11))
            p=dict(midi=48,cents=0,periodicity=.99,started=12)
            self.assertEqual(s.note(p),"tuning")  # 40 cents below the measured A-string reference
            self.assertEqual(store.total(),0)
            s.frame(dict(quiet=True,monotonic=13))
            self.assertEqual(s.note(dict(p,cents=40,started=14)),"correct")
            self.assertEqual(store.total(),1)
            store.close()

    def test_stale_audio_octaves_pause_and_persistence(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"build") as folder:
            store = Store(folder)
            s = Session(store,clock=lambda:14)
            c = Card("test", "c", "C", "A string", "fret 3", 48)
            s.start(Lesson("test","Test","",(c,)), now=10,size=1)
            p = dict(midi=48, periodicity=.99, cents=0, started=11)
            s.frame(dict(quiet=True, monotonic=9))
            self.assertEqual(s.note(p), "ignored")
            s.frame(dict(quiet=True, monotonic=11))
            self.assertEqual(s.note(dict(p,started=9)), "ignored")
            self.assertEqual(s.note(dict(p,midi=60)), "octave")
            self.assertEqual(s.judge.misses,0)
            s.frame(dict(quiet=True, monotonic=12))
            self.assertEqual(s.note(dict(p,midi=50)),"retry")
            self.assertEqual(s.note(dict(p,midi=50)),"ignored")
            s.frame(dict(quiet=True, monotonic=13))
            s.hint()
            self.assertEqual(s.note(p),"correct")
            self.assertEqual(store.total(),1)
            s.pause()
            self.assertEqual(s.note(p),"ignored")
            store.close()
            store=Store(folder)
            self.assertEqual(store.recent()[0][2:], ("assisted",1))
            s=Session(store,clock=lambda:14)
            c=Card("test","any-c","C","Anywhere","",48,"pitch_class")
            s.start(Lesson("test","Test","",(c,)),now=10,size=1)
            s.frame(dict(quiet=True,monotonic=11))
            self.assertEqual(s.note(dict(p,midi=60)),"correct")
            store.close()


class CaptureTests(unittest.TestCase):
    def test_worker_has_windows_com_apartment_before_opening_audio(self):
        # Without COM on the actual worker, WASAPI fails even when the device is free.
        apartments = []
        def open_stream(**kwargs):
            kind, qualifier = ctypes.c_int(), ctypes.c_int()
            hr = ctypes.WinDLL("ole32").CoGetApartmentType(ctypes.byref(kind), ctypes.byref(qualifier))
            apartments.append((hr, kind.value))
            raise RuntimeError("End probe before opening hardware")
        device = dict(name="QA", index=0, max_input_channels=2, default_samplerate=48000)
        with patch("audio.input_devices", return_value=[device]), patch("audio.sd.InputStream", side_effect=open_stream):
            capture = Capture("QA", 0, -45)
            capture.start()
            self.assertTrue(capture.wait(2000))
        self.assertEqual(apartments, [(0, 1)], "Capture must initialize a multithreaded COM apartment")

    def test_no_callback_input_can_be_stopped_and_is_closed(self):
        started = threading.Event()
        class SilentStream:
            closed = False
            aborted = False
            def start(self): started.set()
            def abort(self): self.aborted = True
            def close(self): self.closed = True
        stream = SilentStream()
        device = dict(name="QA", index=0, max_input_channels=2, default_samplerate=48000)
        with patch("audio.input_devices", return_value=[device]), patch("audio.sd.InputStream", return_value=stream):
            capture = Capture("QA", 0, -45)
            capture.start()
            try:
                self.assertTrue(started.wait(2))
            finally:
                capture.stop()
                self.assertTrue(capture.wait(2000))
            self.assertTrue(stream.aborted)
            self.assertTrue(stream.closed)

    def test_failed_start_closes_stream_even_if_abort_fails(self):
        class FailedStream:
            closed = False
            def start(self): raise RuntimeError("Input busy")
            def abort(self): raise RuntimeError("Already stopped")
            def close(self): self.closed = True
        stream = FailedStream()
        device = dict(name="QA", index=0, max_input_channels=2, default_samplerate=48000)
        with patch("audio.input_devices", return_value=[device]), patch("audio.sd.InputStream", return_value=stream):
            capture = Capture("QA", 0, -45)
            errors = []
            capture.failed.connect(errors.append, Qt.ConnectionType.DirectConnection)
            capture.start()
            self.assertTrue(capture.wait(2000))
            self.assertTrue(errors)
            self.assertTrue(stream.closed)


class SyntheticCapture(QObject):
    opened = Signal(str)
    frame = Signal(dict)
    note = Signal(dict)
    failed = Signal(str)
    finished = Signal()

    def __init__(self,name,channel,gate,parent=None):
        super().__init__(parent)
        self.name, self.channel, self.running = name, channel, False
        self.tracker = PitchTracker(gate)

    def start(self):
        self.running=True
        self.opened.emit(self.name)

    def stop(self):
        self.running=False
        self.finished.emit()

    def wait(self,ms):
        return True

    def set_gate(self,gate):
        if gate != self.tracker.gate:
            self.tracker = PitchTracker(gate, self.tracker.hold_seconds)

    def set_hold_seconds(self,value):
        self.tracker = PitchTracker(self.tracker.gate, value)

    def reset_detection(self):
        self.tracker = PitchTracker(self.tracker.gate, self.tracker.hold_seconds)

    def play(self, samples, count=6):
        for _ in range(count):
            frame, pitch = self.tracker.process(samples,48000)
            self.frame.emit(frame)
            if pitch:
                self.note.emit(pitch)


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def test_fresh_app_selects_board_main_mix(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"build") as folder:
            devices = [dict(name="M12 In 5/6 - Guitar-DI", max_input_channels=2),
                       dict(name="M12 In 11/12 - Main Mix", max_input_channels=2)]
            with patch("app.input_devices", return_value=devices):
                w = MainWindow(Path(folder), ROOT/"lessons", SyntheticCapture)
                try:
                    self.assertEqual(w.settings["input"], "M12 In 11/12 - Main Mix")
                    self.assertEqual(w.settings["channel"], 0)
                finally:
                    w.close()

    def test_real_widgets_calibration_countdown_attempts_gap_quit_and_restart(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            path=Path(folder)
            w=MainWindow(path/'data',ROOT/'lessons',SyntheticCapture)
            try:
                w.settings.update(input='QA generated audio',channel=0,cues=False)
                w.splash_timer.stop()
                w.show_setup()
                w.show()
                QTest.qWait(20)
                QTest.mouseClick(w.mode_buttons[3],Qt.MouseButton.LeftButton)
                self.assertTrue(w.note_box.isVisible())
                self.assertTrue(w.string_box.isVisible())
                w.note_combo.setCurrentIndex(0)
                w.string_combo.setCurrentIndex(w.string_combo.findData(5))
                w.seconds_spin.setValue(25)
                w.attempts_spin.setValue(4)
                QTest.mouseClick(w.start_button,Qt.MouseButton.LeftButton)
                capture=w.capture
                self.assertEqual(w.prompt.text(),'Mute strings')
                capture.play(np.zeros(4096),16)
                for midi in [40,45,50,55,59,64]:
                    capture.play(np.zeros(4096),4)
                    capture.play(wave(midi),6)
                    self.assertEqual(w.transition,'result')
                    before=len(w.calibration.readings)
                    capture.play(np.zeros(4096),4)
                    capture.play(wave(midi+5),6)
                    self.assertEqual(len(w.calibration.readings),before)
                    w.next_timer.stop()
                    w.advance_step()
                    self.assertEqual(w.prompt.text(),'*')
                    w.next_timer.stop()
                    w.advance_step()
                self.assertIsNone(w.calibration)
                self.assertEqual(w.prompt.text(),'C')
                self.assertEqual(w.instruction.text(),'A string')
                self.assertFalse(w.total.isVisible())
                self.assertFalse(w.progress.isVisible())
                self.assertEqual(w.countdown.text(),'00:25')
                self.assertEqual(w.attempt_display.text(),'Attempts\n0/4')
                capture.play(wave(48))
                self.assertEqual(w.session.attempts,0)
                capture.play(np.zeros(4096))
                capture.play(wave(50))
                self.assertEqual(w.session.attempts,1)
                self.assertIn('#ff606b',w.prompt.styleSheet())
                capture.play(np.zeros(4096))
                capture.play(wave(48))
                self.assertEqual(w.session.attempts,2)
                self.assertEqual(w.store.total(),1)
                self.assertIn('#83ed9e',w.prompt.styleSheet())
                self.assertEqual(w.transition,'result')
                QTest.qWait(1100)
                self.assertEqual(w.prompt.text(),'*')
                self.assertFalse(w.countdown.isVisible())
                self.assertFalse(w.attempt_display.isVisible())
                self.assertTrue(w.total.isVisible())
                self.assertEqual(w.progress.text(),'11/12 Left')
                capture.play(np.zeros(4096))
                capture.play(wave(48))
                self.assertEqual(w.store.total(),1)
                QTest.qWait(2100)
                self.assertEqual(w.prompt.text(),'C')
                self.assertFalse(w.session.judge.armed)
                w.session.started=time.monotonic()-22.1
                w.tick()
                self.assertEqual(w.countdown.text(),'00:03')
                self.assertIn('#ff9f32',w.prompt.styleSheet())
                self.assertIn('#ff9f32',w.countdown.styleSheet())
                w.resize(720,640)
                QTest.qWait(20)
                small=w.prompt.font().pixelSize()
                w.resize(1600,1000)
                QTest.qWait(20)
                self.assertGreater(w.prompt.font().pixelSize(),small)
                w.full_screen()
                self.assertTrue(w.isFullScreen())
                w.exit_full_screen()
                QTest.mouseClick(w.quit_button,Qt.MouseButton.LeftButton)
                self.assertFalse(capture.running)
                self.assertTrue(w.closed)
            finally:
                if not w.closed:w.close()
            reopened=MainWindow(path/'data',ROOT/'lessons',SyntheticCapture)
            try:
                self.assertEqual(reopened.store.total(),12)
                self.assertEqual(reopened.seconds_spin.value(),25)
                self.assertEqual(reopened.attempts_spin.value(),4)
                rows=reopened.store.connection.execute('SELECT outcome,attempt_count,shown FROM attempts ORDER BY id').fetchall()
                self.assertEqual(rows[0],('assisted',2,1))
                self.assertEqual(rows[1],('skipped',0,1))
                self.assertTrue(all(row==('skipped',0,0) for row in rows[2:]))
            finally:reopened.close()

    def test_missing_saved_device_is_not_replaced(self):
        dialog=SettingsPanel(dict(input="Disconnected QA input",channel=0),ROOT/"lessons")
        self.assertIsNone(dialog.device.currentData())
        self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled())
        dialog.close()

    def test_completion_cue_is_optional_and_quiet(self):
        import wave as wav
        with tempfile.TemporaryDirectory(dir=ROOT/"build") as folder:
            w=MainWindow(Path(folder),ROOT/"lessons",SyntheticCapture)
            try:
                with patch("cues.winsound.PlaySound") as play:
                    w.play_cue()
                    play.assert_called_once()
                    with wav.open(str(w.cue.path),"rb") as source:
                        self.assertLess(source.getnframes()/source.getframerate(),.25)
                        samples=np.frombuffer(source.readframes(source.getnframes()),dtype="<i2")
                        self.assertLess(np.max(np.abs(samples))/32767,.06)
                    w.settings["cues"]=False
                    w.play_cue()
                    play.assert_called_once()
            finally:
                w.close()


if __name__ == "__main__":
    (ROOT/"build").mkdir(exist_ok=True)
    unittest.main()
