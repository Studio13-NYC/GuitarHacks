"""Exercise the compiled transcription host's argument validation without loading weights."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent
ENGINE = Path(os.environ.get('MIDI_TEST_ENGINE', ROOT/'NeuralNote/cli/build/Release/guitarhacks-transcribe.exe'))


@unittest.skipUnless(ENGINE.is_file(), 'Build the native MIDI engine first')
class NativeOptionsTests(unittest.TestCase):
    def test_lists_authoritative_instrument_names_without_loading_model(self):
        result = subprocess.run([str(ENGINE), '--list-instruments'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        names = result.stdout.splitlines()
        self.assertEqual(len(names), 35)
        self.assertEqual(len(set(names)), 35)
        for name in ('drums', 'voice', 'acoustic_bass', 'electric_bass',
                     'acoustic_guitar', 'clean_electric_guitar', 'distorted_electric_guitar'):
            self.assertIn(name, names)

    def test_rejects_invalid_empty_and_missing_selection_before_audio_or_model_load(self):
        for selection, error in ((['drumz'], 'Unknown instrument'), (['drums,'], 'Empty instrument'),
                                 ([''], 'Empty instrument'), ([], 'requires one'),
                                 (['\u03b4rums'], 'Unknown instrument')):
            with self.subTest(selection=selection):
                result = subprocess.run([str(ENGINE), 'absent.gguf', 'absent.f32', 'absent.tsv',
                                         '--instruments', *selection], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error, result.stderr)
                self.assertNotIn('Cannot open decoded audio', result.stderr)
                self.assertNotIn('MODEL_PROGRESS', result.stdout)
