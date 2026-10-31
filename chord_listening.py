"""Guided, unscored guitar capture. A strum is a cue, never a chord transcription."""
import json
import logging
import time
from PySide6.QtCore import QObject, Signal
from audio import Capture, DEFAULT_GATE_DB

OPEN = (40, 45, 50, 55, 59, 64)
NAMES = ('low E', 'A', 'D', 'G', 'B', 'high E')


class ChordPass:
    def __init__(self, gate):
        self.gate = gate
        self.stage = 'noise'
        self.index = 0
        self.frets = [None]*6
        self.kinds = ['pending']*6
        self.noise = []
        self.noise_seconds = 0.
        self.floor = -90.
        self.after = 0.
        self.heard = None
        self.message = 'Mute all strings briefly to measure the background.'
        self._clear_event()

    def _clear_event(self):
        self.quiet = 0.
        self.armed = False
        self.event = None

    def state(self):
        return dict(stage=self.stage, index=self.index, frets=list(self.frets),
                    kinds=list(self.kinds), message=self.message, heard=self.heard)

    def _prompt(self):
        self.message = f'Play string {6-self.index} ({NAMES[self.index]}), then mute. A muted pluck counts too.'

    def _advance(self, fret, kind, now):
        self.frets[self.index] = fret
        self.kinds[self.index] = kind
        logging.info('Chord listening string=%s fret=%s result=%s', 6-self.index, fret, kind)
        self.index += 1
        self.after = now
        self._clear_event()
        self.heard = None
        if self.index == 6:
            self.stage = 'complete'
            self.message = 'Six strings captured. Review the dots; you can correct them by clicking.'
        else:
            self._prompt()

    def frame(self, f):
        if self.stage in ('complete', 'error') or f['monotonic'] <= self.after:
            return
        dt = f.get('duration', 0)
        if f.get('clipped') or f.get('overflow'):
            self._clear_event()
            self.message = 'Input clipped or interrupted. Mute, then try this string again.'
            self.heard = None
            return
        if self.stage == 'noise':
            self.noise.append(f['db']);self.noise_seconds += dt
            if self.noise_seconds >= 1.2:
                ordered = sorted(self.noise)
                self.floor = ordered[int(.9*(len(ordered)-1))]
                if self.floor > -25 or any(x > self.gate for x in self.noise):
                    self.stage = 'error'
                    self.message = 'The background check heard a loud signal. Mute the strings and start listening again.'
                    return
                self.gate = max(self.gate, self.floor+12)
                self.stage = 'strum'
                self.message = 'Strum your chord once, then mute all strings.'
                self._clear_event()
                self.armed = True  # The background measurement already supplied the gap.
            return
        raw = f.get('raw_pitch')
        self.heard = raw if raw and raw.get('periodicity', 0) >= .9 and f['db'] >= self.gate-6 else None
        below = f['db'] < self.gate-6
        self.quiet = self.quiet+dt if below else 0.
        if self.quiet >= .3:
            if self.stage == 'strum-release':
                self.stage = 'strings';self.after = f['monotonic'];self._clear_event();self._prompt()
                self.armed = True
                return
            if self.event is not None:
                event = self.event
                self.event = None
                if (self.stage == 'strings' and .02 <= event['duration'] <= .35
                        and not event['pitched'] and event['broadband']
                        and event['peak'] >= max(self.gate, self.floor+18)):
                    self._advance(None, 'muted', f['monotonic'])
                    self.armed = True  # This event ended with the required quiet gap.
                    return
                self.message = 'Sound was unclear. Pick this string again and let a fretted note ring briefly, then mute.'
            self.armed = True
        if self.stage == 'strum' and self.armed and f['db'] >= self.gate:
            self.stage = 'strum-release'
            self.message = 'Strum received. Mute all strings; next is low E.'
            return
        if self.stage != 'strings':
            return
        if self.armed and self.event is None and f['db'] >= self.gate:
            self.event = dict(duration=0., pitched=False, broadband=False, peak=-100.)
        if self.event is not None and not below:
            self.event['duration'] += dt
            self.event['pitched'] |= raw is not None
            self.event['broadband'] |= f.get('flatness', 0) >= .18
            self.event['peak'] = max(self.event['peak'], f['db'])

    def note(self, p):
        if (self.stage != 'strings' or not self.armed or p.get('started', 0) <= self.after
                or p.get('periodicity', 0) < .95 or p.get('clipped')):
            return
        fret = p['midi']-OPEN[self.index]
        # Covers the E-shape presets at every selectable root, including fret-14 tones.
        if not 0 <= fret <= 14 or abs(p.get('cents', 0)) > 40:
            self.event = None;self.armed = False
            self.message = 'Pitch is outside frets 0–14 on this string, or too far out of tune. Mute and retry the highlighted string.'
            return
        self._advance(fret, 'note', p['monotonic'])

    def muted(self, now):
        if self.stage == 'strings': self._advance(None, 'muted-manual', now)

    def retry(self, now):
        if self.stage == 'strings' and self.index > 0:
            self.index -= 1
            self.frets[self.index] = None;self.kinds[self.index] = 'pending'
            self.after = now;self.heard = None;self._clear_event();self._prompt()


class ChordListener(QObject):
    changed = Signal(str)
    voice_status = Signal(str)
    command = Signal(str)

    def __init__(self, settings, capture_factory=Capture, available=lambda: True, parent=None, voice_factory=None):
        super().__init__(parent)
        self.settings = settings
        self.factory = capture_factory
        self.available = available
        self.voice_factory = voice_factory
        self.capture = None
        self.voice = None
        self.pass_ = None
        self.setup = None
        self.active = False
        self.calibrated = False
        self.last_frame = {}
        self.last_log = 0.
        self.gate = -75.
        self.floor = -90.
        self.last_stage = None
        self.references = [0.]*6
        self.input_settings = {}

    def publish(self, message=None, stage=None):
        if self.setup:
            state = dict(stage=self.setup.stage,index=self.setup.index,frets=[None]*6,kinds=['pending']*6,message=self.setup.message)
        elif self.pass_:
            state = self.pass_.state()
        else:
            state = dict(stage='ready',index=0,frets=[None]*6,kinds=['pending']*6,message='Listening is ready — click or say Go.')
        f = self.last_frame
        state.update(heard=f.get('raw_pitch'),db=f.get('db'),gate=self.setup.gate if self.setup else self.gate,calibrated=self.calibrated,
                     clipped=f.get('clipped',False),input=self.input_settings.get('input',''),channel=self.input_settings.get('channel',0))
        if message is not None: state['message'] = message
        if stage is not None: state['stage'] = stage
        if state['stage'] != self.last_stage:
            logging.info('Painter phase=%s index=%s gate=%.1f message=%s',state['stage'],state['index'],self.gate,state['message'])
            self.last_stage = state['stage']
        self.changed.emit(json.dumps(state))

    def start(self):
        from guitar_setup import GuitarSetup
        if not self.active and (self.capture is not None or self.voice is not None):
            self.publish('Inputs are still stopping. Retry Recalibrate in a moment.','error')
            return
        if self.capture is not None:
            if self.active:
                self.calibrated=False;self.pass_=None;self.setup=GuitarSetup()
                self.capture.reset_detection();self.publish()
            else: self.publish('Audio is still stopping. Retry in a moment.','error')
            return
        settings = self.settings()
        self.input_settings = dict(settings)
        if not self.available() or not settings.get('input'):
            self.publish('Choose a guitar input in Home → Connection settings, and stop other practice capture first.','error')
            return
        self.setup=GuitarSetup();self.pass_=None;self.calibrated=False
        self.active=True;self.last_frame={};self.gate=-75.
        capture=self.factory(settings['input'],settings.get('channel',0),self.gate,self)
        self.capture=capture
        capture.set_hold_seconds(.3)
        capture.opened.connect(lambda name: self.opened(name))
        capture.frame.connect(self.frame);capture.note.connect(self.note)
        capture.failed.connect(self.failed);capture.finished.connect(lambda: self.finished(capture))
        logging.info('Painter opening input=%s channel=%s',settings['input'],settings.get('channel',0))
        self.publish('Opening guitar input for calibration…','opening');capture.start()

    def opened(self,name):
        if not self.active:return
        self.publish()
        if self.voice is None and self.voice_factory:
            voice=self.voice_factory(self);self.voice=voice
            voice.command.connect(self.voice_command);voice.status.connect(self.voice_status)
            voice.finished.connect(lambda:self.voice_finished(voice));voice.start()

    def voice_command(self,word):
        if self.active:self.command.emit(word)

    def voice_finished(self,voice):
        if self.voice is voice:self.voice=None
        voice.deleteLater()

    def begin(self):
        if not self.active or not self.calibrated or self.setup:return
        self.pass_=ChordPass(self.gate);self.pass_.floor=self.floor
        self.pass_.stage='strum';self.pass_.after=time.monotonic()
        self.pass_.message='Mute briefly, strum your chord, mute again, then pick the highlighted strings.'
        self.capture.reset_detection();self.publish()

    def check(self,string,fret):
        from guitar_setup import GuitarSetup
        if not self.active or not self.calibrated or not 1<=string<=6 or not 0<=fret<=14:return
        self.pass_=None;self.setup=GuitarSetup((6-string,fret));self.capture.reset_detection();self.publish()

    def help(self):
        f=self.last_frame
        logging.warning('Painter incident note-not-detected phase=%s db=%s gate=%s raw=%s clipped=%s overflow=%s action=recalibrate',
                        self.last_stage,f.get('db'),self.gate,f.get('raw_pitch'),f.get('clipped'),f.get('overflow'))
        self.start()

    def frame(self,frame):
        if not self.active:return
        self.last_frame=frame
        if self.setup:
            self.setup.frame(frame)
            if self.setup.stage=='ready':
                if not self.setup.check:
                    self.gate=self.setup.gate;self.floor=self.setup.floor;self.calibrated=True
                    self.references=[r['cents'] for r in self.setup.readings]
                    logging.info('Painter calibration passed gate=%.1f floor=%.1f references=%s',self.gate,self.floor,self.setup.readings)
                else:logging.info('Painter extra note check passed: %s',self.setup.readings)
                self.setup=None;self.capture.set_gate(self.gate);self.capture.reset_detection()
            elif self.setup.stage=='error':
                self.publish();self.stop(notify=False);return
        elif self.pass_:
            self.pass_.frame(frame)
        if frame['monotonic']-self.last_log>=5:
            self.last_log=frame['monotonic']
            logging.info('Painter signal phase=%s db=%.1f gate=%.1f raw=%s quiet=%s clipped=%s overflow=%s',
                         self.last_stage,frame['db'],self.gate,frame.get('raw_pitch'),frame.get('quiet'),frame.get('clipped'),frame.get('overflow'))
        self.publish()

    def note(self,pitch):
        if not self.active or self.setup or not self.pass_ or self.pass_.stage=='complete':return
        before=self.pass_.index
        # Compare to this session's measured tuning, not the requested chord.
        import math
        adjusted=dict(pitch)
        midi_float=69+12*math.log2(pitch['hz']/440)-self.references[before]/100
        adjusted['midi']=round(midi_float);adjusted['cents']=(midi_float-adjusted['midi'])*100
        self.pass_.note(adjusted)
        if self.pass_.index!=before:self.capture.reset_detection()
        else:logging.info('Painter rejected note=%s stage=%s string=%s reason=%s',pitch,self.pass_.stage,6-self.pass_.index,self.pass_.message)
        self.publish()

    def muted(self):
        if self.active and self.pass_:
            self.pass_.muted(time.monotonic());self.capture.reset_detection();self.publish()

    def retry(self):
        if self.active and self.pass_:
            self.pass_.retry(time.monotonic());self.capture.reset_detection();self.publish()

    def failed(self,message):
        if self.active:
            logging.warning('Chord listening input failure: %s',message)
            self.publish(message,'error');self.stop(notify=False)

    def stop(self,notify=True):
        self.active=False;self.calibrated=False
        if self.capture is not None:self.capture.stop()
        if self.voice is not None:self.voice.stop()
        if notify:self.publish('Play stopped. Select Play or Recalibrate to start again.','stopped')

    def finished(self,capture):
        if self.capture is capture:
            if self.active:self.failed('The audio input stopped. Recalibrate to reconnect.')
            self.capture=None
        capture.deleteLater()

    def shutdown(self):
        self.stop(notify=False)
        audio_done=self.capture is None or self.capture.wait(3000)
        voice_done=self.voice is None or self.voice.wait(3000)
        return audio_done and voice_done
