"""Verify lookup and practice handoff through the real embedded browser."""
import json
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from painter_view import ExplorerView

ROOT=Path(__file__).resolve().parent

class ExplorerViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.view=ExplorerView(ROOT)
        self.view.resize(1100,780);self.view.show()
        for _ in range(150):
            if self.js("document.documentElement.dataset.ready==='true'"):break
            QTest.qWait(20)
        else:self.fail('Explorer did not become ready')

    def tearDown(self):
        self.view.shutdown();self.view.close();QTest.qWait(50)

    def js(self,code):
        values=[];self.view.page.runJavaScript(code,values.append)
        for _ in range(150):
            if values:return values[0]
            QTest.qWait(20)
        self.fail('JavaScript callback timed out')

    def test_note_positions_detail_and_practice_handoff(self):
        self.assertEqual(self.js("document.getElementById('lookup-title').textContent"),'B')
        self.assertEqual(self.js("document.querySelectorAll('#lookup-board tbody tr').length"),6)
        self.js("document.querySelector('#lookup-board button[aria-label*=\"string 2\"]').click()")
        self.assertIn('open',self.js("document.getElementById('lookup-detail').textContent"))
        self.assertIn('B3',self.js("document.getElementById('lookup-detail').textContent"))
        notes=[];self.view.bridge.practice.connect(notes.append)
        self.js("document.getElementById('find-everywhere').click()")
        QTest.qWait(50);self.assertEqual(notes,[11])
        self.view.grab().save(str(ROOT/'build/explorer-note.png'))

    def test_chord_spelling_range_and_errors(self):
        self.js("document.getElementById('lookup-kind').value='chord';document.getElementById('lookup-name').value='Bbmaj7';document.getElementById('lookup-form').requestSubmit()")
        self.assertEqual(self.js("document.getElementById('lookup-title').textContent"),'B♭maj7')
        self.assertEqual(json.loads(self.js("JSON.stringify([...document.querySelectorAll('#lookup-tones b')].map(n=>n.textContent))")),['B♭','D','F','A'])
        self.assertTrue(self.js("document.getElementById('find-everywhere').hidden"))
        self.assertTrue(self.js("document.getElementById('lookup-detail').getBoundingClientRect().bottom<innerHeight"))
        QTest.qWait(150)
        self.view.grab().save(str(ROOT/'build/explorer-chord.png'))
        self.js("document.getElementById('lookup-range').value='24';document.getElementById('lookup-range').dispatchEvent(new Event('change'))")
        self.assertEqual(self.js("document.querySelectorAll('#lookup-board thead th').length"),26)
        self.js("document.getElementById('lookup-name').value='Hmaj7';document.getElementById('lookup-form').requestSubmit()")
        self.assertTrue(self.js("document.getElementById('lookup-result').hidden"))
        self.assertTrue(self.js("document.getElementById('lookup-error').textContent.length>0"))

if __name__=='__main__':unittest.main()
