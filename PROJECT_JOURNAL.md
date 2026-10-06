# C4 Nursery — Living Project Journal / New Chat Handoff
Updated: 2026-10-06 (CP164 / build #240 green). Repo: Shabash1744444/Emu, main.
Scope: Android Nursery application. The C4 neural/core runtime is developed separately.

## Mission
Build the Android body, home and learning environment for a C4 organism: normal dialogue, persistent avatar/home, files/camera/mic/screenshots/live-screen sensing, Library, causal worlds, organism bay, future PC/body actions, and restart-safe continuity. Target product density: comparable to the user's previous Arcade Hub, not a debug console.

## Non-negotiable boundaries
UI never invents cognition/evidence. MESSAGE != COGNITIVE EPISODE. ACTION_REQUEST != VERIFIED_OUTCOME. SANDBOX != REAL_WORLD. SIMULATION != OBSERVATION. PREDICTION != EVIDENCE. Replay/self-output/imported material cannot mint independent evidence. Imported != learned != true. Process death never auto-resumes physical/sensory actions. .c4m state != executable runtime. c4Transport stays false until a real runtime handshake reaches RUNNING.

Keep epistemic statuses distinct when supplied by core: DERIVED, UNKNOWN, CONFLICT, QUARANTINED, NEEDS_CHALLENGE, NEEDS_REVALIDATION.

## Implemented
- Android Activity + WebView product shell and durable UI state.
- Candidate-state transactions: clone -> mutate -> persist -> publish.
- Startup recovery for stale session and orphan imports.
- Dialogue timeline with gated C4 REPLY/ASK; no fake replies.
- File/camera/mic/screenshot/live-screen infrastructure.
- Private content-addressed source spool with SHA-256, fsync/promote, metadata sidecars and listSources().
- SAF display names.
- Native-backed Library page.
- .c4m private content-addressed store, installed list, activation/switching and truthful IMPORTED_UNVERIFIED state.
- Typed runtime command allowlist; absent runtime returns RUNTIME_NOT_INSTALLED.
- Causal mechanics + sequence memory.
- Native sandbox verifier owns outcomes/signatures.
- executionSuccess separated from predictionCorrect.
- Native anti-replay owns independentEvidence; DOM cannot promote novelty.

## Contracts
docs/contracts/C4_APP_TRANSPORT_V1.md
docs/contracts/C4_ORGANISM_RUNTIME_LIFECYCLE_V1.md
docs/contracts/C4_EVIDENCE_ENVELOPE_V1.md
docs/contracts/C4_RUNTIME_ADAPTER_V1.md
C4_CORE_HANDOFF.md is synchronization from the separate core branch.

## Current stage
MOBILE ORGANISM SHELL / VERIFIED LEARNING ENVIRONMENT.
The major seams exist: Android host <-> typed runtime socket <-> organism store; source/sensor spool <-> future runtime ingestion; renderer <-> native verifier <-> future ACTION_RECEIPT.
The real C4 engine is NOT embedded yet. Chat UI is now wired to the typed runtime contract and refuses to claim delivery unless a real RUNNING session accepts USER_MESSAGE.

## Build status
CP164 sensory-cortex code was gated on GitHub Actions run #240 and passed:
- WebView JavaScript syntax: PASS
- Python py_compile: PASS
- Gradle assembleDebug: PASS
- APK unzip integrity: PASS
- artifact: C4-Nursery-0.44-sensory-cortex
- artifact ID: 11430637101
- APK bytes: 33,790,954
- APK SHA256: 4ab83f3c91c576852336af79620771e6503c6fd5bdbf4dc272e85a7eaff1c278

The built APK now contains the first non-semantic sensory cortex. This is a host/body capability, not proof that the currently installed C4 runtime accepts or understands sensory frames.

## Next macroiteration
1. Device-test 0.44 on Android: microphone PCM stream, camera, screenshot and live-screen retinal frames.
2. Import exact current G240-compatible runtime + organism and verify whether the runtime exposes SENSORY_*; keep explicit RUNTIME_CAPABILITY_UNAVAILABLE otherwise.
3. Complete BEGIN_SOURCE / APPEND_SOURCE / END_SOURCE delivery from the private source spool to runtime with digest/offset checks.
4. Add continuous organism foreground service so cognition does not stop merely because the Activity is backgrounded.
5. Add the first motor voice surface (parameterized vocalization, not TTS) only behind ACTION_REQUEST -> execution receipt -> auditory feedback.
6. Continue room/body/world expansion after the sensor loop is physically verified.

## Known debt
Screenshot still uses older attachment path. Live-screen future runtime consumer is incomplete. ScreenStreamService lifecycle needs hardening. POST_NOTIFICATIONS polish remains. WebView bridge is larger than desired. WebView security needs audit. Causal mechanics are simplistic. Challenge generation is still partly DOM-owned. Source sidecar integrity/recovery needs hardening. Organism import should become single-pass digest+promote. recoveryInfo has stale previous.c4m concept. Stable signing is absent.

## Checkpoint discipline
Save a physical CP after every meaningful microstage and BEFORE long/risky work. Unsaved work counts as lost. Update THIS journal after every macroiteration. CP files are detailed history; this file is the canonical one-file handoff.

Recent: CP142 chat transport; CP143 training-safe trace export; CP144 crash-safe runtime trace; CP155-161 room/renderer/world; CP162 executable Python runtime host; CP163 normal C4 brain boot; CP164 non-semantic sensory cortex, build #240 green.

## Working style
User works from Android. When user says “делай/дальше/ебош”, take a substantial macroiteration: implement -> negative paths -> test -> checkpoint -> continue. Do not require repeated micro-confirmations.

## Next APK milestone gate
Green build; restart-safe Library; screenshot unified into source spool; native verified receipts with replay protection; core UI mutations transactional; truthful organism/runtime state; no fake cognition; downloaded APK independently checked for size, unzip integrity and SHA.

## End state
Install Nursery, attach a real organism/runtime when available, talk naturally, provide files/photos/audio/screen, let it act in controlled worlds, teach with provenance, inspect status without devtools, kill/restart without corrupting continuity, and later move the same organism to richer Android/PC bodies without changing C4 cognitive physics.


## 2026-10-06 — Repository boundary: C4 core
- User designated separate repository `Shabash1744444/-` as the future storage/home of the C4 core itself.
- `Shabash1744444/Emu` remains the Android Nursery/body/runtime-host/verified learning environment.
- Do not silently copy or freeze the evolving C4 core into Emu.
- Integration remains through explicit versioned runtime/organism contracts and attested artifacts.
- This preserves the existing rule: C4 core and its host/body are separable components.


## 2026-10-06 — CP164 sensory-cortex implementation
- Reframed Emu explicitly as C4's digital body/environment rather than a chat client.
- Added non-semantic `C4_SENSORY_FEATURES_V1` host cortex.
- Audio path now uses AudioRecord PCM16 mono at 16 kHz and emits timed physical feature frames while preserving raw PCM as a private content-addressed source.
- Visual path derives a 12x8 RGB+luma retinal lattice and simple light/contrast/edge measures from camera photos, screenshots and live-screen frames.
- Added typed runtime routing for SENSORY_SESSION_START / SENSORY_FRAME / SENSORY_SESSION_STOP and source/action-receipt command families; unsupported runtime capability stays explicit.
- Fixed Python bridge organism checkpoint binding so the active .c4m path/H3/meta are retained after open_organism.
- App synchronization note updated to canonical C4 G240; G240 device boot is NOT yet claimed.
- Release target: 0.44-sensory-cortex. CI/build result still required before GREEN.
