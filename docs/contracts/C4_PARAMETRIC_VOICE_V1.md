# C4 PARAMETRIC VOICE V1

Date: 2026-10-07
Status: actuator contract
Scope: C4 Nursery Android body

## Purpose

Give C4 a low-level vocal motor surface without bypassing learning through TTS.

This is not:
- text-to-speech;
- phoneme lookup;
- ASR;
- semantic voice generation.

It is a physical waveform actuator.

## Command

C4 may request:

ACTION_REQUEST
- action: VOCALIZE
- requestId
- sessionId
- voice:
  - f0Hz
  - amplitude
  - durationMs
  - formantsHz[3]
  - harmonics
  - breath
  - attackMs
  - releaseMs

Host clamps every parameter to bounded mobile-safe ranges.

## Synthesis

Android deterministically synthesizes:
- PCM16
- mono
- 24 kHz
- harmonic source
- formant-shaped spectrum
- bounded breath noise
- attack/release envelope

The exact generated PCM receives SHA-256 provenance.

PARAMETERS != PHONEME
WAVEFORM != WORD
VOCAL MOTOR COMMAND != LANGUAGE

## Execution semantics

The actuator is asynchronous.

Flow:
C4 ACTION_REQUEST(VOCALIZE)
-> host accepts request as pending
-> PCM generated
-> VOCAL_STARTED UI/body event
-> AudioTrack real playback
-> playback-head completion check
-> VOCAL_RECEIPT
-> ACTION_RECEIPT returned to runtime

PLAYBACK_STARTED != VERIFIED COMPLETION

executionSuccess=true means the Android AudioTrack playback head reached the generated waveform end within the bounded execution window.

## Self-audio feedback

After playback completion, the exact same generated PCM is passed through C4_SENSORY_FEATURES_V1 as:

- modality AUDIO
- source VOCAL_ACTUATOR_FEEDBACK
- origin SELF_AUDIO
- phase ACTUATOR_FEEDBACK
- independentEvidence false
- semanticLabels false
- actuatorRequestId
- waveformDigest

SELF_AUDIO != EXTERNAL OBSERVATION
SELF_AUDIO != INDEPENDENT EVIDENCE
SYNTHESIZED WAVEFORM != WORLD EVIDENCE

The ACTION_RECEIPT does not wait for runtime sensory processing. Playback completion and sensory feedback are separate facts.

## Replay

requestId is idempotent at the host actuator boundary.
A completed request is cached as a receipt and is not played twice.

## Avatar mouth

The VRM renderer may project vocal amplitude into a neutral mouth-open expression if the model exposes aa/a.
This is presentation of the actuator state only.

MOUTH MOTION != SEMANTIC SPEECH
