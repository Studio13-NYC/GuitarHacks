"""Quiz regression checks through the actual Qt WebEngine product surface."""
import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from painter_view import PainterView
from test_painter_listening import TestCapture

ROOT = Path(__file__).resolve().parent


class PainterQuizTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'build')
        self.view = PainterView(self.temp.name, ROOT, capture_factory=TestCapture, voice_factory=False)
        self.view.resize(1100, 900)
        self.view.show()
        for _ in range(150):
            if self.js("document.documentElement.dataset.ready==='true'"):
                break
            QTest.qWait(20)
        else:
            self.fail('Painter did not become ready')
        self.js("document.getElementById('input-mode').value='click';document.getElementById('input-mode').dispatchEvent(new Event('change'))")

    def tearDown(self):
        self.view.shutdown()
        self.view.close()
        QTest.qWait(50)
        self.temp.cleanup()

    def js(self, code):
        result = []
        self.view.page.runJavaScript(code, result.append)
        for _ in range(150):
            if result:
                return result[0]
            QTest.qWait(20)
        self.fail('JavaScript callback timed out')

    def start(self, quality='m7b5', pool='all', count=10):
        for name, value in [('quality', quality), ('pool', pool), ('questions', str(count))]:
            self.js(f"document.getElementById({json.dumps(name)}).value={json.dumps(value)};document.getElementById({json.dumps(name)}).dispatchEvent(new Event('change'))")
        self.js("document.querySelector('[data-mode=guess]').click();document.getElementById('start').click()")

    def enter(self):
        QTest.keyClick(self.view.web.focusProxy(), Qt.Key.Key_Return)
        QTest.qWait(80)

    def test_alias_answer_and_enter_after_correct_and_failed_questions(self):
        self.start()
        self.js("document.getElementById('guess-input').value='c 1/2 dim 7';document.getElementById('guess-input').focus()")
        self.enter()
        self.assertTrue(self.js("document.getElementById('feedback').textContent.startsWith('Correct.')"))
        self.assertEqual(self.js('document.activeElement.id'), 'next')
        self.enter()
        self.assertEqual(self.js("document.getElementById('question-progress').textContent"), 'Question 2 of 10')
        self.assertEqual(self.js('document.activeElement.id'), 'guess-input')
        self.js("for(let n=0;n<3;n++){document.getElementById('guess-input').value='invalid';document.getElementById('guess-form').requestSubmit();}")
        self.assertTrue(self.js("document.getElementById('feedback').textContent.startsWith('Question failed.')"))
        self.assertEqual(self.js('document.activeElement.id'), 'next')
        self.enter()
        self.assertEqual(self.js("document.getElementById('question-progress').textContent"), 'Question 3 of 10')

    def test_minor_major_seventh_is_excluded_from_both_quiz_pools_and_handoff(self):
        for pool in ['sevenths', 'all']:
            if pool == 'all':
                self.js("document.getElementById('review-dialog').close();document.querySelector('[data-mode=instant]').click()")
            self.start(quality='mMaj7', pool=pool, count=100)
            names = json.loads(self.js("JSON.stringify(Array.from({length:100},()=>{document.getElementById('reveal').click();const name=document.getElementById('chord-name').textContent;document.getElementById('next').click();return name;}))"))
            self.assertEqual(len(names), 100)
            self.assertFalse(any('m(maj7)' in name for name in names), names)
            self.assertGreater(len(set(names)), 1)


if __name__ == '__main__':
    unittest.main()
