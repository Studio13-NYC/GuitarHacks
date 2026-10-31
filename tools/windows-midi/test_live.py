"""Opt-in integration check: uses only the dedicated GuitarHacks loopback.

Run from the project root: uv run --frozen --group build python tools/windows-midi/test_live.py
No hardware MIDI, audio stream, driver, or service is modified.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import mido
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from jam_view import JamPage
from practice import Store

app = QApplication([])
root = Path(__file__).resolve().parents[2] / 'build' / 'windows-midi-qa'
root.mkdir(parents=True, exist_ok=True)
folder = Path(tempfile.mkdtemp(prefix='live-', dir=root))
store = Store(folder)
page = JamPage(store, lambda: None)
page.show()

def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), page.status.text()

try:
    page.toggle_connection()
    wait_for(lambda: bool(page.connection))
    identity = page.connection['endpoint']
    send_name = next(n for n in mido.get_output_names() if n.startswith('GuitarHacks Jam Send '))
    receive_name = next(n for n in mido.get_input_names() if n.startswith('GuitarHacks Jam Receive '))
    with mido.open_output(send_name) as output, mido.open_input(receive_name) as observer:
        page.toggle_recording()
        wait_for(lambda: page.take is not None)
        seq = [mido.Message('note_on', note=n, velocity=80) for n in (48, 52, 55)]
        for message in seq:
            output.send(message)
        # Deliberately pause Qt processing: reception timestamps must still reflect the service clock.
        time.sleep(.2)
        for n in (48, 52, 55):
            message = mido.Message('note_off', note=n)
            seq.append(message)
            output.send(message)
        wait_for(lambda: len(page.take.raw) >= 6)
        assert list(observer.iter_pending()) == seq
        assert all(.17 < note.duration < .5 for note in page.take.notes), page.take.notes
        page.toggle_recording()
        wait_for(lambda: page.take is None)
        path = Path(page.takes.currentData())
        midi = mido.MidiFile(path)
        assert len([m for t in midi.tracks for m in t if m.type == 'note_on']) == 3
        raw = json.loads(path.with_suffix('.ump.json').read_text())
        assert len(raw['events']) == 6
        page.disconnect()
        page.toggle_connection()
        wait_for(lambda: bool(page.connection))
        assert page.connection['endpoint'] == identity
        page.toggle_recording()
        wait_for(lambda: page.take is not None)
        output.send(mido.Message('note_on', note=64, velocity=70))
        wait_for(lambda: bool(page.take.notes))
        page.port.process.kill()  # Only our helper: simulate its unexpected exit.
        wait_for(lambda: page.port is None)
        assert page.take is None
        partial = json.loads(Path(page.takes.currentData()).with_suffix('.ump.json').read_text())
        assert any('Incomplete' in w for w in partial['warnings'])
    report = dict(result='passed', tests=['WinMM to SDK', 'two simultaneous readers',
                  'source timestamps despite delayed UI', 'three-note MIDI export',
                  'original UMP sidecar', 'endpoint reuse', 'helper crash saves partial take'],
                  evidence=str(folder), fullTake=str(path))
    (folder/'result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
finally:
    page.disconnect()
    page.close()
    store.close()
