"""Unscored input troubleshooting with measured adjustments and incident records."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import time
import uuid

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from calibration import OPEN_STRINGS


def heard_text(frame):
    pitch = frame.get('raw_pitch')
    if frame.get('clipped'):
        return 'Input is clipping · turn down the guitar input gain.'
    if frame.get('overflow'):
        return 'Audio interrupted · waiting for a clean signal.'
    if not pitch or pitch.get('periodicity', 0) < .95:
        return 'Hearing: — · waiting for a clear note'
    cents = pitch['cents']
    tuning = 'in tune' if abs(cents) <= 5 else f'{abs(cents):.0f} cents {"flat" if cents < 0 else "sharp"}'
    quiet = ' · too quiet to register' if frame['db'] < frame['gate'] else ''
    return f'Hearing {pitch["note"]} · {pitch["hz"]:.1f} Hz · {tuning}{quiet}'


class LiveHearing:
    """Keep the last clear reading briefly through silence, labelled as previous."""
    def __init__(self):
        self.clear()

    def clear(self):
        self.last_text = ''
        self.last_at = float('-inf')

    def update(self, frame, now=None):
        now = time.monotonic() if now is None else now
        text = heard_text(frame)
        pitch = frame.get('raw_pitch')
        if frame.get('clipped') or frame.get('overflow'):
            return text
        if pitch and pitch.get('periodicity', 0) >= .95:
            self.last_text, self.last_at = text, now
        elif self.last_text and now - self.last_at < 2.5:
            return self.last_text.replace('Hearing ', 'Last heard ', 1)
        return text


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * fraction)]


def analyse(noise, played, expected, before):
    """Only adjust sensitivity/duration when a clear target was actually measured."""
    result = {'settings': dict(before), 'can_retest': False}
    all_frames = noise + played
    if any(f.get('clipped') for f in all_frames):
        return dict(result, reason='Input is clipping. Turn down the interface gain and run the check again.')
    if any(f.get('overflow') for f in all_frames):
        return dict(result, reason='Audio was interrupted. Check the input connection and close conflicting audio capture before retrying.')
    if not noise or not played:
        return dict(result, reason='No audio frames arrived. Check the selected input and channel in Connection.')
    floor = percentile([f['db'] for f in noise], .9)
    if any(f.get('raw_pitch', {}).get('periodicity', 0) >= .95 for f in noise if f.get('raw_pitch')):
        return dict(result, reason='A note was heard during the muted check. Mute every string and retry.')
    frequency = 440 * 2 ** ((expected - 69) / 12)
    matched, run, longest, span = [], 0.0, 0.0, []
    heard = []
    for frame in played:
        pitch = frame.get('raw_pitch')
        reliable = pitch and pitch.get('periodicity', 0) >= .95
        cents = 1200 * math.log2(pitch['hz'] / frequency) if reliable else None
        if reliable:
            heard.append(pitch['note'])
        if reliable and abs(cents) <= 80 and frame['db'] >= floor + 12:
            span.append(cents)
            if max(span) - min(span) > 50:
                run, span = 0.0, [cents]
            run += frame['duration']
            longest = max(longest, run)
            matched.append(frame['db'])
        else:
            run, span = 0.0, []
    result['evidence'] = {'noise_db': round(floor, 1), 'peak_db': round(max(f['db'] for f in played), 1),
                          'stable_target_seconds': round(longest, 3), 'heard_notes': sorted(set(heard))}
    if longest < .3:
        if max(f['db'] for f in played) < floor + 12:
            reason = 'The guitar is too close to the background level. Check the guitar volume, input gain and selected channel, then retry.'
        elif heard and not matched:
            reason = 'A different pitch was heard. Check the selected open string and tuning using the live readout, then retry.'
        else:
            reason = 'The note was not steady long enough. Mute the other strings, pick once, and let this string ring.'
        return dict(result, reason=reason)
    level = statistics.median(matched)
    proposed = dict(before)
    if level < before['gate'] + 3 or floor >= before['gate'] - 6:
        proposed['gate'] = math.ceil(max(-75, floor + 10, level - 6))
        if proposed['gate'] > -15:
            return dict(result, reason='The background/input level is too high for a safe sensitivity adjustment. Reduce input noise or gain and retry.')
    if longest < before['hold_seconds']:
        proposed['hold_seconds'] = .3
    changes = []
    if proposed['gate'] != before['gate']:
        changes.append('adjusting sensitivity to your measured guitar level')
    if proposed['hold_seconds'] != before['hold_seconds']:
        changes.append('using a shorter, still-stable note check')
    reason = ('Retesting after ' + ' and '.join(changes) + '.') if changes else 'The input looks clear. Checking two fresh notes with the current settings.'
    return dict(result, settings=proposed, can_retest=True, reason=reason)


class DetectionHelp(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.owner = window
        self.setWindowTitle('GuitarHacks · Detection help')
        self.setMinimumWidth(540)
        self.setMaximumWidth(620)
        self.phase = 'ready'
        self.before = {'gate': window.calibration.gate, 'hold_seconds': window.settings.get('hold_seconds', .5)}
        self.proposed = dict(self.before)
        self.persisted = False
        self.closed_incident = False
        self.noise, self.played = [], []
        self.seconds = 0.0
        self.verified = 0
        self.last_note = 0.0
        self.hearing = LiveHearing()
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.log_path = window.store.directory / 'diagnostics' / f'note-detection-{stamp}-{uuid.uuid4().hex[:8]}.jsonl'
        box = QVBoxLayout(self)
        title = QLabel('Help the app hear your guitar')
        title.setStyleSheet('font-size:22px; font-weight:600; color:#b6e4cc;')
        box.addWidget(title)
        self.issue = QComboBox()
        self.issue.addItems(['Note not detected', 'Wrong note detected', 'Audio cuts out'])
        box.addWidget(self.issue)
        self.string = QComboBox()
        for number, midi, name, _ in OPEN_STRINGS:
            self.string.addItem(f'{name} string · open', midi)
        self.string.setCurrentIndex(window.calibration.index)
        box.addWidget(self.string)
        self.instructions = QLabel('First mute all strings for two seconds. Then play the open string shown above. Nothing here is scored.')
        self.instructions.setWordWrap(True)
        box.addWidget(self.instructions)
        self.heard = QLabel('Hearing: —')
        self.heard.setStyleSheet('font-size:20px; color:#b6e4cc;')
        self.heard.setWordWrap(True)
        box.addWidget(self.heard)
        self.details = QLabel('')
        self.details.setWordWrap(True)
        box.addWidget(self.details)
        controls = QHBoxLayout()
        self.start = QPushButton('Start input check')
        self.start.setObjectName('primary')
        self.start.clicked.connect(self.begin)
        controls.addWidget(self.start)
        self.close_button = QPushButton('Continue setup')
        self.close_button.clicked.connect(self.accept)
        controls.addWidget(self.close_button)
        box.addLayout(controls)
        self.log_button = QPushButton('Open incident log')
        self.log_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_path))))
        box.addWidget(self.log_button)
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.timeout_check)
        self.finished.connect(self.finish)
        try:
            self.record('reported', issue=self.issue.currentText(), expected_midi=self.string.currentData(),
                        input=window.settings.get('input'), channel=window.settings.get('channel', 0), before=self.before,
                        recent_frames=list(window.recent_input))
        except OSError as error:
            self.start.setEnabled(False)
            self.details.setText(f'Cannot save an incident log: {error}. No automatic changes will be made.')

    def record(self, event, **data):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'utc': datetime.now(timezone.utc).isoformat(), 'event': event, **data}) + '\n')

    def restore(self):
        if not self.persisted and self.owner.capture:
            self.owner.capture.set_gate(self.before['gate'])
            self.owner.capture.set_hold_seconds(self.before['hold_seconds'])
            self.owner.capture.reset_detection()

    def begin(self):
        self.restore()
        try:
            self.record('check_started', issue=self.issue.currentText(), expected_midi=self.string.currentData())
        except OSError as error:
            self.details.setText(f'Cannot save incident log: {error}')
            return
        self.phase, self.seconds = 'noise', 0.0
        self.noise, self.played = [], []
        self.verified = 0
        self.start.setEnabled(False)
        self.issue.setEnabled(False); self.string.setEnabled(False)
        self.instructions.setText('Mute ALL strings now · measuring two seconds of background.')
        self.details.setText('')
        self.deadline = time.monotonic() + 5
        self.sample_after = time.monotonic()
        self.timer.start()

    def frame(self, frame):
        self.heard.setText(self.hearing.update(frame))
        if self.phase not in ('noise', 'play') or frame['monotonic'] < self.sample_after:
            return
        self.seconds += frame['duration']
        (self.noise if self.phase == 'noise' else self.played).append(frame)
        if self.phase == 'noise' and self.seconds >= 2:
            self.phase, self.seconds = 'play', 0.0
            self.instructions.setText(f'Play the {self.string.currentText()} now. Pick once and let it ring.')
            self.deadline = time.monotonic() + 9
        elif self.phase == 'play' and self.seconds >= 6:
            self.assess()

    def assess(self):
        plan = analyse(self.noise, self.played, self.string.currentData(), self.before)
        try:
            self.record('diagnosis', **plan)
        except OSError as error:
            self.attention(f'Cannot log the diagnosis: {error}')
            return
        self.details.setText(plan['reason'])
        if not plan['can_retest']:
            self.attention(plan['reason'])
            return
        self.proposed = plan['settings']
        self.owner.capture.set_gate(self.proposed['gate'])
        self.owner.capture.set_hold_seconds(self.proposed['hold_seconds'])
        self.owner.capture.reset_detection()
        self.phase = 'verify'
        self.last_note = self.sample_after = time.monotonic()
        self.instructions.setText('Retest 1 of 2 · Mute briefly, then pick this open string and let it ring.')
        self.deadline = time.monotonic() + 30

    def note(self, pitch):
        if self.phase != 'verify' or pitch.get('started', 0) < self.sample_after or pitch['monotonic'] <= self.last_note:
            return
        expected = 440 * 2 ** ((self.string.currentData() - 69) / 12)
        cents = 1200 * math.log2(pitch['hz'] / expected)
        if abs(cents) > 80 or pitch.get('periodicity', 0) < .95 or pitch.get('clipped'):
            return
        self.last_note = pitch['monotonic']
        self.verified += 1
        try:
            self.record('retest_note', number=self.verified, pitch=pitch)
        except OSError as error:
            self.attention(f'Cannot save retest results: {error}')
            return
        self.owner.capture.reset_detection()
        self.sample_after = time.monotonic()
        if self.verified < 2:
            self.instructions.setText('Retest 2 of 2 · Mute briefly, then pick the same string again.')
            return
        try:
            self.owner.store.set_settings(self.proposed)
            self.owner.settings.update(self.proposed)
            self.persisted = True
            self.owner.calibration.gate = self.proposed['gate']
            self.owner.calibration.minimum_gate = self.proposed['gate']
            self.owner.calibration.noise_floor = percentile([f['db'] for f in self.noise], .9)
            self.record('resolved', before=self.before, after=self.proposed, verified_notes=2,
                        fix='settings_adjusted' if self.proposed != self.before else 'fresh_muted_plucks_no_setting_change')
        except Exception as error:
            self.attention(f'Could not complete the settings/log save: {error}')
            return
        self.phase = 'resolved'
        self.timer.stop()
        self.instructions.setText('Both notes registered. Settings saved · continue setup when ready.')
        self.details.setText('Verified settings and measurements are saved in the incident log.')
        self.start.setText('Check complete')
        self.start.setEnabled(False)

    def attention(self, message):
        if self.persisted:
            self.phase = 'log_error'
            self.timer.stop()
            self.instructions.setText(message)
            self.details.setText('The verified settings were saved, but the incident log could not be completed.')
            self.start.setEnabled(False)
            return
        self.restore()
        self.phase = 'attention'
        self.timer.stop()
        self.instructions.setText(message)
        self.details.setText('Previous settings restored. Retry the check or continue setup.')
        self.start.setText('Retry input check'); self.start.setEnabled(True)
        self.issue.setEnabled(True); self.string.setEnabled(True)
        try:
            self.record('needs_attention', reason=message, restored=self.before)
        except OSError:
            self.details.setText('Incident log is unavailable. No unverified adjustment was saved.')

    def timeout_check(self):
        if time.monotonic() >= self.deadline:
            message = ('Retest did not receive two clean notes. Try again and mute between plucks.' if self.phase == 'verify'
                       else 'Not enough audio arrived. Check the input connection and channel, then retry.')
            self.attention(message)

    def finish(self, *_):
        if self.closed_incident:
            return
        self.closed_incident = True
        self.timer.stop()
        self.restore()
        try:
            self.record('closed', outcome=self.phase, settings_saved=self.persisted, after=self.proposed if self.persisted else self.before)
        except OSError:
            pass
