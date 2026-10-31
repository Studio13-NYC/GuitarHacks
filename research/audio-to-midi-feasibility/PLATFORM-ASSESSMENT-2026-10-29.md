# Audio to MIDI platform and model assessment

Assessed 2026-10-29 for DuffMan and MIDIfier. Research only: no new models or dependencies installed, no account actions, no audio uploads, no application changes.

## Decision

Use **Hugging Face Hub for model discovery and versioned downloads, the authors' GitHub repositories for reference code, and DuffMan for primary evaluation**. This is the best fit for the existing local application and the preference for little or no recurring cost. It is not a claim that every candidate fits DuffMan or transcribes well.

Use Kaggle as the first hosted notebook fallback when a promising model needs more VRAM or a Linux environment. Use Colab when an author already maintains a suitable notebook. Do not build MIDIfier around a free hosted demo or a free notebook runtime.

Four research agents contributed: Terra 6.1 High for general-model capability, Terra 6.1 High for specialist transcription, Sol 6.1 Medium for platform alternatives, and Luna Medium for Hugging Face terms. Higher-effort agents handled model and benchmark judgments; the lighter agent checked bounded platform facts. Actual agent charges were not measured. Findings were synthesized against current documentation and local files.

## Why Hugging Face is the right hub

The Hub provides searchable model repositories, model cards, license metadata and downloadable weights. Its Python client supports local caching and selecting an exact repository revision. That suits a local app: download a reviewed version once, retain its identity, and run inference without sending recordings to a service. [Hub search](https://huggingface.co/docs/huggingface_hub/guides/search), [downloads and revisions](https://huggingface.co/docs/huggingface_hub/guides/download).

A model card is not a quality certification. It may contain the author's own results, and a repository can require custom code rather than a standard Transformers pipeline. Review the actual code, model terms and checkpoint before execution. Do not automatically execute arbitrary repository code or update a working model to whatever is newest. Check upstream deliberately, evaluate the candidate, then pin the accepted version. [Model cards](https://huggingface.co/docs/huggingface_hub/guides/model-cards).

### Free access is not unlimited free inference

| Service | Current terms and useful role |
| --- | --- |
| Hugging Face model discovery/downloads | Primary catalog and source of weights, subject to each repository's access and license requirements. |
| Existing ZeroGPU Spaces | Free-account quota currently 5 GPU minutes daily, with shared queues. Useful for short demonstrations, not repeated full-song evaluation. |
| Hosting our own ZeroGPU Space | Eligible free personal accounts can host two; verified email, good standing and account age over 30 days required. Gradio-only compatibility needs checking. |
| Ordinary Gradio/Docker Spaces | Current creation rules require a paid plan, except the eligible ZeroGPU route. CPU Basic has no hourly charge, but that does not remove the plan requirement. |
| Inference Providers API | Current free accounts receive no monthly inference credits. Availability is provider/model-specific, not automatic for every model on the Hub. |

Sources: [ZeroGPU quotas and eligibility](https://huggingface.co/docs/hub/en/spaces-zerogpu), [Spaces creation and hardware](https://huggingface.co/docs/hub/en/spaces-overview), [Inference Providers billing](https://huggingface.co/docs/inference-providers/pricing). These terms can change; check again before deployment or spending.

ADT_STR illustrates the distinction: its weights and local-loading instructions are on Hugging Face, but its card currently says it is not deployed by an Inference Provider. [ADT_STR model card](https://huggingface.co/Pierfrancesco/adt-str).

Public, protected and private Spaces have different source/app visibility. None alone establishes an app's audio-retention behavior. Keep recordings local during the first evaluation; review code, access and retention before any later upload. [Space visibility](https://huggingface.co/docs/hub/en/spaces-overview).

## Ranked execution choices

| Rank | Place | Why use it | Main constraint |
| --- | --- | --- | --- |
| 1 | DuffMan with Hub downloads | Existing local audio files, repeatable runs, no hosted inference bill or upload. | RTX 3080 has 10 GB VRAM; each model/runtime must prove fit. |
| 2 | Kaggle Models and Notebooks | Integrated notebooks, attached models and versioned local downloads. Best hosted alternative for controlled experiments. | Shared compute and account quotas; not a guaranteed accelerator or production service. |
| 3 | Google Colab | Convenient when a candidate supplies an official notebook. | Dynamic GPU availability, temporary runtimes and interactive-use restrictions. |
| 4 | ModelScope notebooks | Consider if a specific candidate has a better-maintained release there. | Current account eligibility, useful checkpoint coverage and Windows migration remain unresolved. |

Kaggle's GPU guidance currently describes a weekly quota of 30 hours, sometimes higher depending on demand/resources; it is not a reservation. Its official client supports versioned resource downloads. [Kaggle GPU guidance](https://www.kaggle.com/docs/efficient-gpu-usage), [Models](https://www.kaggle.com/docs/models), [kagglehub](https://github.com/Kaggle/kagglehub).

Colab's free resources are not guaranteed; sessions can run at most 12 hours depending on availability and usage. Free notebooks must not be turned into a persistent app backend or used to bypass the notebook interface. [Colab FAQ](https://research.google.com/colaboratory/faq.html).

No cloud account eligibility, remaining quota, billing status or private-storage configuration was inspected. Paid APIs are not necessary to start this evaluation.

## What DuffMan already runs

Live inspection identifies DUFFMAN and an NVIDIA RTX 3080 with 10,240 MiB VRAM. `uv` is available. The current model is `NeuralNote/models/muscriptor-large-f16.gguf`, 2,739,142,176 bytes. Recent processing logs report `DEVICE Vulkan / NVIDIA GeForce RTX 3080`.

The current host uses `NeuralNote/source/ThirdParty/muscriptor.cpp`, not the official Python/CUDA implementation. Its wrapper leaves `TranscribeOptions.instruments` empty, which selects the unconditional/all-instruments path. It does not expose classifier-free guidance. The local port documentation describes greedy decoding; the official Large headline benchmark uses CFG 2. These paths have not been compared on the failed recording.

Recent Mr. Jones results contain drums in the bass and lead-guitar event files as well as the drum event file. The exporter preserves those predicted groups. This is concrete evidence of unwanted instrument assignments in the current pipeline, not proof that all missing hits or wrong pitches have the same cause. Instrument restriction may prevent unwanted categories; it cannot guarantee recovery of missed notes.

Local evidence:

- `NeuralNote/cli/main.cpp`
- `NeuralNote/export_midi.py`
- `NeuralNote/source/ThirdParty/muscriptor.cpp/cpp/include/muscriptor/transcriber.hpp`
- `NeuralNote/source/ThirdParty/muscriptor.cpp/docs/MODEL.md`
- `StemSlicer/processing/20261029-112346-midi-452ea8/` (bass)
- `StemSlicer/processing/20261029-112430-midi-d1eed9/` (drums)
- `StemSlicer/processing/20261029-112508-midi-5ba46d/` (lead)

The GuitarHacks parent directory is not a Git repository; its NeuralNote source is a separate nested checkout. Preserve the existing feasibility assessment and working application. Future evaluation should use separate project-local `uv` environments and output folders, not modify the production environment.

## Model shortlist

These are candidates to test, not a ranking of proven quality on Nick's music.

| Candidate | Role | Why it belongs | Caveat |
| --- | --- | --- | --- |
| MuScriptor Large, official implementation | General multi-instrument reference baseline | Establish whether the model's reference inference outperforms our current integration before replacing the family. | Python/CUDA memory fit, gating and parity with the current Vulkan output need testing. |
| ADT_STR, initially tau-0.8 | Specialist drum candidate | Author-published weights and local inference interface; richer percussion vocabulary and velocity output. | Windows/GPU operation and actual hit accuracy untested here. |
| ADTOF / ADTOF PyTorch port | Contrasting drum baseline | Established pretrained drum transcription and notebook/CLI routes. | Five broad classes are less detailed than a full kit; port behavior and permissions need review. |
| YourMT3+ | Contrasting general-model baseline | Public checkpoints and reference work provide a genuinely different model family. | Not established as an upgrade over MuScriptor; code/checkpoint licenses differ. |
| Spotify Basic Pitch | Isolated polyphonic guitar/bass baseline | Lightweight audio-to-MIDI with pitch-bend support; useful as a control rather than assuming bigger is always better. | Not a drum or full-mix specialist; no quality claim on these stems. |

The MuScriptor authors report Large at 47.8 multi-instrument F1 and 49.6 drum F1 versus YourMT3+ at 21.9 and 41.4 on their held-out set. These are author-run results at CFG 2, not a guarantee on this recording or a percentage of notes that will be correct. They do not establish the best specialist model. The review found no sufficiently supported, readily deployable general replacement that can simply be declared a superior upgrade. [MuScriptor model card](https://huggingface.co/MuScriptor/muscriptor-large), [official implementation](https://github.com/muscriptor/muscriptor).

ADT_STR consolidates percussion into 26 classes and offers three checkpoints. Its authors favor tau-0.8 overall on their ENST/MDB evaluation. A separate developer reports difficulty reproducing parts of that performance, so evaluate it alongside ADTOF rather than accepting the headline. [ADT_STR code and evaluation](https://github.com/pier-maker92/ADT_STR), [weights](https://huggingface.co/Pierfrancesco/adt-str), [contrasting developer evaluation](https://github.com/miraer/drum2midi).

ADTOF's author repository links the PyTorch port and a Colab/local notebook; the original documented test environment is macOS/Python 3.10, not proof of Windows support. [ADTOF](https://github.com/MZehren/ADTOF), [PyTorch port](https://github.com/xavriley/ADTOF-pytorch).

YourMT3+ remains a comparison candidate, not the selected replacement. [Code](https://github.com/mimbres/YourMT3), [checkpoints](https://huggingface.co/mimbres/YourMT3). Basic Pitch is a separate single-instrument polyphonic baseline, not a solution for drums. [Basic Pitch](https://github.com/spotify/basic-pitch).

### Licensing gate

Free download, local execution and permission to distribute or use commercially are separate questions. MuScriptor's code is MIT but its weights are CC BY-NC; ADTOF's author repository is CC BY-NC-SA; ADT_STR states CC BY-SA; Basic Pitch is Apache-2.0. YourMT3 code is GPL-3.0 while the checkpoint card declares Apache-2.0. Review the exact assets and dependencies before integration/distribution; do not infer all permissions from one repository badge. Terms are linked in the respective sources above. No license terms were accepted during this research.

## Proposed evaluation before any integration

Use 4-6 short excerpts, including the passage Nick rejected, a busy drum fill, exposed cymbals, a bass riff, a clear guitar melody and overlapping guitar notes/chords. Preserve both the original mix and existing stems. Include a known-MIDI reference rendered to audio when available, without treating synthetic success as proof on real recordings.

1. Keep the current output as the failure baseline. Record source/model hashes, revision, device, decoding options, resampling and run time for every candidate.
2. Compare current MuScriptor with its official reference path, including instrument-conditioned runs on known stems. Do not silently change tempo or quantize the first comparison.
3. Compare ADT_STR and ADTOF on the same drum excerpts. Count missing/extra hits per class, timing errors and dropouts through fills; state the matching tolerance, initially 50 ms.
4. Compare isolated guitar/bass with the general reference and Basic Pitch. Check pitches, octave errors, repeated notes, overlaps and starts/ends. Do not reduce chord transcription to a monophonic melody test.
5. Inspect raw note events, exported MIDI and playback in Reason or Guitar Pro separately. Multiple percussion tracks are not intrinsically wrong; unintended duplicate hits or percussion from melodic stems are the failure. Check track/channel assignments and chunk boundaries rather than merely counting tracks.
6. Listen to source and MIDI through consistent sounds and levels. Record correction time as well as numerical scores. A valid file, completed inference or large note count is not musical acceptance.

The acceptance decision is a recognizable, useful transcription with tolerable cleanup on Nick's material. A candidate must materially improve the rejected output before it enters MIDIfier. If none passes, retain audio stems for practice and label MIDI conversion experimental instead of disguising errors with quantization or filtering.

## Next decision

Adopt the Hub-plus-local workflow as the research base. The first bounded experiment should compare the existing drum result with ADT_STR and ADTOF, while establishing the official MuScriptor reference on the same short excerpt. Do not buy a subscription, change audio drivers, add Remote mappings or rebuild the application for this platform decision.
