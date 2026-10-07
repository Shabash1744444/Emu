# CP-176 — PARAMETRIC MOTOR VOICE GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 802bb36683d6d4fa9d41796a6a868b072496a756

## Goal

Give C4 a low-level vocal motor surface without using TTS.

## Implemented

### Android actuator
- new VocalActuator.java;
- deterministic PCM16 mono synthesis at 24 kHz;
- bounded physical parameters:
  - f0Hz
  - amplitude
  - durationMs
  - formantsHz
  - harmonics
  - breath
  - attackMs
  - releaseMs
- exact generated waveform SHA-256;
- AudioTrack MODE_STATIC playback;
- playback-head completion check before executionSuccess=true.

### Async action semantics
VOCALIZE is asynchronous.

Flow:
ACTION_REQUEST(VOCALIZE)
-> pending actuator ACK
-> VOCAL_STARTED
-> real Android playback
-> playback completion verified
-> VOCAL_RECEIPT
-> ACTION_RECEIPT returned to runtime

PLAYBACK_STARTED != VERIFIED COMPLETION.

### Self-audio
After the action receipt, the exact generated PCM is routed through the physical audio feature extractor as:
- source VOCAL_ACTUATOR_FEEDBACK
- origin SELF_AUDIO
- phase ACTUATOR_FEEDBACK
- independentEvidence false
- semanticLabels false
- same waveformDigest and requestId

The action receipt does not wait for runtime sensory processing.

SELF_AUDIO != EXTERNAL OBSERVATION
SELF_AUDIO != INDEPENDENT EVIDENCE
SYNTHESIZED WAVEFORM != WORLD EVIDENCE

### Replay
Completed requestId values are cached and not played twice.

### VRM mouth
The VRM renderer may project actuator amplitude into an aa/a mouth-open expression for the requested duration.

MOUTH MOTION != SEMANTIC SPEECH.

### UI
- Home capability chip: VOICE
- speaking / ready / error state
- self-audio accepted/local state
- no user-facing puppet/speak button

## No shortcut

CI explicitly rejects:
- Android TextToSpeech
- browser speechSynthesis

## Build

GitHub Actions run #385: SUCCESS

Artifact:
- name: C4-Nursery-0.56-parametric-voice
- artifact ID: 11485063780
- ZIP bytes: 48,149,170
- ZIP SHA256: 8c0f5b0202136038d871a744209031c16de8690548017a373168547a5fb91cab

APK:
- bytes: 48,148,743
- SHA256: 1c77cb868cdf5a7468d9f8d28e8e18cc9a002438638640de144ae06a2642c823
- unzip integrity: PASS

VRM bundle:
- SHA256: 0d7cb4c162481b1412c1bd61ffd97231e06f4ee291a17c9923f1b1b2750a1dfc

## Physical Android gate

Still required:
- verify phone speaker playback;
- verify playback-head completion semantics on device;
- inspect volume safety and audible timbre;
- verify VRM mouth expression mapping;
- verify SELF_AUDIO runtime acceptance with the installed C4 runtime.
