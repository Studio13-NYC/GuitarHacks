"""Song-folder reuse, explicit destinations, and cancellation before processing."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox
from StemSlicer.library import find_song_folder, remember_folder, reports
from stems_view import StemSlicerPage, SliceDestinationDialog

ROOT = Path(__file__).resolve().parent


class SliceDestinationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'build')
        self.root = Path(self.temp.name)
        self.audio = self.root/'01 Mr Jones.wav'
        self.audio.touch()
        for name in ('.venv/Scripts/python.exe', 'separate_instruments.py', 'export_stems.py', 'recipe_spec.py'):
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True); path.touch()
        self.page = StemSlicerPage(lambda: None, self.root)
        self.page.set_source(self.audio)
        for row in list(self.page.containers): self.page.remove_stem(row)
        self.page.add_stem(['vocals'])

    def tearDown(self):
        if self.page.log: self.page.log.close()
        self.page.close(); self.page.deleteLater(); self.app.processEvents()
        self.temp.cleanup()

    def test_existing_song_reused_and_button_stays_create_slices(self):
        folder = self.root/'separated'/'Mr Jones'; folder.mkdir(parents=True)
        (folder/'mr-jones-V.mp3').write_bytes(b'previous export')
        with patch('stems_view.SliceDestinationDialog') as dialog, patch.object(self.page, 'begin_job') as begin:
            self.page.start_separation()
        dialog.assert_not_called(); begin.assert_called_once()
        self.assertEqual(self.page.output, folder)
        self.assertEqual(self.page.plan['names'], ['mr-jones-V-2'])
        self.assertIn(str(folder), self.page.commands[-1])
        self.assertEqual((folder/'mr-jones-V.mp3').read_bytes(), b'previous export')
        self.page.finish('COMPLETE', success=True)
        self.assertEqual(self.page.start.text(), 'Create slices')

    def test_new_destination_cancel_does_not_start_or_create_song_folder(self):
        with patch('stems_view.SliceDestinationDialog') as dialog, patch.object(self.page, 'begin_job') as begin:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.page.start_separation()
        begin.assert_not_called()
        self.assertFalse((self.root/'separated'/'Mr Jones').exists())
        self.assertFalse((self.root/'processing').exists())

    def test_override_exports_to_named_folder_and_is_remembered(self):
        original = self.root/'separated'/'Mr Jones'; original.mkdir(parents=True)
        (original/'mr-jones-V.mp3').write_bytes(b'keep')
        alternate = self.root/'alternate location'/'Vocals practice'
        alternate.parent.mkdir()
        with patch('stems_view.SliceDestinationDialog') as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.destination.return_value = alternate
            self.assertTrue(self.page.choose_destination(override=True))
            self.assertNotEqual(dialog.call_args.args[1], original)
        with patch.object(self.page, 'begin_job'):
            self.page.start_separation()
        self.assertEqual(self.page.output, alternate)
        self.assertEqual(self.page.plan['names'], ['mr-jones-V'])
        self.assertEqual(find_song_folder(self.root, self.audio, 'Mr Jones'), alternate)
        self.assertEqual((original/'mr-jones-V.mp3').read_bytes(), b'keep')
        (alternate/'mr-jones-V.mp3').touch()
        manifest = alternate/'stem-manifest-test.json'
        manifest.write_text(json.dumps({'source': str(self.audio), 'title':'Mr Jones', 'files':['mr-jones-V.mp3']}))
        self.assertIn(manifest, reports(self.root))
        fresh = StemSlicerPage(lambda: None, self.root)
        fresh.set_source(self.audio)
        self.assertEqual(fresh.destination_for_song(), alternate)
        self.assertEqual(fresh.results.currentData(), str(alternate))
        self.assertEqual(fresh.files.count(), 2)
        fresh.close(); fresh.deleteLater(); self.app.processEvents()

    def test_normalized_existing_song_and_new_song_reset(self):
        folder = self.root/'separated'/'Mr  Jones'; folder.mkdir(parents=True)
        self.page.destination_key = None
        self.assertEqual(self.page.destination_for_song(), folder)
        different = self.root/'Another Song.wav'; different.touch()
        self.page.set_source(different)
        self.assertEqual(self.page.destination_for_song(), self.root/'separated'/'Another Song')
        self.assertFalse(self.page.destination_confirmed)

    def test_dialog_requires_safe_folder_name_and_shows_existing_folder(self):
        dialog = SliceDestinationDialog(self.page, self.root/'New mix')
        self.assertEqual(dialog.destination(), self.root/'New mix')
        for bad in ('', '..', '../escape', 'CON', 'folder/name', 'a'*81):
            dialog.folder_name.setText(bad)
            self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled())
        folder = self.root/'Existing'; folder.mkdir()
        dialog.folder_name.setText('Existing')
        self.assertIn('Existing folder', dialog.preview.text())
        self.assertEqual(dialog.destination(), folder)
        dialog.close(); dialog.deleteLater()
