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
