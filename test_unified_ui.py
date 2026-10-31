"""Single-window navigation and responsive audio practice behavior."""
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
from test_flashcards import QApplication, MainWindow, SyntheticCapture, QTest, Qt
from single_instance import SingleInstance
from exercises import make_exercise
from everywhere import EverywhereSession
from session import Session
from app import apply_theme
from PySide6.QtGui import QFontMetrics, QFontDatabase
from PySide6.QtCore import QPoint

ROOT=Path(__file__).resolve().parent


class UnifiedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        # The offscreen Qt platform does not discover Windows fonts itself.
        for name in ('segoeui.ttf','segoeuib.ttf'):
            QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
        apply_theme(cls.app)

    def test_all_audio_navigation_and_connection_stay_in_one_window(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            with patch('app.input_devices',return_value=[]):
                w=MainWindow(Path(folder),ROOT/'FretboardFiend'/'lessons',SyntheticCapture)
                w.show();w.splash_timer.stop();w.show_home()
                try:
                    native_id=w.winId()
                    w.show_notes();self.assertIs(w.setup_page.window(),w)
                    w.connection_settings();self.app.processEvents()
                    self.assertIs(w.connection_dialog.window(),w)
                    self.assertIs(w.pages.currentWidget(),w.connection_page)
                    w.connection_dialog.reject();self.app.processEvents()
                    self.assertIs(w.pages.currentWidget(),w.setup_page)
                    w.show_home();w.show_everywhere()
                    self.assertIs(w.setup_page.window(),w)
                    self.assertEqual(w.winId(),native_id)
                    visible=[widget for widget in self.app.topLevelWidgets() if widget.isVisible()]
                    self.assertEqual(visible,[w])
                    w.resize(680,640);QTest.qWait(30)
                    self.assertFalse(w.setup_page.wide)
                    self.assertEqual(w.setup_page.horizontalScrollBar().maximum(),0)
                    self.assertLessEqual(w.setup_page.workspace.geometry().right(),w.setup_page.widget().width())
                finally:w.close()

    def test_connection_saves_and_returns_without_creating_another_window(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            with patch('app.input_devices',return_value=[dict(name='QA input',max_input_channels=2)]):
                w=MainWindow(Path(folder),ROOT/'FretboardFiend'/'lessons',SyntheticCapture)
                w.show();w.splash_timer.stop();w.show_home()
                try:
                    w.connection_settings();w.connection_dialog.device.setCurrentIndex(0)
                    w.connection_dialog.channel.setCurrentIndex(1)
                    w.connection_dialog.accept()
                    QTest.qWait(50)
                    self.assertIs(w.pages.currentWidget(),w.home_page)
                    self.assertEqual(w.settings['input'],'QA input')
                    self.assertEqual(w.store.settings()['channel'],1)
                    self.assertIsNone(w.connection_page)
                finally:w.close()

    def test_second_launch_signals_owner_and_does_not_acquire_profile(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            first=SingleInstance(folder);second=SingleInstance(folder)
            activations=[];first.activated.connect(lambda:activations.append(True))
            try:
                self.assertTrue(first.acquire())
                self.assertFalse(second.acquire())
                QTest.qWait(50)
                self.assertEqual(activations,[True])
                self.assertFalse(second.owner)
                first.close()
                self.assertTrue(second.acquire())
            finally:first.close();second.close()

    def test_missing_audio_returns_to_inline_message_without_another_window(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            with patch('app.input_devices',return_value=[]):
                w=MainWindow(Path(folder),ROOT/'FretboardFiend'/'lessons',SyntheticCapture)
            w.show();w.splash_timer.stop();w.show_notes()
            try:
                w.settings.update(input='QA',cues=False)
                w.toggle()
                w.audio_failed('No audio data from the input.')
                QTest.qWait(20)
                self.assertIs(w.pages.currentWidget(),w.setup_page)
                self.assertIsNone(w.capture)
                self.assertTrue(w.setup_error.isVisible())
                self.assertIn('No audio data',w.setup_error.text())
                self.assertEqual([x for x in self.app.topLevelWidgets() if x.isVisible()],[w])
                self.assertEqual(w.store.total(),0)
            finally:w.close()

    def test_practice_surfaces_fit_and_render_with_isolated_data(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            with patch('app.input_devices',return_value=[]):
                w=MainWindow(Path(folder),ROOT/'FretboardFiend'/'lessons',SyntheticCapture)
            w.show();w.splash_timer.stop();w.clock_timer.stop()
            output=ROOT/'build'/'unified-ui-preview';output.mkdir(exist_ok=True)
            try:
                for section in ('notes','everywhere'):
                    (w.show_notes if section=='notes' else w.show_everywhere)()
                    QTest.qWait(20)
                    title=w.setup_title
                    self.assertLessEqual(max(QFontMetrics(title.font()).horizontalAdvance(word) for word in title.text().split()),title.width())
                    w.grab().save(str(output/f'{section}-setup.png'))
                for race in (False,True):
                    w.session=EverywhereSession(w.store) if race else Session(w.store)
                    lesson=make_exercise(4,0) if race else make_exercise(3,0,5)
                    w.session.start(lesson)
                    w.capture=SyntheticCapture('QA',0,-36,w)
                    w.show_card();QTest.qWait(20)
                    self.assertIs(w.card_page.window(),w)
                    self.assertGreater(w.prompt.font().pixelSize(),90)
                    self.assertLessEqual(w.instruction.mapTo(w.card_page.viewport(),QPoint(0,w.instruction.height())).y(),w.card_page.viewport().height())
                    w.grab().save(str(output/('everywhere-play.png' if race else 'flashcards-play.png')))
                    w.session.quit();w.show_complete();QTest.qWait(20)
                    w.grab().save(str(output/'results.png'))
                w.show_home()
            finally:w.close()


if __name__=='__main__':unittest.main()
