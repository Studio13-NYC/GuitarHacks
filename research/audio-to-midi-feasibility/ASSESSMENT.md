# Polyphonic guitar-to-MIDI feasibility

Investigation started 2026-10-28. Required: polyphonic chords and overlapping notes. A monophonic prototype does not satisfy the request.

## Preliminary decision

Recording/importing an isolated guitar performance and converting it locally to MIDI is feasible using existing polyphonic models. A standalone app and VST3 can share the transcription engine. Live low-latency polyphonic guitar-to-synth is a separate research risk; offline conversion speed does not establish playable latency.

Reason 14 explicitly does not support VST MIDI output. Proposed live route: guitar audio track -> our audio-effect VST3 -> bounded queue/worker -> dedicated Windows MIDI Services loopback -> Reason external MIDI input -> armed synth instrument track. This is a design proposal, not a tested path. Reason can own the audio interface while the plugin consumes host audio, avoiding a second standalone ASIO client. Host MIDI output can additionally be implemented for other DAWs that support it.

For recorded files, plugin/utility exports MIDI for import into Reason or Guitar Pro. That path does not depend on Reason accepting VST MIDI output. Track start offset, tempo map and note timing must be retained explicitly. Live loopback timing, Reason monitoring, controller assignment, transport stop, stuck-note release, offline bounce and feedback prevention need actual host tests.

## Binary evidence so far

Selected file: C:\Program Files\Jam Origin\MIDI Guitar 3\MIDI Guitar 3.exe
SHA256: 462eae5a765db0bdff638fb0d310033d09fc394e847961028f746437eaa14fb4
Size: 31,291,904 bytes. REA identifies x64 PE32+, 11 sections, no CLI/.NET metadata.
REA Evidence: ev_ef5bf1f5185d9905adab6fddf21aa86e2e78883ae4eaf642712afdb91ac82e0b. Full record in rea-evidence.json.

Ordinary Python static byte inspection (not REA decompilation) is saved in binary-static.json with file offsets. RTTI-like strings include OffbeatEngine, BaseTrackerModule, FinalTrackerModule, FinalTracker3Module, HighwayTrackerModule; JUCE identifiers and polyphonic tracking descriptions also occur. These support an inference of native C++/JUCE infrastructure with distinct tracker components. They do not reveal the pitch estimator, its training data, processing latency, or quality. Boost/asio network strings must not be confused with Steinberg ASIO audio evidence.

Initial native REA analysis was blocked by unconfigured Ghidra and Java 8 runtime. User subsequently authorized Ghidra/JDK installation. No licensing routines were modified and the target was not executed by this analysis.

## Candidate engines

- Spotify Basic Pitch: documented polyphonic audio-file-to-MIDI baseline, best with one instrument at a time. One guitar playing chords is polyphonic even though it is a single instrument. Benchmark on clean DI guitar first.
- NeuralNote v1.1.0: existing standalone/VST3 implementation of Basic Pitch demonstrates the requested record-or-import workflow. Its own README explicitly rules out live transcription with this pipeline: long CQT windows, model lookahead and noncausal note decoding. Faster-than-real-time throughput does not remove this dependency on future audio.
- NeuralNote v2: now uses MuScriptor, is local and supports multiple instruments. Evaluate as a separate offline baseline rather than assuming v1 behavior or licensing. Official site states Apache-2.0 app code and CC BY-NC 4.0 model weights; model permissions differ from app permissions.
- Independent live engine: needs causal multi-pitch estimation plus onset/offset separation, harmonic rejection, overlapping-note state, repeated strums and optional per-note bends. Proposed shared native C++ core and standalone/VST3 wrappers; the live estimator may differ from the offline model. Packaging is ordinary engineering; reliable polyphonic tracking is the difficult part.

## Acceptance before committing to a live product

Use annotated dry guitar recordings covering dyads, triads, sevenths, open/barre chords, strums, arpeggios with overlap, quiet inner voices, palm muting, low notes, repeated notes and bends. Measure false/missed notes per chord, onsets/offsets, repeated-note splitting, worst-case processing cost and onset-to-MIDI latency on this machine. Test both actual performances and controlled signals; synthetic chords alone cannot establish tracking quality. A chord label is not enough: export each independently timed note. MIDI pitch alone cannot establish physical string/fret or distinguish two strings playing an identical pitch reliably. Per-note bends require a compatible destination; basic polyphony does not require MPE.

Recommended sequence for the revised scope: benchmark polyphonic offline quality, select an engine, build a shared utility/VST3 prototype, and verify audio capture plus MIDI-file import in Reason. Live tracking and synth routing are deferred. Do not promise Jam-equivalent live performance from a short binary inspection.

## Question coverage

- Standalone record/import -> polyphonic MIDI: feasible in principle; quality on Nick's guitar unmeasured.
- VST capture then MIDI-file export: feasible in principle; proposed implementation not built.
- VST MIDI directly into Reason tracks: unsupported by Reason's documented host interface.
- Windows MIDI loopback into Reason: plausible design; existing GuitarHacks transport tests do not prove this complete host path.
- Jam tracking algorithm reconstruction: unresolved; requires focused native analysis, and may remain substantial research even after decompilation.

## Primary references

https://docs.reasonstudios.com/reason14/working-with-vst-plugins
https://docs.reasonstudios.com/reason14/recording-in-the-sequencer
https://github.com/spotify/basic-pitch
https://raw.githubusercontent.com/DamRsn/NeuralNote/v1.1.0/README.md
https://github.com/DamRsn/NeuralNote
https://neuralnote.co/
https://www.jamorigin.com/technology/

## Native tooling update

Ghidra 12.1.4 and full Temurin JDK 21.0.12.1+1 installed under `tools/reverse-engineering`, with official SHA256 checks verified. REA CLI now reports Ghidra available and has imported the selected binary. REA MCP environment is configured for the next reconnect; existing server retains its previous environment. No global Java/PATH changes. Setup/rollback details: `../../tools/reverse-engineering/README.md`.

Ghidra's first pass did not locate a matching Jam PDB in configured locations. Initial analysis emits some embedded-image and unresolved-constructor warnings, so successful startup is not proof of complete reconstruction. The full pass subsequently timed out; no completed native overview or snapshot was produced. Feasibility conclusions above do not depend on recovering proprietary source.

## Revised scope and completed installation status

User explicitly deferred piping MIDI into a Reason synth. First version therefore requires polyphonic record/import -> transcription -> MIDI export, in standalone and VST3 forms. A Reason audio-effect plugin can capture host audio and transcribe after Stop; the user imports the resulting MIDI onto an instrument track. This is not direct live MIDI recording via the VST host interface. If direct live sequencer recording is later required, the documented Reason MIDI-output limitation still needs the external-port route.

This narrower scope does not require a low-latency causal tracker. It is a substantially more practical engineering project using an existing local polyphonic model. No monophonic fallback is proposed. Prototype success must be judged on complete chords and overlapping notes from real dry guitar takes, not single-note demos. Start with Basic Pitch/NeuralNote v1 as a small baseline and compare NeuralNote v2/MuScriptor for offline quality before choosing a model. Neither has been benchmarked on this guitar in this investigation.

Ghidra/JDK installation and REA provider detection are verified. The first full native indexing pass imported Jam and ran analysis but terminated with provider_timeout at 330000 ms in list_documents. No completed native overview or snapshot was produced. REA cleaned up its owned temporary process/project. native-overview.json contains the timeout error (not an overview). The earlier REA classification and raw-byte findings remain valid; no tracker algorithm has been decompiled or reconstructed. No additional toolchain installation is needed to retry with a supported longer analysis budget or a more focused analysis workflow.

Overall assessment: high feasibility for the revised record/import and offline polyphonic transcription workflow, with transcription quality as the main acceptance risk. Standalone/VST3 packaging and MIDI-file export are established patterns demonstrated by the cited open-source projects. Matching Jam's real-time tracker is outside this first version and has not been established by this analysis.


