"""Exercise the real embedded surface with generated input, never the user's input."""
import json
import os
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
import tempfile
import time
import unittest
from pathlib import Path
import numpy as np
from test_flashcards import QApplication, QTest
from PySide6.QtCore import QObject, Signal
from painter_view import PainterView
from audio import PitchTracker

ROOT = Path(__file__).resolve().parent


class TestCapture(QObject):
    opened = Signal(str)
    frame = Signal(dict)
    note = Signal(dict)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, name, channel, gate, parent):
        super().__init__(parent)
        self.gate=gate;self.hold=.3;self.stopped=False
        self.tracker=PitchTracker(gate, self.hold)
        self.now=time.monotonic()
    def set_gate(self, gate): self.gate=gate
    def set_hold_seconds(self, hold): self.hold=hold;self.reset_detection()
    def reset_detection(self): self.tracker=PitchTracker(self.gate, self.hold)
    def start(self): self.opened.emit('Generated QA only')
    def stop(self): self.stopped=True
    def wait(self, timeout): return True
    def send(self, x):
        self.now+=len(x)/48000
        frame,pitch=self.tracker.process(x,48000,now=self.now)
        self.frame.emit(frame)
        if pitch:self.note.emit(pitch)
    def quiet(self, n=16):
        for _ in range(n):self.send(np.zeros(4096))
    def tone(self, midi, n=10):
        x=.15*np.sin(2*np.pi*(440*2**((midi-69)/12))*np.arange(4096)/48000)
        for _ in range(n):self.send(x)


class PainterListeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'build')
        self.settings=dict(input='Generated QA only',channel=0,gate=-40,hold_seconds=.3)
        self.open_view()

    def open_view(self, show=True):
        self.view=PainterView(self.temp.name,ROOT,settings=lambda:self.settings,capture_factory=TestCapture,voice_factory=False)
        self.view.resize(1360,1100)
        if show:self.view.show()
        for _ in range(150):
            if self.js("document.documentElement.dataset.ready==='true'"):break
            QTest.qWait(20)
        else:self.fail('Painter did not become ready')

    def tearDown(self):
        self.view.shutdown();self.view.close();QTest.qWait(50);self.temp.cleanup()

    def js(self, code):
        values=[]
        self.view.page.runJavaScript(code,lambda value:values.append(value))
        for _ in range(150):
            if values:return values[0]
            QTest.qWait(20)
        self.fail('JavaScript callback timed out')

    def choose_play(self,paint=True):
        if paint:self.js("document.querySelector('[data-mode=paint]').click()")
        self.js("document.getElementById('input-mode').value='play';document.getElementById('input-mode').dispatchEvent(new Event('change'))")
        QTest.qWait(80)
        return self.view.listener.capture

    def calibrate(self,paint=True):
        capture=self.choose_play(paint)
        self.assertIsNotNone(capture)
        self.assertTrue(self.js("document.getElementById('start').disabled"))
        capture.quiet(20)
        for midi in [40,45,50,55,59,64]:capture.tone(midi);capture.quiet(8)
        QTest.qWait(100)
        self.assertTrue(self.view.listener.calibrated)
        self.assertFalse(capture.stopped)
        self.assertFalse(self.js("document.getElementById('start').disabled"))
        return capture

    def begin(self):
        capture=self.calibrate()
        self.view.listener.command.emit('go');QTest.qWait(80)
        capture.quiet(8);capture.tone(40,3);capture.quiet(8)
        QTest.qWait(80)
        self.assertEqual(self.view.listener.pass_.stage,'strings')
        return capture

    def test_generated_capture_calibration_go_review_next_and_quit(self):
        capture=self.begin()
        self.assertTrue(self.js("document.getElementById('submit-paint').disabled"))
        for midi in [40,47,52,56,59,64]:capture.tone(midi);capture.quiet(8)
        QTest.qWait(100)
        self.assertEqual(self.view.listener.pass_.frets,[0,2,2,1,0,0])
        self.assertFalse(capture.stopped)
        self.assertTrue(self.js("!document.getElementById('submit-paint').disabled"))
        self.assertEqual(self.js("document.getElementById('attempts').textContent"),'0 / 3')
        self.assertEqual(self.js("document.querySelectorAll('.dot').length"),3)
        # Review edits are not overwritten by subsequent monitoring frames.
        self.js("document.querySelector('[data-string=\"0\"][data-fret=\"1\"]').click()")
        capture.quiet(8);QTest.qWait(60)
        self.assertTrue(self.js("document.querySelector('[data-string=\"0\"][data-fret=\"1\"]').getAttribute('aria-pressed')==='true'"))
        # Complete this unscored question via ordinary UI, then spoken Next starts capture.
        self.js("document.getElementById('reveal').click()")
        self.view.listener.command.emit('next');QTest.qWait(80)
        self.assertEqual(self.view.listener.pass_.stage,'strum')
        self.assertTrue(self.js("document.getElementById('submit-paint').disabled"))
        self.view.listener.command.emit('quit');QTest.qWait(80)
        self.assertTrue(capture.stopped)
        self.assertFalse(self.view.listener.active)
        self.assertEqual(self.js("document.getElementById('correct-total').textContent"),'0')
        self.assertFalse((Path(self.temp.name)/'chord-painter.json').exists())

    def test_auto_muted_hidden_labels_and_navigation_stops_idle_capture(self):
        capture=self.begin()
        self.js("document.getElementById('show-notes').click();document.getElementById('show-intervals').click();")
        capture.tone(40,2);QTest.qWait(60)
        heard=self.js("document.getElementById('listen-heard').textContent")
        self.assertNotIn('Hz',heard);self.assertNotIn('E2',heard);self.assertNotIn('interval',heard)
        capture.quiet(8)
        noise=np.random.default_rng(17).normal(0,.15,4096)*np.exp(-np.arange(4096)/1200)
        capture.send(noise);capture.quiet(8);QTest.qWait(80)
        self.assertEqual(self.view.listener.pass_.kinds[0],'muted')
        self.assertEqual(self.js("document.querySelector('.string-label.listening-string').textContent"),'A')
        self.view.hide();QTest.qWait(80)
        self.assertTrue(capture.stopped)
        before=list(self.view.listener.pass_.frets)
        capture.tone(45)
        self.assertEqual(self.view.listener.pass_.frets,before)

    def test_input_failure_and_optional_fretted_check(self):
        capture=self.calibrate()
        self.js("document.getElementById('check-note').click()")
        capture.quiet(20);capture.tone(45);capture.quiet(8);QTest.qWait(80)
        self.assertTrue(self.view.listener.calibrated)
        self.assertIsNone(self.view.listener.setup)
        self.view.listener.command.emit('go');QTest.qWait(80)
        capture.failed.emit('QA device disconnected');QTest.qWait(80)
        self.assertTrue(capture.stopped)
        self.assertTrue(self.js("document.getElementById('submit-paint').disabled"))
        self.assertIn('QA device disconnected',self.js("document.getElementById('listen-status').textContent"))

    def test_no_device_does_not_clear_dots_or_start_quiz(self):
        self.view.shutdown();self.view.close();QTest.qWait(50)
        self.settings.clear()
        self.open_view()
        before=self.js("document.querySelectorAll('.dot').length")
        self.choose_play(False)
        self.assertIsNone(self.view.listener.capture)
        self.assertEqual(self.js("document.querySelectorAll('.dot').length"),before)
        self.assertIn('Connection',self.js("document.getElementById('listen-status').textContent"))

    def test_play_is_default_and_explicit_click_survives_mode_changes(self):
        self.assertEqual(self.js("document.getElementById('input-mode').value"),'play')
        capture=self.view.listener.capture
        self.assertIsNotNone(capture)
        self.assertTrue(self.view.listener.setup is not None)
        self.js("document.querySelector('[data-mode=paint]').click()")
        QTest.qWait(60)
        self.assertEqual(self.js("document.getElementById('input-mode').value"),'play')
        self.assertIs(self.view.listener.capture,capture)
        self.assertFalse(capture.stopped)
        self.js("document.getElementById('input-mode').value='click';document.getElementById('input-mode').dispatchEvent(new Event('change'))")
        QTest.qWait(60)
        self.assertTrue(capture.stopped)
        self.js("document.querySelector('[data-mode=instant]').click();document.querySelector('[data-mode=paint]').click()")
        self.assertEqual(self.js("document.getElementById('input-mode').value"),'click')
        self.assertFalse(self.js("document.getElementById('start').disabled"))

    def test_hidden_preload_waits_for_painter_to_be_shown(self):
        self.view.shutdown();self.view.close();QTest.qWait(50)
        self.open_view(show=False)
        self.assertEqual(self.js("document.getElementById('input-mode').value"),'play')
        self.assertIsNone(self.view.listener.capture)
        self.view.show();QTest.qWait(150)
        self.assertIsNotNone(self.view.listener.capture)
        self.assertTrue(self.view.listener.active)

    def test_guess_uses_typed_answers_with_play_as_the_guitar_default(self):
        self.js("document.querySelector('[data-mode=guess]').click()")
        QTest.qWait(60)
        self.assertTrue(self.js("document.getElementById('listening-panel').hidden"))
        self.assertFalse(self.js("document.getElementById('start').disabled"))
        self.js("document.getElementById('start').click()")
        self.assertFalse(self.js("document.getElementById('guess-form').hidden"))

    def test_settings_surface_and_ready_screenshot(self):
        capture=self.calibrate()
        self.assertTrue(self.js("document.querySelector('.setup-fields #input-mode')!==null"))
        self.assertIn('Level',self.js("document.getElementById('listen-level').textContent"))
        self.assertEqual(self.js("document.getElementById('start').textContent"),'Go →')
        QTest.qWait(500)
        self.view.grab().save(str(ROOT/'build'/'play-calibration-ready.png'))
        self.view.hide();QTest.qWait(80)
        self.assertTrue(capture.stopped)
        self.view.listener.command.emit('go');QTest.qWait(80)
        self.assertTrue(self.js("document.getElementById('round-info').hidden"))

    def test_spoken_next_submits_once_then_rearms_a_wrong_answer(self):
        capture=self.begin()
        # An all-open voicing cannot satisfy the fixed C-root target in this test.
        for midi in [40,45,50,55,59,64]:capture.tone(midi);capture.quiet(8)
        QTest.qWait(80)
        self.view.listener.command.emit('next');QTest.qWait(80)
        self.assertEqual(self.js("document.getElementById('attempts').textContent"),'1 / 3')

        self.assertEqual(self.view.listener.pass_.stage,'strum')
        self.view.listener.command.emit('next');QTest.qWait(80)
        self.assertEqual(self.js("document.getElementById('attempts').textContent"),'1 / 3')

    def test_production_view_enables_voice_with_explicit_capture_factory(self):
        from voice_commands import VoiceCommands
        view=PainterView(self.temp.name,ROOT,settings=lambda:self.settings,capture_factory=TestCapture)
        self.assertIs(view.listener.voice_factory,VoiceCommands)
        view.shutdown();view.close();QTest.qWait(50)

    def test_shutdown_status_does_not_read_closed_settings_store(self):
        capture=self.calibrate()
        self.view.listener.settings=lambda: (_ for _ in ()).throw(RuntimeError('settings store closed'))
        self.view.listener.stop()
        self.view.listener.publish(stage='stopped')
        self.assertTrue(capture.stopped)

    def test_desktop_focus_layout_and_settings_at_normal_window_size(self):
        self.view.resize(1100, 780)
        capture=self.choose_play()
        capture.quiet(20);QTest.qWait(100)
        self.assertTrue(self.js("document.body.classList.contains('calibrating')"))
        self.assertEqual(self.js("document.querySelector('.string-label.listening-string').textContent"),'E')
        self.assertTrue(self.js("document.getElementById('chord-prompt').hidden"))
        self.assertEqual(self.js("document.querySelectorAll('.dot').length"),0)
        self.view.grab().save(str(ROOT/'build'/'painter-focus-calibration.png'))
        for midi in [40,45,50,55,59,64]:capture.tone(midi);capture.quiet(8)
        QTest.qWait(100)
        self.assertFalse(self.js("document.body.classList.contains('calibrating')"))
        self.view.listener.command.emit('go');QTest.qWait(80)
        capture.quiet(8);capture.tone(40,3);capture.quiet(8);QTest.qWait(80)
        self.view.grab().save(str(ROOT/'build'/'painter-focus-playing.png'))
        geometry=self.js("JSON.stringify({height:innerHeight,scroll:document.documentElement.scrollHeight,diagram:document.getElementById('diagram').getBoundingClientRect().bottom,action:document.getElementById('open-audio').getBoundingClientRect().bottom})")
        values=json.loads(geometry)
        self.assertLessEqual(values['diagram'],values['height'],geometry)
        self.assertLessEqual(values['action'],values['height'],geometry)
        self.assertLessEqual(values['scroll'],values['height'],geometry)
        for midi in [40,47,52,56,59,64]:capture.tone(midi);capture.quiet(8)
        QTest.qWait(100)
        self.assertTrue(self.js("!document.getElementById('submit-paint').disabled"))
        self.assertTrue(self.js("document.getElementById('open-audio').getBoundingClientRect().bottom<=innerHeight"))
        self.view.grab().save(str(ROOT/'build'/'painter-focus-review.png'))
        self.js("document.getElementById('open-settings').click()")
        QTest.qWait(150)
        self.assertTrue(self.js("document.getElementById('settings-dialog').open"))
        self.view.grab().save(str(ROOT/'build'/'painter-focus-settings.png'))
        self.view.listener.command.emit('quit');QTest.qWait(40)
        self.assertFalse(capture.stopped) # no voice command behind a modal
        self.js("document.getElementById('close-settings').click();document.getElementById('open-audio').click()")
        self.assertTrue(self.js("document.getElementById('audio-dialog').open"))
        self.assertIn('Level',self.js("document.getElementById('listen-level').textContent"))
        self.js("document.getElementById('listen-help').click()")
        self.assertFalse(self.js("document.getElementById('audio-dialog').open"))
        self.assertTrue(self.view.listener.setup is not None)


if __name__=='__main__':unittest.main()
