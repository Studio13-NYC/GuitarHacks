"""Measured recovery of missed B-string notes, with no invented lesson scores."""
import json
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np

from test_flashcards import QApplication, MainWindow, SyntheticCapture, wave, ROOT, QTest
from audio import PitchTracker
from detection_help import analyse, heard_text, LiveHearing


def frames(midi=None, db=-60, count=24, cents=0):
    output=[]
    tracker=PitchTracker()
    signal=np.zeros(4096) if midi is None else wave(midi,cents)
    if midi is not None:
        signal=signal/np.sqrt(np.mean(signal*signal))*10**(db/20)
    for _ in range(count):
        frame,_=tracker.process(signal,48000)
        if midi is None:frame['db']=db
        output.append(frame)
    return output


class DetectionTests(unittest.TestCase):
    def test_last_heard_note_survives_silence_but_new_e_replaces_b_immediately(self):
        hearing=LiveHearing()
        self.assertIn('B3',hearing.update(frames(59,-25,cents=-12)[0],now=0))
        retained=hearing.update(frames()[0],now=1)
        self.assertIn('Last heard B3',retained)
        self.assertIn('Hz',retained)
        self.assertIn('flat',retained)
        fresh=hearing.update(frames(64,-25)[0],now=1.1)
        self.assertIn('Hearing E4',fresh)
        self.assertNotIn('B3',fresh)
        self.assertNotIn('E4',hearing.update(frames()[0],now=4))
        hearing.clear()
        self.assertNotIn('Last heard',hearing.update(frames()[0],now=4))

    def test_shorter_hold_still_requires_quiet_and_clean_stable_audio(self):
        tracker=PitchTracker(-49,.3)
        signal=wave(59);signal=signal/np.sqrt(np.mean(signal*signal))*10**(-43/20)
        for _ in range(8):self.assertIsNone(tracker.process(signal,48000)[1])
        for _ in range(4):tracker.process(np.zeros(4096),48000)
        for _ in range(3):self.assertIsNone(tracker.process(signal,48000)[1])
        self.assertEqual(tracker.process(signal,48000)[1]['midi'],59)
        for _ in range(4):tracker.process(np.zeros(4096),48000)
        for _ in range(8):self.assertIsNone(tracker.process(signal,48000,overflow=True)[1])

    def test_tuner_observes_quiet_b_without_accepting_it_as_answer(self):
        sample=frames(59,-43,cents=-12)[0]
        self.assertIn('B3',heard_text(sample))
        self.assertIn('flat',heard_text(sample))
        self.assertIn('too quiet',heard_text(sample))
        self.assertFalse(sample['pitched'])
        self.assertIn('sharp',heard_text(frames(59,-25,cents=12)[0]))

    def test_adjustment_requires_clear_expected_pitch_and_noise_margin(self):
        before={'gate':-36,'hold_seconds':.5}
        plan=analyse(frames(),frames(59,-43),59,before)
        self.assertTrue(plan['can_retest'])
        self.assertLess(plan['settings']['gate'],-43)
        self.assertGreaterEqual(plan['settings']['gate'],-50)
        self.assertFalse(analyse(frames(),frames(55,-25),59,before)['can_retest'])
        self.assertFalse(analyse(frames(db=-45),frames(59,-43),59,before)['can_retest'])
        clipped=frames(59,-25);clipped[0]['clipped']=True
        self.assertFalse(analyse(frames(),clipped,59,before)['can_retest'])
        short=analyse(frames(),frames(59,-25,count=4),59,before)
        self.assertEqual(short['settings']['hold_seconds'],.3)

    def make_window(self, folder):
        with patch('app.input_devices', return_value=[]):
            window=MainWindow(Path(folder),ROOT/'FretboardFiend/lessons',SyntheticCapture)
        window.splash_timer.stop()
        window.settings.update(input='QA guitar channel',channel=0,gate=-36,cues=False)
        window.show_setup();window.toggle()
        calibration=window.calibration
        calibration.stage='strings';calibration.index=4;calibration.noise_floor=-60
        calibration.reference_cents={6:0,5:0,4:0,3:0}
        window.show_calibration()
        return window

    def test_red_setup_note_keeps_rejection_details_through_silence(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            window=self.make_window(temp)
            try:
                window.calibration.armed=True
                window.calibration.started=time.monotonic()-1
                window.audio_note(dict(midi=64,note='E4',hz=329.63,cents=0,db=-25,
                                       periodicity=.99,started=time.monotonic(),monotonic=time.monotonic()))
                self.assertIn('Heard E4',window.run_help.text())
                self.assertIn('329.6 Hz',window.run_help.text())
                self.assertIn('Expected B3',window.run_help.text())
                for frame in frames(count=40):window.audio_frame(frame)
                self.assertIn('Heard E4',window.run_help.text())
                self.assertEqual(window.calibration.index,4)
            finally:
                window.close();window.deleteLater();app.processEvents()

    def measure(self, dialog):
        dialog.begin()
        for frame in frames():dialog.frame(frame)
        for frame in frames(59,-43,count=72):dialog.frame(frame)
        self.assertEqual(dialog.phase,'verify')

    def test_weak_b_recovery_requires_two_new_plucks_then_logs_and_saves(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            window=self.make_window(temp)
            try:
                window.report_detection()
                dialog=window.detection_dialog
                self.assertEqual(dialog.issue.currentText(),'Note not detected')
                self.assertEqual(dialog.string.currentData(),59)
                self.measure(dialog)
                self.assertEqual(window.store.settings()['gate'],-36)
                signal=wave(59);signal=signal/np.sqrt(np.mean(signal*signal))*10**(-43/20)
                for attempt in range(2):
                    window.capture.play(np.zeros(4096),4)
                    QTest.qWait(20)
                    window.capture.play(signal,8)
                    self.assertEqual(dialog.verified,attempt+1)
                self.assertEqual(dialog.phase,'resolved')
                self.assertLess(window.store.settings()['gate'],-43)
                self.assertEqual(window.calibration.index,4)
                self.assertEqual(set(window.calibration.reference_cents),{3,4,5,6})
                self.assertEqual(window.store.connection.execute('SELECT count(*) FROM attempts').fetchone()[0],0)
                self.assertEqual(window.store.connection.execute('SELECT count(*) FROM runs').fetchone()[0],0)
                records=[json.loads(line) for line in dialog.log_path.read_text().splitlines()]
                self.assertEqual(records[-1]['event'],'resolved')
                self.assertEqual(records[-1]['verified_notes'],2)
                self.assertEqual(records[-1]['before']['gate'],-36)
                dialog.accept();app.processEvents()
                self.assertIsNone(window.detection_dialog)
                self.assertEqual(window.calibration.index,4)
            finally:
                window.close();window.deleteLater();app.processEvents()

    def test_failed_or_cancelled_retest_restores_settings_and_logs_unresolved(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            window=self.make_window(temp)
            try:
                window.report_detection();dialog=window.detection_dialog
                self.measure(dialog)
                dialog.deadline=time.monotonic()-1;dialog.timeout_check()
                self.assertEqual(dialog.phase,'attention')
                self.assertEqual(window.capture.tracker.gate,-36)
                self.assertEqual(window.store.settings()['gate'],-36)
                self.measure(dialog)
                log=dialog.log_path
                dialog.reject();app.processEvents()
                self.assertEqual(window.capture.tracker.gate,-36)
                records=[json.loads(line) for line in log.read_text().splitlines()]
                self.assertFalse(records[-1]['settings_saved'])
                self.assertTrue(any(r['event']=='needs_attention' for r in records))
            finally:
                window.close();window.deleteLater();app.processEvents()

    def test_setup_report_starts_capture_and_input_failure_is_logged(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            with patch('app.input_devices',return_value=[]):
                window=MainWindow(Path(temp),ROOT/'FretboardFiend/lessons',SyntheticCapture)
            try:
                window.settings.update(input='QA guitar channel',gate=-36,cues=False)
                window.report_detection()
                self.assertIsNotNone(window.detection_dialog)
                log=window.detection_dialog.log_path
                window.audio_failed('test disconnected input')
                self.assertIsNone(window.detection_dialog)
                records=[json.loads(line) for line in log.read_text().splitlines()]
                self.assertTrue(any(r['event']=='needs_attention' and 'disconnected' in r['reason'] for r in records))
            finally:
                window.close();window.deleteLater();app.processEvents()


if __name__=='__main__':unittest.main()
