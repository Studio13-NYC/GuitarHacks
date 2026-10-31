# Guitar practice record

Started: 2026-10-13 (America/New_York)

## Confirmed by Nick

- Beginning triads and seventh chords; wants note names, intervals, practical fingering, and movable shapes.
- Start with C major, C minor, and C diminished on the thick low E, A, D strings.
- Standard tuning: E2 A2 D3 G3 B3 E4.
- Guitar is connected to the computer through TASCAM Model 12 channel 5.
- Wants called-note/chord exercises, audio feedback where validated, and more practice on specific difficulties.
- Requested a small Windows app, preferably an executable, with spoken and on-screen prompts. The standalone app is now the intended interface; chat-controlled CLI monitoring was the initial calibration step.

## Audio status

- On 2026-10-13, read-only Windows PnP enumeration showed `M12 In 5/6 - Guitar-DI (USBAudio2-ACX)` with status OK.
- Channel 5 is the first channel of this stereo pair, subject to actual capture validation.
- On 2026-10-13 at 17:03 America/New_York, a shared-mode WASAPI capture successfully opened this stereo endpoint at 48 kHz and selected its first channel. Channel 5 carried strong signal; channel 6 was near the noise floor.
- The initial live calibration produced repeated C3 estimates near 130 Hz, consistent with the requested C at A-string fret 3. Finger, string, and fret choice cannot be proven from pitch. These are calibration observations, not mastery or recall scores.
- The capture reports pitch events to the assistant through a running local command. It is not an always-on service, and monitoring ends when the bounded session closes.
- Do not equate endpoint presence with working audio. Do not change system routing or drivers to begin a lesson.
- Initial five-second level check: `sessions/20261013T210310068532Z.jsonl`. First live pitch session: `sessions/20261013T210338541548Z.jsonl` (180-second window).
- That live session closed normally at 17:06:38 America/New_York after 180.3 seconds with no input overflows. Its 60 pitch events are detector observations, not 60 attempts or independently verified notes. Monitoring is off after this session.
- A 78-case synthetic signal check passed for low guitar notes, detuning, and stronger second harmonics; silence and random noise were rejected. This does not validate live chord recognition or eliminate harmonic errors.
- Quiet periodic readings near 180 Hz and some transient other-pitch estimates occurred during live calibration. They are not evidence of player mistakes. The next session's default gate is -45 dBFS (initial session used -55); `--gate-db` remains adjustable.

## First shape family

All fret lists below run from low E (string 6) toward G (string 3).
Triads are in second inversion: fifth in the bass, root on A string.
Suggested fingers in that string order: middle, ring, index; add pinky on G for sevenths. These suggestions are untested for Nick's hand.

| Chord | Frets | Notes, low to high | Intervals, low to high |
| --- | --- | --- | --- |
| C/G | 3 3 2 | G C E | 5 1 3 |
| Cm/G | 3 3 1 | G C Eb | 5 1 b3 |
| Cdim/Gb | 2 3 1 | Gb C Eb | b5 1 b3 |
| Cmaj7/G | 3 3 2 4 | G C E B | 5 1 3 7 |
| C7/G | 3 3 2 3 | G C E Bb | 5 1 3 b7 |
| Cm7/G | 3 3 1 3 | G C Eb Bb | 5 1 b3 b7 |
| Cm7b5/Gb | 2 3 1 3 | Gb C Eb Bb | b5 1 b3 b7 |
| Cdim7/Gb | 2 3 1 2 | Gb C Eb Bbb | b5 1 b3 bb7 |
| Cm(maj7)/G | 3 3 1 4 | G C Eb B | 5 1 b3 7 |

The diminished seventh Bbb sounds like A in equal temperament; preserve the Bbb spelling to explain the interval.
Sevenths require a fourth distinct note; add the G string for complete grips. Three-string shells can be learned later.
The C-to-D move is two frets upward on every fretted note. Shapes stay the same on this string set; note names change.

## Teaching sequence

1. Locate C: A string fret 3, ring finger. Say "C, root, one."
2. Add E: D string fret 2, index finger. Say "E, major third, three."
3. Add G: low E string fret 3, middle finger. Say "G, fifth, five."
4. Pick each string separately, then together. Check comfort, clear notes, and muting before speed.
5. Lower E to Eb for minor; then G to Gb for diminished. Identify the one changing note each time.
6. Use short prompts in both directions: interval to note, note to interval, chord to fingering. Start with visible answers, then recall.
7. Revisit observed mistakes after intervening prompts and at the next session; keep note recall, interval recall, grip comfort, and audio uncertainty separate.
8. Move the same shape to D and identify its new notes before adding more positions or seventh chords.

## Observed performance

No scored recall attempts yet. No weaknesses or mastered skills inferred.

| Date | Prompt / target | Response or observation | Evidence | Next review |
| --- | --- | --- | --- | --- |
| 2026-10-13 | Audio calibration: C on A string fret 3 | Repeated C3 estimates around 130 Hz on channel 5; finger placement unverified | `sessions/20261013T210338541548Z.jsonl` | Recall C later without the fingering hint; do not treat calibration as mastery |
| 2026-10-13 | Exploring channel 5 with different notes | C3, E3, F3, G3 and low E2 were among the detected pitches. Nick explicitly confirmed he was deliberately trying different notes. No wrong answers or E/F confusion assigned. | Same live session log plus Nick's confirmation in chat | Begin a clearly cued, single-note exercise when Nick is ready |

Next structured exercise: one clearly cued target followed by a pause; start with C3 (A string fret 3, ring finger, root/1), then E3 (D string fret 2, index finger, major third/3). The live session above was exploration, not a scored attempt at this sequence.
