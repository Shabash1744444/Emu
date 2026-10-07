# CP-176 — PRE PARAMETRIC MOTOR VOICE

Date: 2026-10-07
Parent: CP-175 Embodied Motion V2 GREEN
Status: PRE

Goal:
Give C4 a low-level vocal actuator instead of a text-to-speech shortcut.

Target flow:
C4 ACTION_REQUEST(action=VOCALIZE, voice parameters)
-> Android validates bounded motor parameters
-> deterministic PCM16 synthesis
-> real AudioTrack playback
-> physical SELF_AUDIO feature feedback
-> playback-complete ACTION_RECEIPT
-> optional VRM mouth actuator projection

Voice parameters are physical controls, not phoneme/word labels:
- f0Hz
- amplitude
- durationMs
- formantsHz
- harmonics
- breath
- attackMs
- releaseMs

Hard boundaries:
VOCAL MOTOR COMMAND != LANGUAGE
SELF_AUDIO != EXTERNAL OBSERVATION
SYNTHESIZED WAVEFORM != EVIDENCE ABOUT THE WORLD
MOUTH MOTION != SEMANTIC SPEECH
PLAYBACK_STARTED != VERIFIED COMPLETION

No TTS.
No text -> speech shortcut.
No ASR feedback shortcut.

Target release:
0.56-parametric-voice
