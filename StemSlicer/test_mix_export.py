"""Exercise overlapping stem contents, encoding, naming, and preserved exports."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np

from export_stems import decode, export
from recipe_spec import output_bases, song_title, validate_stems

ROOT = Path(__file__).resolve().parent


class MixExportTests(unittest.TestCase):
    def test_overlapping_mixes_have_requested_audio_and_preserve_prior_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'verification', prefix='mix-test-') as folder:
            root = Path(folder)
            instruments, guitars = root / 'instruments', root / 'guitars'
            instruments.mkdir(); guitars.mkdir()
            time = np.arange(44100) / 44100
            lead = np.repeat((.1 * np.sin(2 * np.pi * 440 * time))[:, None], 2, axis=1)
            rhythm = np.repeat((.2 * np.sin(2 * np.pi * 660 * time))[:, None], 2, axis=1)
            for path, samples in ((root/'source.wav', lead+rhythm),
                                  (guitars/'lead-guitar.wav', lead), (guitars/'rhythm-guitar.wav', rhythm)):
                subprocess.run(['ffmpeg','-v','error','-f','f64le','-ar','44100','-ac','2',
                                '-i','pipe:0','-c:a','pcm_f32le',str(path)],
                               input=samples.astype('<f8').tobytes(),check=True)
            plan = {'title':'Wasteland', 'format':'both', 'stems':[['lead-guitar'], ['lead-guitar','rhythm-guitar']]}
            output = root/'separated'/'Wasteland'
            with contextlib.redirect_stdout(io.StringIO()):
                export(root/'source.wav', instruments, guitars, output, plan, root/'complete.json')
            result = json.loads((root/'complete.json').read_text())
            self.assertEqual(set(result['files']), {'wasteland-L.wav','wasteland-L.mp3','wasteland-L-R.wav','wasteland-L-R.mp3'})
            _, left = decode(output/'wasteland-L.wav')
            _, mixed = decode(output/'wasteland-L-R.wav')
            np.testing.assert_allclose(left, lead, atol=2/2**23)
            np.testing.assert_allclose(mixed, lead+rhythm, atol=2/2**23)
            _, mp3 = decode(output/'wasteland-L-R.mp3')
            self.assertEqual(mp3.shape,mixed.shape)
            self.assertGreater(np.corrcoef(mp3[:,0],mixed[:,0])[0,1],.99)
            previous = {name:(output/name).read_bytes() for name in result['files']}
            with contextlib.redirect_stdout(io.StringIO()):
                export(root/'source.wav', instruments, guitars, output, plan, root/'complete2.json')
            rerun = json.loads((root/'complete2.json').read_text())
            self.assertIn('wasteland-L-R-2.mp3',rerun['files'])
            for name, content in previous.items():
                self.assertEqual((output/name).read_bytes(),content)
            plan['names'] = ['My solo', 'My backing']
            with contextlib.redirect_stdout(io.StringIO()):
                export(root/'source.wav', instruments, guitars, output, plan, root/'custom.json')
            custom = json.loads((root/'custom.json').read_text())
            self.assertEqual(set(custom['files']), {'My solo.wav', 'My solo.mp3', 'My backing.wav', 'My backing.mp3'})
            _, renamed = decode(output/'My solo.wav')
            np.testing.assert_allclose(renamed, lead, atol=2/2**23)

    def test_empty_unknown_duplicate_and_unsafe_names(self):
        for stems in ([], [[]], [['invalid']]):
            with self.assertRaises(ValueError): validate_stems(stems)
        self.assertEqual(output_bases('Wasteland', [['lead-guitar'],['lead-guitar']],['WASTELAND-L']),
                         ['wasteland-L-2','wasteland-L-3'])
        for title in ('../Elsewhere','CON','Hello/World','A:B'):
            safe = song_title(title)
            self.assertEqual(Path(safe).name,safe)
            self.assertNotIn(':',safe)
        self.assertEqual(output_bases('Song', [['bass'], ['drums']], ['SOLO'], ['Solo', 'Solo']), ['Solo-2', 'Solo-3'])
        for name in ('../escape', 'NUL', 'folder/file', 'bad:name', '..', 'CON.wav'):
            with self.assertRaises(ValueError):
                output_bases('Song', [['bass']], names=[name])


if __name__ == '__main__': unittest.main()
