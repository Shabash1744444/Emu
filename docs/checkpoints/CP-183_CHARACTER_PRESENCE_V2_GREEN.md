# CP-183 — CHARACTER PRESENCE V2 GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 39cf8cf2124a92f1d0994c8d05dbdddcf48e1e1e

## Implemented
- irregular presentation-only blink timing;
- subtle gaze target drift while idle;
- breathing through chest/spine/shoulders;
- slow bounded weight transfer through hips;
- tiny head/neck micro-motion;
- smoother amplitude/f0-influenced vocal mouth envelope;
- VRM spring-bone update remains active through normal vrm.update();
- real motor actions continue to override idle presentation.

## Boundaries
IDLE MICRO-MOTION != C4 ACTION
GAZE DRIFT != ATTENTION
BLINK != EMOTION
POSTURE != INTERNAL STATE
MOUTH MOTION != LANGUAGE
SPRING PHYSICS != INTENTION

## Build
GitHub Actions run #440: SUCCESS
Run ID: 37648959398

Artifact:
- C4-Nursery-0.63-character-presence
- artifact ID: 11495951500
- ZIP bytes: 48,171,496
- ZIP SHA256: 488282a760ff2efcd0b14a9b46584d57cc7ace85c46bb1d3a10435735d5fc12f

APK:
- bytes: 48,171,063
- SHA256: 39402765d58e82fe1ddbb50d96317878640c0eefb2bae80f477e97a8f8817950
- unzip integrity PASS

VRM bundle SHA256:
03738cb1a71eb4c7706e005c76e7d4a980af01e8f33b3a6fadb993d446f0ff1b

Physical gate:
- inspect blink expression names on default/imported VRM;
- verify gaze drift does not look mechanical;
- verify shoulder/hip axes across different VRM rigs;
- verify mouth cadence with real VOCALIZE requests;
- verify spring-bone cost under ECO mode.
