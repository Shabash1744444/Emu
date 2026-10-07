# CP-179 — WORLD HUB V2 GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 9fe3c6093248b4e213cf9586964e3d068d575645

## Implemented
- World page rebuilt as a three-mode hub: Overview / Physics / Memory;
- overview projects verified native room state only;
- C4 body x, held object, body action count and room objects are shown;
- passive room map for BALL / BLOCK / BOOK / PLANT / LAMP;
- current native room task is surfaced;
- existing causal mechanics preserved under Physics;
- existing sequence-memory verifier preserved under Memory;
- no user-facing avatar/object puppeteering controls were added.

## Boundaries
WORLD MAP != NEW OBSERVATION
MAP POSITION != NATIVE WORLD AUTHORITY
INSPECT != ACT
SIMULATION != EXTERNAL OBSERVATION
SANDBOX_RECEIPT != REAL_WORLD_RECEIPT

## Build
GitHub Actions run #410: SUCCESS

Artifact:
- C4-Nursery-0.59-world-hub
- artifact ID: 11492162789
- ZIP bytes: 48,161,801
- ZIP SHA256: 7b1a8c00341e4c13d83cee1e5b364bc2618408b1c0ffec7adab01f372329c1e4

APK:
- bytes: 48,161,395
- SHA256: 4ba571144b748b9b1afc7c192583503e9383cb5713f3ac07e1cfaca558aef215
- unzip integrity PASS

Physical gate:
- verify World Hub map readability on the user's phone;
- verify task text for L1/L2 live runtime tasks;
- verify Physics/Memory panel density and touch targets.
