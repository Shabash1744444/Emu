# CP-166 — EMBODIED CHAT GREEN

Date: 2026-10-06
Status: GREEN
Binary code head: 052bb6c2271f7c4c7fa0d7633664e83db3562998

Release:
- versionCode 46
- versionName 0.46-embodied-chat
- GitHub Actions run #283
- artifact ID 11439127952
- artifact ZIP 33,814,860 bytes
- artifact ZIP SHA256 5059a3e5c42323a24ef1bc652d95440bbac18134212c342994dadb28101fbb93
- APK 33,814,442 bytes
- APK SHA256 add064c1944125cf5e4a64dea6cc0140abfcbce80ea7cb0d6c87ea673007d3c3

Passed:
- WebView JavaScript syntax
- Python py_compile
- Gradle assembleDebug
- APK archive integrity
- independent downloaded APK SHA verification

Implemented:
- direct 3-step brain setup inside Dialogue;
- expanding mobile composer and honest transport state;
- visible REPLY / ASK / PUBLISH distinction;
- live AUDIO, VISION and Android device-sensor telemetry;
- motion / rotation / light / proximity sensory stream;
- avatar contact sensory events;
- notification-permission and background-inbox hardening;
- exact APK version diagnostics;
- current core handoff updated to observed G260.

Boundaries:
UI != COGNITION
SENSOR FEATURE != CONCEPT
CAPTURED != PERCEIVED
PERCEIVED != LEARNED
PUBLISH UI != fabricated initiative
HOST CONTACT EVENT != semantic interpretation

Next device gates:
- install and interact on real Android hardware;
- test direct runtime/.c4m setup from Dialogue;
- test sustained microphone, camera and device-sensor sessions;
- test background initiative delivery;
- test exact G260 runtime compatibility.
