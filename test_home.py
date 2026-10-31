"""Exercise navigation through real Qt widgets, with isolated data and fake capture."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_flashcards import QApplication, MainWindow, SyntheticCapture, QTest, Qt
from exercises import make_exercise

ROOT=Path(__file__).resolve().parent


class HomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(dir=ROOT/'build')
        with patch('app.input_devices',return_value=[]):
            self.window=MainWindow(Path(self.folder.name),ROOT/'FretboardFiend'/'lessons',SyntheticCapture)
        self.window.show()
        self.window.splash_timer.stop()
        self.window.splash_timer.timeout.emit()
        QTest.qWait(10)

    def tearDown(self):
        self.window.close()
        self.folder.cleanup()

    def click(self,button):
        QTest.mouseClick(button,Qt.MouseButton.LeftButton)
        self.app.processEvents()

    def test_startup_and_section_cards_preserve_note_settings_without_opening_audio(self):
        w=self.window
        self.assertEqual(w.pages.currentWidget(),w.home_page)
        self.assertEqual(w.windowTitle(),'GuitarHacks · Home')
        self.assertIsNone(w.capture)
        self.click(w.home_page.cards[0])
        self.assertEqual(w.pages.currentWidget(),w.setup_page)
        self.click(w.mode_buttons[3])
        w.note_combo.setCurrentIndex(2)
        w.string_combo.setCurrentIndex(w.string_combo.findData(4))
        w.seconds_spin.setValue(35);w.attempts_spin.setValue(5)
        w.lesson_combo.setCurrentIndex(1)
        note_lesson=w.selected_lesson().id
        # Older installations have no per-section selection keys yet.
        w.settings.pop('note_mode',None);w.settings.pop('note_plugin',None)
        w.show_home()
        self.click(w.home_page.cards[1])
        self.assertEqual(w.pages.currentWidget(),w.explorer)
        self.assertEqual(w.windowTitle(),'GuitarHacks · Fretboard Explorer')
        self.assertIsNone(w.capture)
        w.explorer.bridge.findEverywhere(2)
        self.assertEqual(w.setup_title.text(),'Find everywhere')
        self.assertEqual(w.selected_lesson().id,'everywhere-v1')
        self.assertFalse(w.seconds_spin.isVisible())
        w.show_home();self.click(w.home_page.cards[0])
        self.assertEqual(w.mode_group.checkedId(),3)
        self.assertEqual(w.selected_lesson().id,note_lesson)
        self.assertEqual((w.note_combo.currentData(),w.string_combo.currentData()),(2,4))
        self.assertEqual((w.seconds_spin.value(),w.attempts_spin.value()),(35,5))
        self.assertIsNone(w.capture)
        self.assertEqual(w.store.total(),0)

    def test_home_during_calibration_stops_input_without_a_result_and_can_restart(self):
        w=self.window;w.settings.update(input='QA',cues=False)
        self.click(w.home_page.cards[0]);self.click(w.start_button)
        self.assertIsNotNone(w.calibration)
        capture=w.capture
        self.click(w.card_home)
        self.assertEqual(w.pages.currentWidget(),w.home_page)
        self.assertIsNone(w.capture);self.assertFalse(capture.running)
        self.assertIsNone(w.calibration);self.assertEqual(w.store.total(),0)
        self.click(w.home_page.cards[1]);w.explorer.bridge.findEverywhere(0);self.click(w.start_button)
        self.assertEqual(w.run_lesson.id,'everywhere-v1')
        self.assertIsNotNone(w.calibration)

    def test_home_ends_a_run_once_and_cancels_pending_transitions(self):
        w=self.window
        w.session.start(make_exercise(3,0,5),size=2)
        capture=SyntheticCapture('QA',0,-36,w)
        w.capture=capture;capture.running=True
        capture.finished.connect(w.capture_finished)
        w.show_card()
        w.transition='gap';w.next_timer.start(100)
        self.click(w.card_home)
        QTest.qWait(120)
        self.assertEqual(w.pages.currentWidget(),w.home_page)
        self.assertFalse(w.session.active);self.assertIsNone(w.capture)
        self.assertIsNone(w.transition);self.assertFalse(w.next_timer.isActive())
        self.assertEqual(w.store.total(),2)
        w.show_home();self.assertEqual(w.store.total(),2)

    def test_home_stacks_cards_at_small_window_width_and_all_sections_remain_reachable(self):
        w=self.window
        w.resize(680,640);QTest.qWait(20)
        self.assertEqual(w.home_page.columns,1)
        self.assertEqual(w.home_page.horizontalScrollBar().maximum(),0)
        for card in w.home_page.cards:
            self.assertLessEqual(card.geometry().right(),w.home_page.widget().width())
            self.assertLessEqual(card.layout().minimumSize().height(),card.height())
        w.home_page.ensureWidgetVisible(w.home_page.cards[3])
        self.assertTrue(w.home_page.cards[3].isVisible())
        w.resize(1100,820);QTest.qWait(20)
        self.assertEqual(w.home_page.columns,3)
        self.assertEqual(w.home_page.horizontalScrollBar().maximum(),0)

    def test_stems_navigation_and_manual_selection_do_not_start_audio(self):
        w=self.window
        self.click(w.home_page.cards[3])
        self.assertEqual(w.pages.currentWidget(),w.stems)
        self.assertEqual(w.windowTitle(),'GuitarHacks · StemSlicer')
        self.assertIsNone(w.capture)
        self.assertFalse(w.stems.running)
        source=Path(self.folder.name)/'source.wav'
        source.touch()
        w.stems.set_source(source)
        first,second=w.stems.containers
        self.assertEqual(first.parts(),['lead-guitar'])
        self.assertEqual(second.parts(),['lead-guitar','rhythm-guitar'])
        extra=w.stems.add_stem()
        self.assertFalse(w.stems.start.isEnabled())
        extra.checks['drums'].setChecked(True)
        self.assertTrue(w.stems.start.isEnabled())
        self.assertEqual(w.stems.definitions(),[['lead-guitar'],['lead-guitar','rhythm-guitar'],['drums']])
        w.stems.remove_stem(extra)
        self.assertEqual(len(w.stems.containers),2)
        self.click(w.stems.home)
        self.assertEqual(w.pages.currentWidget(),w.home_page)


if __name__=='__main__':unittest.main()
