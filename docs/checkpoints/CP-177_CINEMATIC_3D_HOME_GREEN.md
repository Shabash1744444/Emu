# CP-177 — CINEMATIC 3D HOME GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: bb3170a85f50532542536ff91c227ab8a8361c52

## Implemented
- real Three.js habitat around the VRM body;
- floor, walls, window, skyline, bed, desk, monitor, shelves, books, rug and holographic orb;
- PBR-ish materials, fog, soft light, contact shadows;
- native verified BALL / BLOCK / BOOK state projected into the 3D scene;
- updateWorld() keeps renderer props synchronized after native ACTION_RECEIPT;
- VRM load sync restores verified room objects + held object + body x;
- subtle presentation-only camera/orb/monitor motion;
- BODY_MANIFEST_V1 generated from actual Android hardware availability;
- body manifest offered to the runtime on OPEN_SESSION without making launch depend on support;
- WORLD_EVENT / WORLD_TASK routing bug in Python adapter corrected;
- premium Home cards + real organ map + System manifest diagnostics.

## Boundaries
3D ROOM != WORLD EVIDENCE
RENDERER PROP != NATIVE WORLD STATE
CAMERA PRESENTATION != C4 ATTENTION
BODY_MANIFEST != OBSERVATION
AVAILABLE != RUNTIME_SUPPORTED

## Build
GitHub Actions run #397: SUCCESS

Artifact:
- C4-Nursery-0.57-cinematic-home
- artifact ID: 11492650373
- ZIP bytes: 48,155,896
- ZIP SHA256: ad888ea87baafeb09070a2ff8c1da07698f1eddda803537eaebd44e0c26ca841

APK:
- bytes: 48,155,475
- SHA256: 8c68661b24c8ce04cb76adb2d92cf1b7a397824bf8809a7f0c7ce101dd6f69c6
- unzip integrity PASS

VRM bundle SHA256:
5f3f0ee8cca9d3d81597c00b6cbe45f94e85790e303e2235ce2bd79e353902db

## Physical gate
- inspect room scale/occlusion on the user's phone;
- verify 3D prop positions match the visible environment;
- check mobile GPU thermal cost;
- verify body manifest acceptance with the current runtime.
