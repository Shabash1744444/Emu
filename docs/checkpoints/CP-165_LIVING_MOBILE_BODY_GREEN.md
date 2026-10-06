# CP-165 — LIVING MOBILE BODY GREEN

Date: 2026-10-06
Status: GREEN at build gate
Binary code head: ccc72bf54d972093737eacd41a2c9276f2c26164
Documentation advanced afterward without binary changes.

## Release
- versionCode: 45
- versionName: 0.45-living-body
- GitHub Actions run: #264
- artifact: C4-Nursery-0.45-living-body
- artifact ID: 11431854363
- artifact ZIP bytes: 33,793,970
- artifact ZIP SHA256: c1bcc8f763aa46355b00869f01c3c0ea162a9864441077270a8641a992acd86d
- APK bytes: 33,793,558
- APK SHA256: ea923823e884dba1aaae2503f063e5b3b6189bb31813a072a5fb62c9ab9197a1

## Gates
- WebView JavaScript syntax: PASS
- Python c4_mobile_bridge.py py_compile: PASS
- Gradle :app:assembleDebug: PASS
- staged APK nonzero: PASS
- APK unzip integrity: PASS
- downloaded artifact ZIP integrity: PASS
- downloaded APK SHA verification: PASS

## What materially changed
1. Chat is the primary launch surface.
2. RUNNING organism autonomy moved into a foreground Android service.
3. Process-wide Python gate serializes Activity/service runtime calls.
4. Heartbeat prevents a stale RUNNING claim after process death.
5. Background runtime events are durable; C4 initiative is not silently lost when UI is hidden.
6. ASK/PUBLISH may become tappable Android initiative notifications.
7. Live camera is a continuous VISION sensory session.
8. Live screen is a continuous VISION session rather than unrelated still frames.
9. Microphone remains continuous AUDIO physical-feature sensing from CP164.
10. File/photo/audio/screenshot chat attachments can be sent into BEGIN_SOURCE / APPEND_SOURCE / END_SOURCE.
11. Binary chunks are base64 only across JSON transport and decoded back to bytes at the Python adapter.
12. Screenshot capture now enters the same SHA-256 source spool.
13. Library exposes explicit source delivery to C4.
14. Home/habitat visual layer gained depth, light, presence aura, breathing/blink and brain-live state.
15. Current observed core synchronization is G249, but exact G249 on-device SENSORY_* compatibility is NOT claimed yet.

## Epistemic/body boundaries
SIGNAL != SOURCE
CAPTURED != PERCEIVED
DELIVERED_TO_RUNTIME != INGESTED
INGESTED != LEARNED
LEARNED != ACCEPTED_AS_TRUE automatically
FEATURE != CONCEPT
ACTION_REQUEST != VERIFIED_OUTCOME
UI != COGNITION
BACKGROUND TICK != PROOF OF SUBJECTIVE EXPERIENCE

## Next physical gates
- install 0.45 on device;
- verify camera foreground service permission/start/stop;
- verify microphone stream over sustained use;
- verify C4 continues ticking with Activity backgrounded;
- verify pending ASK/PUBLISH appears after returning to the app;
- install exact current G249-compatible runtime + child_g249_audio_recurrence_green.c4m;
- test SENSORY_* and source methods against the real runtime;
- then begin the motor voice path: motor command -> synthesized physical sound -> speaker -> microphone/self-hearing -> correction, without substituting TTS for learned articulation.
