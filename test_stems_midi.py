"""MIDI timing, polyphony, preservation, and Qt action availability."""
import csv
import hashlib
import json
import os
import subprocess
import sys
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
import mido
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QProcess
from unittest.mock import patch
from NeuralNote.export_midi import make_midi, export
from stems_view import StemSlicerPage

ROOT = Path(__file__).resolve().parent


def note(start, end, pitch, program=27, drum=False):
    return dict(onset=start, offset=end, pitch=pitch, program=program,
                is_drum=int(drum), instrument='drums' if drum else 'electric_guitar')


class MidiTests(unittest.TestCase):
    def test_export_records_conditioning_used_without_changing_note_timing(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            folder = Path(temp)
            raw = folder/'audio.f32'; raw.write_bytes(bytes(64000))
            audio = folder/'audio.wav'; audio.touch()
            notes = folder/'notes.tsv'
            with notes.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, list(note(0,1,36)), delimiter='\t')
                writer.writeheader(); writer.writerow(note(.2, .21, 36, 128, True))
            settings = {'instruments':['drums'], 'decoder':'greedy', 'prelude_forcing':True,
                        'notes_sha256':hashlib.sha256(notes.read_bytes()).hexdigest()}
            notes.with_suffix('.settings.json').write_text(json.dumps(settings))
            result = subprocess.run([sys.executable, str(ROOT/'NeuralNote/export_midi.py'),
                                     str(notes), str(audio), str(raw), str(folder/'out'),
                                     '--name', 'drums', '--completion', str(folder/'done.json'),
                                     '--instruments', 'drums'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((folder/'done.json').read_text())
            self.assertEqual(manifest['instruments'], ['drums'])
            self.assertEqual(manifest['decoder'], 'greedy')
            midi = mido.MidiFile(folder/'out/drums.mid')
            self.assertAlmostEqual(next(m.time for m in midi if m.type == 'note_on'), .2, delta=.001)
            notes.with_suffix('.settings.json').write_text(json.dumps({**settings, 'instruments':[]}))
            failed = subprocess.run([sys.executable, str(ROOT/'NeuralNote/export_midi.py'),
                                     str(notes), str(audio), str(raw), str(folder/'out'),
                                     '--name', 'wrong', '--completion', str(folder/'wrong.json'),
                                     '--instruments', 'drums'], capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse((folder/'out/wrong.mid').exists())
            notes.with_suffix('.settings.json').write_text(json.dumps(settings))
            notes.write_text(notes.read_text().replace('36', '38'))
            stale = subprocess.run([sys.executable, str(ROOT/'NeuralNote/export_midi.py'),
                                     str(notes), str(audio), str(raw), str(folder/'out'),
                                     '--name', 'stale', '--completion', str(folder/'stale.json'),
                                     '--instruments', 'drums'], capture_output=True, text=True)
            self.assertNotEqual(stale.returncode, 0)
            self.assertFalse((folder/'out/stale.mid').exists())

    def test_saved_recipes_condition_each_stem_without_guessing_from_filenames(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            root = Path(temp)
            song = root/'separated'/'Song'; song.mkdir(parents=True)
            original = root/'original.wav'; original.touch()
            recipes = {'take.wav': ['drums'], 'bass.wav': ['bass'],
                       'guitar.wav': ['lead-guitar', 'rhythm-guitar'],
                       'mix.wav': ['drums', 'bass'], 'other.wav': ['other'],
                       'old-D.wav': None}
            files = {}
            for filename, parts in recipes.items():
                (song/filename).touch()
                files[filename] = {'instruments': parts, 'sha256':hashlib.sha256(b'').hexdigest()}
            (song/'stem-manifest-test.json').write_text(json.dumps({'source':str(original), 'files':files}))
            page = StemSlicerPage(lambda: None, root)
            try:
                page.results.setCurrentIndex(page.results.findData(str(song)))
                for i in range(page.files.count()):
                    page.files.item(i).setCheckState(Qt.CheckState.Checked)
                with patch.object(page, 'start_next_midi'):
                    page.start_midify()
                actual = {Path(row['audio']).name: row.get('instruments') for row in page.midi_queue}
                self.assertEqual(actual, {
                    'original.wav': [], 'take.wav': ['drums'],
                    'bass.wav': ['acoustic_bass', 'electric_bass'],
                    'guitar.wav': ['acoustic_guitar', 'clean_electric_guitar', 'distorted_electric_guitar'],
                    'mix.wav': ['drums', 'acoustic_bass', 'electric_bass'],
                    'other.wav': [], 'old-D.wav': []})
                page.midi_instruments.setCurrentIndex(page.midi_instruments.findData('drums'))
                self.assertEqual(actual['bass.wav'], ['acoustic_bass', 'electric_bass'])
                page.midi_queue.clear()
                with patch.object(page, 'start_next_midi'):
                    page.start_midify()
                self.assertTrue(all(row['instruments'] == ['drums'] for row in page.midi_queue))
                page.midi_instruments.setCurrentIndex(page.midi_instruments.findData('all'))
                self.assertTrue(all(row['instruments'] == ['drums'] for row in page.midi_queue))
                page.running = True; page.update_midi_actions()
                self.assertFalse(page.midi_instruments.isEnabled())
                page.running = False
            finally:
                page.close(); page.deleteLater(); app.processEvents()

    def test_conditioning_reaches_native_command_and_export_settings(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            root = Path(temp)
            for relative in ('StemSlicer/pyproject.toml', '.venv/Scripts/python.exe',
                             'NeuralNote/cli/build/Release/guitarhacks-transcribe.exe',
                             'NeuralNote/models/muscriptor-large-f16.gguf', 'NeuralNote/export_midi.py',
                             'source.wav', 'ffmpeg.exe'):
                path = root/relative; path.parent.mkdir(parents=True, exist_ok=True); path.touch()
            page = StemSlicerPage(lambda: None, root/'StemSlicer')
            try:
                page.batch_bpm = 119
                request = {'audio':str(root/'source.wav'), 'output':str(root/'out'),
                           'original':False, 'instruments':['drums']}
                with patch('stems_view.shutil.which', return_value=str(root/'ffmpeg.exe')), patch.object(page, 'begin_job'):
                    self.assertTrue(page.start_midi_item(request))
                self.assertEqual(page.commands[1][-2:], ['--instruments', 'drums'])
                self.assertEqual(page.commands[2][-2:], ['--instruments', 'drums'])
            finally:
                if page.log: page.log.close(); page.log = None
                page.close(); page.deleteLater(); app.processEvents()

    def test_replaced_stem_is_unrestricted_and_saved_original_beats_same_title_picker(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            root=Path(temp); song=root/'separated'/'Song'; song.mkdir(parents=True)
            original=root/'original.wav'; original.touch()
            replacement=root/'Song.wav'; replacement.touch()
            stem=song/'drums.wav'; stem.write_bytes(b'changed audio')
            (song/'stem-manifest-test.json').write_text(json.dumps({
                'source':str(original), 'files':{stem.name:{'instruments':['drums'],
                    'sha256':hashlib.sha256(b'old audio').hexdigest()}}}))
            page=StemSlicerPage(lambda:None,root)
            try:
                page.set_source(replacement)
                self.assertEqual(page.files.item(0).data(Qt.ItemDataRole.UserRole)['audio'], str(original))
                page.files.item(1).setCheckState(Qt.CheckState.Checked)
                with patch.object(page, 'start_next_midi'):
                    page.start_midify()
                self.assertEqual(page.midi_queue[0].get('instruments'), [])
                original.unlink()
                page.set_source(replacement)
                self.assertEqual(page.files.item(0).data(Qt.ItemDataRole.UserRole)['audio'], str(replacement))
            finally:
                page.close();page.deleteLater();app.processEvents()

    def test_polyphony_seconds_and_drums_survive_roundtrip(self):
        rows = [note(1, 2, 60), note(1, 3, 64), note(1, 2.5, 67), note(.5, .51, 36, 128, True)]
        midi, count, tracks = make_midi(rows, 119, 4)
        self.assertEqual((count, tracks), (4, 2))
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            path = Path(temp)/'test.mid'; midi.save(path)
            checked = mido.MidiFile(path)
            seconds, starts, ends = 0, {}, {}
            for message in checked:
                seconds += message.time
                if message.type == 'note_on':
                    starts[message.note] = seconds
                    self.assertEqual(message.channel == 9, message.note == 36)
                if message.type == 'note_off':
                    ends[message.note] = seconds
            for row in rows:
                self.assertAlmostEqual(starts[row['pitch']], row['onset'], delta=.001)
                self.assertAlmostEqual(ends[row['pitch']], row['offset'], delta=.001)
            self.assertAlmostEqual(checked.length, 4, delta=.001)

    def test_rerun_preserves_midi_and_empty_detection_publishes_nothing(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            folder = Path(temp)
            raw = folder/'audio.f32'; raw.write_bytes(bytes(64000*3))
            audio = folder/'audio.wav'; audio.touch()
            notes = folder/'notes.tsv'
            fields = list(note(0,1,60))
            with notes.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fields, delimiter='\t'); writer.writeheader()
                writer.writerow(note(0, 1, 60))
            output = folder/'out'
            result = export(notes, audio, raw, output, 'guitar-L', 119, folder/'done.json')
            before = (output/result['files'][0]).read_bytes()
            again = export(notes, audio, raw, output, 'guitar-L', 119, folder/'done.json')
            self.assertEqual(again['files'], ['guitar-L-2.mid'])
            self.assertEqual((output/'guitar-L.mid').read_bytes(), before)
            notes.write_text('\t'.join(fields)+'\n')
            with self.assertRaisesRegex(ValueError, 'No notes detected'):
                export(notes, audio, raw, output, 'empty', 119, folder/'done.json')
            self.assertFalse((output/'empty.mid').exists())

    def test_original_available_without_stems(self):
        app = QApplication.instance() or QApplication([])
        page = StemSlicerPage(lambda: None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
                audio = Path(temp)/'song.wav'; audio.touch()
                page.set_source(audio)
                for container in list(page.containers):
                    page.remove_stem(container)
                self.assertFalse(page.start.isEnabled())
                self.assertIn('ORIGINAL', page.files.item(0).text())
                page.files.item(0).setCheckState(Qt.CheckState.Checked)
                self.assertTrue(page.midify.isEnabled())
                page.running = True; page.update_midi_actions()
                self.assertFalse(page.midify.isEnabled())
                page.running = False
        finally:
            page.close(); page.deleteLater(); app.processEvents()

    def test_song_checklist_previews_midi_but_only_converts_audio(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            root = Path(temp)
            original = root/'first.wav'; original.touch()
            other = root/'second.wav'; other.touch()
            song = root/'separated'/'First'; song.mkdir(parents=True)
            stem = song/'custom guitar.wav'; stem.touch()
            midi = song/'custom guitar.mid'; midi.touch()
            (song/'stem-manifest-test.json').write_text(json.dumps({'source':str(original),'files':[stem.name]}))
            (song/'midi-manifest-test.json').write_text(json.dumps({'source':str(stem),'files':[midi.name]}))
            page = StemSlicerPage(lambda: None, root)
            try:
                page.set_source(other)
                page.results.setCurrentIndex(page.results.findData(str(song)))
                self.assertEqual(page.files.count(), 3)
                self.assertEqual(page.files.item(0).data(Qt.ItemDataRole.UserRole)['audio'], str(original))
                for i in range(3): page.files.item(i).setCheckState(Qt.CheckState.Checked)
                self.assertEqual([r['audio'] for r in page.checked_audio()], [str(original), str(stem)])
                self.assertEqual(page.preview.paths, [original, stem, midi])
                page.refresh_results(str(song))
                self.assertEqual(page.preview.paths, [original, stem, midi])
                with patch.object(page, 'start_next_midi'):
                    page.start_midify()
                self.assertEqual(page.midi_total, 2)
                self.assertEqual([r['original'] for r in page.midi_queue], [True, False])
                self.assertTrue(all(r['output'] == str(song) for r in page.midi_queue))
                page.midi_done = [midi]
                page.finish('CANCELLED')
                self.assertEqual(page.midi_queue, [])
                self.assertIn('1 of 2', page.status.text())
                self.assertTrue(midi.exists())
            finally:
                page.close(); page.deleteLater(); app.processEvents()

    def test_custom_filename_survives_instrument_changes_and_rejects_paths(self):
        app = QApplication.instance() or QApplication([])
        page = StemSlicerPage(lambda: None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
                audio = Path(temp)/'song.wav'; audio.touch(); page.set_source(audio)
                row = page.containers[0]
                row.name_edited('My solo.mp3'); page.definitions_changed()
                row.checks['bass'].setChecked(True)
                self.assertEqual(row.filename.text(), 'My solo.mp3')
                page.format_combo.setCurrentIndex(1)
                self.assertEqual(row.filename.text(), 'My solo.wav')
                row.name_edited('../escape'); page.definitions_changed()
                self.assertFalse(page.start.isEnabled())
                row.name_edited(''); page.definitions_changed()
                self.assertTrue(page.start.isEnabled())
                self.assertIn('-B-L.wav', row.filename.text())
        finally:
            page.close(); page.deleteLater(); app.processEvents()
