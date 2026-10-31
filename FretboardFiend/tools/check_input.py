"""Bounded hardware check through the same capture path as the Windows app."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication, QTimer
from audio import Capture, input_devices, DEFAULT_GATE_DB

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--pair", choices=["1/2", "3/4", "5/6", "7/8", "9/10", "11/12"], default="11/12")
parser.add_argument("--channel", type=int, choices=[1, 2], default=1, help="Channel within the selected pair")
parser.add_argument("--seconds", type=int, choices=range(1, 31), default=5)
args = parser.parse_args()
app = QCoreApplication([])
matches = [d for d in input_devices() if f"M12 In {args.pair}" in d["name"]]
if len(matches) != 1:
    raise SystemExit(f"Expected exactly one Model 12 input {args.pair}. No fallback selected.")
result = dict(device=matches[0]["name"], usb_input_channel=int(args.pair.split('/')[args.channel-1]), frames=0,
              overflows=0, clipped=0, note_events=0, errors=[], peak_rms_db=-200)
capture = Capture(matches[0]["name"],args.channel-1,DEFAULT_GATE_DB)
def frame(value):
    result["frames"] += 1
    result["overflows"] += int(value["overflow"])
    result["clipped"] += int(value["clipped"])
    result["peak_rms_db"] = max(result["peak_rms_db"],value["db"])
def note(value):
    result["note_events"] += 1
capture.frame.connect(frame)
capture.note.connect(note)
capture.failed.connect(result["errors"].append)
capture.finished.connect(app.quit)
QTimer.singleShot(args.seconds*1000,capture.stop)
capture.start()
app.exec()
if not capture.wait(3000):
    raise SystemExit("Input failed to release within three seconds")
print(json.dumps(result,indent=2))
raise SystemExit(1 if result["errors"] or result["frames"] == 0 else 0)
