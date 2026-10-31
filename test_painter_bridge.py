"""Protect existing progress when the embedded app saves or encounters bad data."""
import json
from pathlib import Path
import tempfile
import unittest
from painter_view import PainterBridge


class PainterStorageTests(unittest.TestCase):
    def test_progress_survives_a_new_bridge_and_invalid_save_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = PainterBridge(folder)
            self.assertEqual(bridge.load(), '')
            saved = dict(version=1, config={'rootFret': 8}, history=[{'result': 'correct'}], stats={})
            bridge.save(json.dumps(saved))
            self.assertEqual(json.loads(PainterBridge(folder).load()), saved)
            errors = []
            bridge.error.connect(errors.append)
            with self.assertLogs(level='ERROR'):
                bridge.save('{"version":2}')
            self.assertTrue(errors)
            self.assertEqual(json.loads(bridge.load()), saved)

    def test_corrupted_input_is_preserved_for_the_view_to_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'chord-painter.json'
            path.write_text('broken JSON', encoding='utf-8')
            self.assertEqual(PainterBridge(folder).load(), 'broken JSON')
            self.assertEqual(path.read_text(encoding='utf-8'), 'broken JSON')

    def test_deleted_file_is_not_recreated_by_an_open_window(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = PainterBridge(folder)
            raw = json.dumps(dict(version=1, config={}, history=[], stats={}))
            bridge.save(raw)
            bridge.path.unlink()
            with self.assertLogs(level='ERROR'):
                bridge.save(raw)
            self.assertFalse(bridge.path.exists())
            fresh = PainterBridge(folder)
            self.assertEqual(fresh.load(), '')
            fresh.save(raw)
            self.assertTrue(fresh.path.exists())

    def test_external_edit_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = PainterBridge(folder)
            raw = json.dumps(dict(version=1, config={}, history=[], stats={}))
            bridge.save(raw)
            bridge.path.write_text('external edit', encoding='utf-8')
            with self.assertLogs(level='ERROR'):
                bridge.save(raw)
            self.assertEqual(bridge.path.read_text(encoding='utf-8'), 'external edit')
