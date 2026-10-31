"""Preview timing, polyphony, mixing, cancellation and failure checks."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import patch

import mido
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer

from preview_player import RATE, PreviewCancelled, PreviewPlayer, prepare_mix, render_midi

ROOT = Path(__file__).resolve().parent
FONT = ROOT / 'StemSlicer/playback/FluidR3Mono_GM.sf3'


def write_wave(path, samples):
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim == 1:
        samples = np.repeat(samples[:, None], 2, axis=1)
    with wave.open(str(path), 'wb') as output:
        output.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
        output.writeframes((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())


def read_wave(path):
    with wave.open(str(path), 'rb') as source:
        return np.frombuffer(source.readframes(source.getnframes()), dtype='<i2').reshape(-1, 2) / 32768


def make_midi(path, notes=(69, 76), program=0, channel=0):
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack(); midi.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=500000))
    track.append(mido.Message('program_change', channel=channel, program=program))
    for index, note in enumerate(notes):
        track.append(mido.Message('note_on', channel=channel, note=note, velocity=90, time=480 if index == 0 else 0))
    track.append(mido.MetaMessage('set_tempo', tempo=1000000, time=480))
    for index, note in enumerate(notes):
        track.append(mido.Message('note_off', channel=channel, note=note, time=480 if index == 0 else 0))
    midi.save(path)


class PreviewTests(unittest.TestCase):
    def test_stem_window_fits_transport_without_clipping_bottom_controls(self):
        from app import MainWindow, apply_theme
        app = QApplication.instance() or QApplication([])
        apply_theme(app)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
            with patch('app.input_devices', return_value=[]):
                window = MainWindow(Path(temp), ROOT/'FretboardFiend/lessons')
            try:
                window.splash_timer.stop()
                window.show_stems(); window.show(); app.processEvents()
                self.assertEqual(window.width(), 800)
                self.assertGreaterEqual(window.height(), window.stems.minimumHeight())
                self.assertLessEqual(window.stems.midify.mapTo(window.stems, window.stems.midify.rect().bottomRight()).y(), window.height())
            finally:
                window.close(); window.deleteLater(); app.processEvents()

    def test_real_polyphonic_midi_preserves_leading_silence_and_tempo_changes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as temp:
            folder = Path(temp)
            source, output = folder/'chord.mid', folder/'chord.f32'
            make_midi(source)
            frames = render_midi(source, output, FONT)
            samples = np.fromfile(output, dtype='<f4').reshape(-1, 2).mean(axis=1)
            self.assertEqual(frames, 3 * RATE)  # 0.5 silence + 1.5 notes + 1 release
            self.assertEqual(float(np.max(np.abs(samples[:int(.49 * RATE)]))), 0)
            self.assertGreater(float(np.max(np.abs(samples[int(.6 * RATE):int(1.8 * RATE)]))), .01)
            segment = samples[int(.6 * RATE):int(1.0 * RATE)]
            spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))
            frequencies = np.fft.rfftfreq(len(segment), 1 / RATE)
            for hz in (440, 659.25):
                self.assertGreater(spectrum[np.abs(frequencies - hz) < 8].max(), spectrum.max() * .05)

    def test_mixed_stems_are_aligned_and_do_not_jump_in_gain_at_shorter_end(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as temp:
            folder = Path(temp)
            first = np.zeros(RATE); first[10000:15000] = .2; first[35000:40000] = .2
            second = np.zeros(RATE // 2); second[10000:15000] = .4
            write_wave(folder/'one.wav', first); write_wave(folder/'two.wav', second)
            output = prepare_mix([folder/'one.wav', folder/'two.wav'], folder, FONT)
            mixed = read_wave(output)[:, 0]
            self.assertEqual(len(mixed), RATE)
            self.assertAlmostEqual(float(mixed[11000:14000].mean()), .3, places=3)
            self.assertAlmostEqual(float(mixed[36000:39000].mean()), .1, places=3)
            self.assertLess(np.max(np.abs(mixed[:9900])), .0001)

    def test_two_midis_keep_separate_programs_and_drums_when_mixed_with_audio(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as temp:
            folder = Path(temp)
            make_midi(folder/'piano.mid', notes=(60,), program=0)
            make_midi(folder/'guitar.mid', notes=(64,), program=26)
            make_midi(folder/'drums.mid', notes=(36,), channel=9)
            write_wave(folder/'stem.wav', np.zeros(3 * RATE))
            paths = [folder/name for name in ('piano.mid', 'guitar.mid', 'drums.mid', 'stem.wav')]
            output = prepare_mix(paths, folder, FONT)
            mixed = read_wave(output)
            rendered = [np.fromfile(folder/f'midi-{i}.f32', dtype='<f4').reshape(-1, 2) for i in range(3)]
            expected = sum(rendered) / 4
            self.assertEqual(mixed.shape, expected.shape)
            self.assertGreater(np.max(np.abs(mixed)), .01)
            self.assertLess(float(np.max(np.abs(mixed - expected))), .0002)
            self.assertFalse(np.allclose(rendered[0], rendered[1]))
            self.assertGreater(np.max(np.abs(rendered[2])), .01)

    def test_cancel_and_bad_file_do_not_publish_preview(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as temp:
            folder = Path(temp)
            make_midi(folder/'song.mid')
            with self.assertRaises(PreviewCancelled):
                prepare_mix([folder/'song.mid'], folder, FONT, lambda: True)
            (folder/'bad.mid').write_bytes(b'not MIDI')
            with self.assertRaises(Exception):
                prepare_mix([folder/'bad.mid'], folder, FONT)
            self.assertFalse((folder/'preview.wav').exists())

    def test_stop_before_worker_result_prevents_late_playback_and_cleans_temp(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as temp:
            root = Path(temp)
            write_wave(root/'song.wav', np.zeros(RATE))
            player = PreviewPlayer(root)
            try:
                player.set_files([root/'song.wav'])
                with patch('preview_player.QMediaDevices.defaultAudioOutput') as device:
                    device.return_value.isNull.return_value = False
                    player.toggle()
                    player.worker.wait()  # Ready signal is still queued on GUI thread.
                    player.stop()
                    app.processEvents()
                self.assertEqual(player.player.playbackState(), QMediaPlayer.PlaybackState.StoppedState)
                self.assertTrue(player.player.source().isEmpty())
                self.assertEqual(list((root/'preview-cache').iterdir()), [])
                self.assertTrue(player.play.isEnabled())
            finally:
                player.shutdown(); player.deleteLater(); app.processEvents()


if __name__ == '__main__':
    unittest.main()
