# CP-182 — ADAPTIVE QUALITY V1 GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 9725a8195442cd4249b3101c9e13e8d001244e08

## Implemented
- AUTO / HIGH / BALANCED / ECO renderer profiles;
- Android thermal and power-save telemetry;
- AUTO defaults to BALANCED and drops to ECO for power-save / SEVERE thermal;
- CRITICAL+ thermal forces ECO regardless of requested profile;
- renderer-only pixel ratio / target FPS / shadow cost control;
- ECO disables dynamic shadows and presentation-only camera drift;
- UI exposes requested/effective mode and thermal state.

## Boundaries
GRAPHICS QUALITY != COGNITION QUALITY
THERMAL DOWNSHIFT != RUNTIME DOWNSHIFT

No runtime ticks, chat, sensory services, source transport, motor receipts or C4 state are throttled.

## Build
GitHub Actions run #433: SUCCESS
Run ID: 37648366151

Artifact:
- C4-Nursery-0.62-adaptive-quality
- artifact ID: 11496080545
- ZIP bytes: 48,170,346
- ZIP SHA256: 0b037b7e56186894b9754e8fe763928d4cea529f5cf64bf4cac6b3c8083f8729

APK:
- bytes: 48,169,919
- SHA256: a5cd25ee9cd5a44e5c1fb9da43c15e953a2c0ebbae9573cf4f263bace174f240
- unzip integrity PASS

VRM bundle SHA256:
b4216533d58a24ed1bff9919b6229b15b7bbd0d4821ad10fcc20c9437f511121

Physical gate:
- verify thermal status on target phone;
- verify HIGH/BALANCED/ECO visual difference;
- verify AUTO downshift under power-save;
- inspect GPU/thermal behavior during long 3D sessions.
