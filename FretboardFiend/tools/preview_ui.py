"""Visible UI smoke check with isolated generated input; F6 cycles states."""
import os
os.environ['QT_QPA_PLATFORM']='windows'
import sys
import tempfile
import time
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QTimer
from PySide6.QtGui import QShortcut,QKeySequence
from PySide6.QtWidgets import QApplication
from app import MainWindow,apply_theme
from exercises import make_exercise
from session import Session
from everywhere import EverywhereSession
from test_flashcards import SyntheticCapture

app=QApplication([])
apply_theme(app)
with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
    w=MainWindow(Path(folder),ROOT/'lessons',SyntheticCapture)
    w.setWindowTitle('GuitarHacks · UI check · generated input')
    w.splash_timer.stop()
    w.clock_timer.stop()
    w.settings.update(input='QA generated audio',cues=False)
    phases=['splash','setup','playing','warning','retry','correct','gap','everywhere','results']
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=phases,default='splash')
    parser.add_argument('--compact',action='store_true')
    args=parser.parse_args()
    index=[phases.index(args.phase)]
    if args.compact:w.resize(680,640)
    def show():
        phase=phases[index[0]]
        w.next_timer.stop()
        w.transition=None
        if phase=='splash':w.pages.setCurrentWidget(w.splash)
        elif phase=='setup':
            w.mode_buttons[3].setChecked(True)
            w.note_combo.setCurrentIndex(2)
            w.config_changed()
            w.show_setup()
        elif phase=='everywhere':
            w.session.quit()
            w.session=EverywhereSession(w.store)
            w.session.start(make_exercise(4,0))
            w.capture=SyntheticCapture('QA',0,-36,w)
            w.show_card()
            for midi in (48,50,60,60):
                w.audio_frame(dict(quiet=True,monotonic=time.monotonic()))
                w.audio_note(dict(midi=midi,cents=0,periodicity=.99,started=time.monotonic()))
            w.session.run_started-=24
            w.flash_until=0
            w.tick()
        elif phase=='results':
            w.session.quit()
            w.session=Session(w.store)
            w.session.start(make_exercise(),now=time.monotonic()-103)
            for number in range(12):
                w.session.started=time.monotonic()-(2+number)
                if number==3:
                    w.session.started=time.monotonic()-20
                    w.session.tick()
                else:
                    if number%3==0:
                        w.session.frame(dict(quiet=True,monotonic=time.monotonic()))
                        w.session.note(dict(midi=w.session.card.midi+1,cents=0,periodicity=.99,started=time.monotonic()))
                    w.session.frame(dict(quiet=True,monotonic=time.monotonic()))
                    w.session.note(dict(midi=w.session.card.midi,cents=0,periodicity=.99,started=time.monotonic()))
                if w.session.active:w.session.next()
            w.show_complete()
        else:
            if not w.session.active:
                w.capture=SyntheticCapture('QA',0,-36,w)
                w.session.start(make_exercise(3,2,5))
            w.show_card()
            w.session.started=time.monotonic()-(17.05 if phase=='warning' else 8)
            w.tick()
            if phase=='retry':w.paint_note('#ff606b',True)
            if phase=='correct':w.paint_note('#83ed9e',True)
            if phase=='gap':
                w.transition='result'
                w.advance_step()
                w.next_timer.stop()
        print(phase,flush=True)
    def next_phase():
        index[0]=(index[0]+1)%len(phases)
        show()
    shortcut=QShortcut(QKeySequence('F6'),w)
    shortcut.activated.connect(next_phase)
    w.show()
    show()
    app.exec()
