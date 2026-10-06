# CP-164 — SENSORY CORTEX GREEN

Date: 2026-10-06
Status: GREEN at build gate

## Release
- versionCode: 44
- versionName: 0.44-sensory-cortex
- GitHub Actions run: #240
- artifact: C4-Nursery-0.44-sensory-cortex
- artifact ID: 11430637101
- APK bytes: 33,790,954
- APK SHA256: 4ab83f3c91c576852336af79620771e6503c6fd5bdbf4dc272e85a7eaff1c278
- artifact ZIP digest: sha256:b15e3be6eac982035bbc4a698fbeebf0a94944b78c47c522c51136ca37d7fec1

## Gates
- WebView JavaScript syntax: PASS
- Python c4_mobile_bridge.py py_compile: PASS
- Gradle :app:assembleDebug: PASS
- staged APK nonzero: PASS
- APK unzip integrity: PASS
- independent downloaded APK SHA verification: PASS

## Implemented
- live microphone moved from opaque AAC capture to PCM16 mono 16 kHz stream;
- C4_SENSORY_FEATURES_V1 audio frames: RMS, mean abs, peak, zero crossings, fixed spectral probes, timing;
- raw PCM preserved as a private content-addressed source;
- camera photo, screenshot and live-screen frames produce a 12x8 RGB+luma retinal lattice plus light/contrast/local-edge measures;
- SENSORY_SESSION_START / SENSORY_FRAME / SENSORY_SESSION_STOP cross Android -> Python;
- runtime rejection remains explicit as RUNTIME_CAPABILITY_UNAVAILABLE;
- typed source/action-receipt command families are now routable through the Python adapter;
- open_organism now binds the active checkpoint path/H3/meta so checkpoint() can save the running organism;
- UI shows host-only sensory features versus runtime-accepted sensory flow;
- app handoff synchronized to canonical core G240, without claiming a G240 device boot.

## Non-negotiable boundary
No ASR transcript, object classification, emotion label, LLM/VLM description or other hidden semantic inference is inserted into the sensory layer.

SIGNAL != SOURCE
CAPTURED != PERCEIVED
PERCEIVED != LEARNED
FEATURE != CONCEPT
ACTION_REQUEST != VERIFIED_OUTCOME

## Remaining device gates
Build GREEN is not a hardware/sensory-learning claim. Next physical test must verify microphone permission/stream stability, camera/screenshot/live-screen feature delivery, installed runtime sensory capability, and exact G240 compatibility on device.
