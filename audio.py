"""Local input capture and Windows speech, isolated from the UI thread."""
import queue
import ctypes
import threading
import time

import numpy as np
from PySide6.QtCore import QThread, Signal
import sounddevice as sd

from monitor import estimate_pitch

DEFAULT_GATE_DB = -36


def input_devices():
    apis = sd.query_hostapis()
    return [dict(d, index=i) for i,d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0 and apis[d["hostapi"]]["name"] == "Windows WASAPI"]


class PitchTracker:
    """Require quiet, a clear onset, then half a second of stable pitch."""
    def __init__(self, gate=DEFAULT_GATE_DB, hold_seconds=.5):
        self.gate = gate
        self.hold_seconds = hold_seconds
        self.recent = []
        self.quiet_seconds = 0.0
        self.ready = False
        self.candidate = False

    def process(self, samples, rate, overflow=False, now=None):
        now = time.monotonic() if now is None else now
        x = np.asarray(samples, dtype=float)
        db = float(20*np.log10(max(float(np.sqrt(np.mean(x*x))), 1e-10)))
        clipped = bool(np.max(np.abs(x)) >= .999)
        duration = len(x)/rate
        below_release = db < self.gate-6
        self.quiet_seconds = self.quiet_seconds+duration if below_release and not overflow else 0.0
        if self.quiet_seconds >= .3:
            self.ready = True
            self.candidate = False
        if self.ready and db >= self.gate and not clipped and not overflow:
            self.candidate = True
        # Hysteresis lets a picked note decay without treating low-level noise as an onset.
        analyzing = self.ready and self.candidate and not below_release and not clipped and not overflow
        observed = estimate_pitch(x, rate) if db > -75 and not clipped and not overflow else None
        result = observed if analyzing else None
        reliable = result is not None and result["periodicity"] >= .95
        frame = dict(db=db, quiet=self.quiet_seconds >= .3, clipped=clipped,
                     overflow=bool(overflow), pitched=bool(reliable), monotonic=now,
                     duration=duration, analyzing=bool(analyzing), gate=self.gate,
                     raw_pitch=observed, ready=self.ready, hold_seconds=self.hold_seconds)
        # Broadband evidence for the guided chord listener's muted-pluck check.
        # This does not affect the single-note acceptance path below.
        frame['flatness'] = 0.0
        if observed is None and db >= self.gate-6 and not clipped and not overflow:
            spectrum = np.abs(np.fft.rfft((x-x.mean())*np.hanning(len(x))))**2
            bins = np.fft.rfftfreq(len(x), 1/rate)
            band = spectrum[(bins >= 70) & (bins <= 5000)]
            if len(band):
                frame['flatness'] = float(np.exp(np.mean(np.log(band+1e-20)))/(np.mean(band)+1e-20))
        if not reliable:
            self.recent.clear()
            return frame, None
        self.recent.append((now, result, duration, db))
        while len(self.recent)>1 and sum(r[2] for r in self.recent[1:]) >= self.hold_seconds:
            self.recent.pop(0)
        values = [r[1] for r in self.recent]
        if (sum(r[2] for r in self.recent) < self.hold_seconds or len({r["midi"] for r in values}) != 1
                or max(r["cents"] for r in values)-min(r["cents"] for r in values) > 50):
            return frame, None
        pitch = dict(result, clipped=False, db=float(np.median([r[3] for r in self.recent])),
                     monotonic=now, started=self.recent[0][0])
        for key in ("hz", "cents", "periodicity"):
            pitch[key] = float(np.median([r[key] for r in values]))
        self.ready = False
        self.candidate = False
        self.recent.clear()
        return frame, pitch


class Capture(QThread):
    opened = Signal(str)
    frame = Signal(dict)
    note = Signal(dict)
    failed = Signal(str)

    def __init__(self, name, channel, gate, parent=None):
        super().__init__(parent)
        self.device_name, self.channel, self.gate = name, channel, gate
        self.stop_event = threading.Event()
        self.reset_at = 0.0
        self.hold_seconds = .5

    def stop(self):
        self.stop_event.set()

    def set_gate(self, value):
        self.gate = float(value)

    def set_hold_seconds(self, value):
        self.hold_seconds = max(.3, min(.5, float(value)))

    def reset_detection(self):
        self.reset_at = time.monotonic()

    def run(self):
        com = ctypes.OleDLL("ole32")
        com_initialized = False
        try:
            # WASAPI uses COM on this worker as well as on the main thread.
            # Importing sounddevice on the main thread does not initialize this one.
            com.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
            com_initialized = True
            matches = [d for d in input_devices() if d["name"]==self.device_name]
            if len(matches)!=1:
                raise RuntimeError("The selected input is unavailable. Choose an input in Settings.")
            device = matches[0]
            if self.channel >= device["max_input_channels"]:
                raise RuntimeError("That channel is not available on this input.")
            rate = float(device["default_samplerate"])
            channels = min(device["max_input_channels"], max(2,self.channel+1))
            tracker = PitchTracker(self.gate, self.hold_seconds)
            reset_at = self.reset_at
            frames = queue.Queue(maxsize=8)
            dropped = False

            def callback(data, count, timing, status):
                nonlocal dropped
                try:
                    frames.put_nowait((data[:,self.channel].copy(),
                                       bool(status.input_overflow) or dropped, time.monotonic()))
                    dropped = False
                except queue.Full:
                    dropped = True

            stream = sd.InputStream(device=device["index"], samplerate=rate, channels=channels,
                                    blocksize=4096, dtype="float32", latency="high", callback=callback,
                                    extra_settings=sd.WasapiSettings(exclusive=False))
            try:
                stream.start()
                self.opened.emit(self.device_name)
                last_frame = time.monotonic()
                while not self.stop_event.is_set():
                    try:
                        data, overflowed, captured = frames.get(timeout=.2)
                    except queue.Empty:
                        if time.monotonic()-last_frame > 3:
                            raise RuntimeError("No audio data from the input. Check the device connection and other audio apps.")
                        continue
                    last_frame = time.monotonic()
                    # Delayed callback data is not a current answer.
                    overflowed = overflowed or last_frame-captured > .5
                    if tracker.gate != self.gate or tracker.hold_seconds != self.hold_seconds or reset_at != self.reset_at:
                        tracker = PitchTracker(self.gate, self.hold_seconds)
                        reset_at = self.reset_at
                    if captured < reset_at:
                        continue
                    frame, pitch = tracker.process(data, rate, overflowed, now=captured)
                    self.frame.emit(frame)
                    if pitch:
                        self.note.emit(pitch)
            finally:
                try:
                    stream.abort()
                finally:
                    stream.close()
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            if com_initialized:
                com.CoUninitialize()


def speech_options():
    import pythoncom
    from win32com.client import dynamic
    pythoncom.CoInitialize()
    try:
        voice = dynamic.Dispatch("SAPI.SpVoice")
        def items(collection):
            return [(collection.Item(i).Id,collection.Item(i).GetDescription()) for i in range(collection.Count)]
        return items(voice.GetVoices()),items(voice.GetAudioOutputs())
    finally:
        pythoncom.CoUninitialize()


class Speaker(QThread):
    started_speech = Signal(int)
    ended_speech = Signal(int)
    failed = Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.commands = queue.Queue()
        self.stop_event = threading.Event()
        self.generation = 0

    def say(self,text,voice_id,output_id):
        self.generation += 1
        token = self.generation
        self.commands.put((token,text,voice_id,output_id))
        return token

    def cancel(self):
        self.generation += 1

    def stop(self):
        self.cancel()
        self.stop_event.set()

    def run(self):
        import pythoncom
        from win32com.client import dynamic
        pythoncom.CoInitialize()
        try:
            voice = dynamic.Dispatch("SAPI.SpVoice")
            voice.Rate = 0
            while not self.stop_event.is_set():
                try:
                    token,text,voice_id,output_id = self.commands.get(timeout=.1)
                except queue.Empty:
                    continue
                if token!=self.generation:
                    continue
                try:
                    for selected, collection, property_name in (
                        (voice_id,voice.GetVoices(),"Voice"),
                        (output_id,voice.GetAudioOutputs(),"AudioOutput")):
                        if selected:
                            match = [collection.Item(i) for i in range(collection.Count) if collection.Item(i).Id==selected]
                            if not match:
                                raise RuntimeError("The selected voice or speaker output is unavailable. Check Settings.")
                            setattr(voice,property_name,match[0])
                    self.started_speech.emit(token)
                    voice.Speak(text,3)  # Asynchronous, purging earlier speech.
                    while not voice.WaitUntilDone(50):
                        if self.stop_event.is_set() or token!=self.generation:
                            voice.Speak("",3)
                            break
                except Exception as e:
                    self.failed.emit(f"Speech unavailable: {e}")
                finally:
                    self.ended_speech.emit(token)
        except Exception as e:
            self.failed.emit(f"Speech unavailable: {e}")
        finally:
            pythoncom.CoUninitialize()
