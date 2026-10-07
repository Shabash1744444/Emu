# C4 Nursery — Living Project Journal / New Chat Handoff
Updated: 2026-10-07 (CP172 / build #336 green). Repo: Shabash1744444/Emu, main.
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
LIVING MOBILE BODY / VERIFIED LEARNING ENVIRONMENT.
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

Recent: CP162 executable Python runtime host; CP163 normal C4 brain boot; CP164 non-semantic sensory cortex; CP165 living mobile body / foreground continuity / live vision, build #264 green.

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


## 2026-10-06 — CP165 living body
- Dialogue is now the default/primary surface; Home remains the organism's local habitat.
- RUNNING C4 moves from Activity-owned timer to OrganismService foreground continuity.
- Process-wide C4PythonGate serializes Activity/service calls into the Python runtime.
- Service heartbeat distinguishes live foreground continuity from stale process-death state.
- Real runtime ASK/PUBLISH/REPLY/etc produced while UI is hidden are durably queued; ASK/PUBLISH can surface as tappable Android notifications.
- Live camera vision added as a foreground camera service and one continuous VISION sensory session.
- Live screen is likewise represented as one continuous visual session rather than independent fake observations.
- Chat attachments (file/photo/audio/screenshot) can flow immediately into the private source spool and then BEGIN_SOURCE -> APPEND_SOURCE -> END_SOURCE.
- Binary source chunks are base64 only across JSON transport and are decoded back to bytes before a concrete Python append_source call.
- Screenshot now uses the same durable source spool instead of the older attachment-only path.
- Library has explicit "Передать C4" controls; STORED/DELIVERED_TO_RUNTIME remain distinct from INGESTED/LEARNED/TRUE.
- Room/home rendering received a living-body visual pass: depth, light, breathing/blink/presence animation and brain-live state.
- Core synchronization advanced from G240 to current observed G249 (1,247,711-byte organism); exact G249 device boot remains unverified.

Build gate:
- GitHub Actions run #264 SUCCESS.
- JavaScript syntax PASS.
- Python py_compile PASS.
- Gradle assembleDebug PASS.
- APK unzip integrity PASS.
- artifact: C4-Nursery-0.45-living-body
- artifact ID: 11431854363
- artifact ZIP bytes: 33,793,970
- artifact ZIP SHA256: c1bcc8f763aa46355b00869f01c3c0ea162a9864441077270a8641a992acd86d
- APK bytes: 33,793,558
- APK SHA256: ea923823e884dba1aaae2503f063e5b3b6189bb31813a072a5fb62c9ab9197a1

Physical device gates still required:
- live camera start/stop and foreground permission behavior;
- microphone streaming stability and battery/thermal behavior;
- background initiative notification permission on Android 13+;
- exact G249 runtime + .c4m SENSORY_* compatibility;
- source ingestion with the actual current runtime methods.


## 2026-10-06 — CP166 embodied chat
- Dialogue is the primary launch surface with direct Runtime ZIP, .c4m and Launch controls.
- Chat shows honest runtime transport state and distinct REPLY / ASK / PUBLISH messages.
- Input is now an expanding mobile textarea.
- Added live audio, vision and device-sensor telemetry in the chat HUD.
- Added Android device-sensor streaming for motion, rotation, light and proximity.
- Added avatar contact events as a separate sandbox sensory lane.
- Improved Android notification permission and background-event recovery.
- Exact APK version is shown in System diagnostics.
- Core handoff synchronized to observed G260; G260 device boot is still unverified.

Build gate:
- GitHub Actions run #283 SUCCESS.
- JavaScript syntax PASS.
- Python py_compile PASS.
- Gradle assembleDebug PASS.
- APK integrity PASS.
- artifact: C4-Nursery-0.46-embodied-chat
- artifact ID: 11439127952
- artifact ZIP bytes: 33,814,860
- artifact ZIP SHA256: 5059a3e5c42323a24ef1bc652d95440bbac18134212c342994dadb28101fbb93
- APK bytes: 33,814,442
- APK SHA256: add064c1944125cf5e4a64dea6cc0140abfcbce80ea7cb0d6c87ea673007d3c3


## 2026-10-07 — CP167 interaction hotfix
Physical symptom from device: UI rendered but buttons did not respond.

Root cause:
- WebView JavaScript used the single-element helper $() for collection operations in several legacy paths.
- Initial render called $('#dropTargets button').forEach(...), throwing at runtime before later click handlers were registered.
- The same class of bug existed in room/game selectors and retinal preview collection handling.

Fix:
- converted all collection-intended selector calls to $$();
- corrected retinal-grid collection handling;
- added CI lint which rejects single-element $() used with collection methods.

Build gate:
- GitHub Actions run #289 SUCCESS.
- JavaScript syntax PASS.
- selector misuse lint PASS.
- Python py_compile PASS.
- Gradle assembleDebug PASS.
- APK unzip integrity PASS.
- artifact: C4-Nursery-0.47-interaction-hotfix
- artifact ID: 11440789470
- artifact ZIP bytes: 33,814,659
- artifact ZIP SHA256: dc6a465913f6a5e2986a5e4af21b87c2f5545af55038131b09da04bd9ce24c3c
- APK bytes: 33,814,226
- APK SHA256: 0a3fe43ad7da7a51590c954e2100557f073c41e8f203358b11bf80f9cc231faa


## 2026-10-07 — CP168 organism picker hotfix
Physical symptom: selecting a .c4m in setup step 2 returned to the app with no visible change.

Root cause:
- Android ACTION_OPEN_DOCUMENT commonly returns content:// URIs without the original filename.
- The importer incorrectly searched the URI text for ".c4m", so valid organisms could fail with EXPECTED_C4M.
- ORGANISM_ERROR was stored only as a diagnostic event, making the failure look like no-op.

Fix:
- resolve OpenableColumns.DISPLAY_NAME and validate the actual display filename;
- emit ORGANISM_IMPORTING immediately;
- show hashing/copying, success and errors directly in the Dialogue setup gate;
- persist/display the organism filename;
- verify non-empty input and copied byte count;
- CI guard rejects URI-text .c4m validation regression.

Build gate:
- GitHub Actions run #296 SUCCESS.
- JavaScript syntax PASS.
- selector misuse lint PASS.
- organism picker regression lint PASS.
- Python py_compile PASS.
- Gradle assembleDebug PASS.
- APK unzip integrity PASS.
- artifact: C4-Nursery-0.48-organism-picker-hotfix
- artifact ID: 11441971846
- artifact ZIP bytes: 33,815,451
- artifact ZIP SHA256: edb932de27fabae61159f00d82929b0475458e509f4cf94ad0095712ee272818
- APK bytes: 33,815,006
- APK SHA256: 62cd08cae35add096f2f7b5a5266d48ea515b8a29543c21edd07911e15bbc31e


## 2026-10-07 — CP169 stable live chat
Physical G266 device result:
- compatible runtime + organism successfully reached C4 RUNNING;
- real autonomous ASK events arrived in Dialogue;
- repeated ASK flow caused the UI to rerender and force-scroll, making typing impractical.

Host/UI repair:
- conversation rendering isolated from full app rendering;
- incoming REPLY / ASK / PUBLISH use chat-only persistence/render path;
- user send uses explicit follow-bottom path;
- incoming events never steal scroll while composer is focused;
- reader position is preserved when not following the bottom;
- unread badge surfaces queued visible messages instead of forced scrolling;
- Android visualViewport drives a dynamic viewport height;
- keyboard mode hides nav/sensory chrome and keeps the composer usable;
- composer is visually prioritized directly below the feed;
- detailed sensory HUD is collapsed by default and can be opened explicitly;
- every real C4 event is still persisted; no cognition or initiative is suppressed.

Build gate:
- GitHub Actions run #303 SUCCESS.
- JavaScript syntax PASS.
- selector misuse lint PASS.
- organism picker regression lint PASS.
- stable chat forced-scroll regression guard PASS.
- Python py_compile PASS.
- Gradle assembleDebug PASS.
- APK unzip integrity PASS.
- artifact: C4-Nursery-0.49-stable-live-chat
- artifact ID: 11442428033
- artifact ZIP bytes: 33,816,613
- artifact ZIP SHA256: 495e55dbdde99d4dcc0a108c8c23263f59b779571eecdc836d0e23bf3ae97bb3
- APK bytes: 33,816,186
- APK SHA256: deaa05dab40505982aa62b27c75f5ebce55f3eebdb4022fa229c417b5847e083

Observed core behavior requiring separate core-level analysis:
- G266 currently emits multiple unresolved g223-world ASK events during autonomous ticks.
- CP169 does not delete, coalesce or suppress those organism events; it only prevents them from destabilizing the chat UI.


## 2026-10-07 — CP170 AI-owned body
User correction: the human must not puppet C4's avatar.

Agency boundary implemented:
- removed user-facing Wave / Move Ball / direct Take / Place / Look controls that executed C4 motor actions;
- Home now states explicitly that the body belongs to C4;
- user interactions are USER_WORLD (call, point/touch environment, avatar tactile contact), not C4_ACTION;
- sandbox challenges are delivered through WORLD_TASK capability probing instead of being smuggled through TICK;
- user-world interactions use WORLD_EVENT capability probing;
- unsupported runtime capability stays explicit RUNTIME_CAPABILITY_UNAVAILABLE.

C4 motor lane:
- ACTION_REQUEST remains the only route that can mutate C4 body state;
- native host now supports bounded body verbs WAVE, NOD, LOOK_AROUND, STEP_LEFT, STEP_RIGHT, IDLE;
- object motor verbs remain bounded by native affordances;
- C4-requested target is now forwarded to the native executor;
- verified motor receipts update only the habitat/avatar, not the whole app/chat;
- recent C4 motor action is visible in Home;
- animations are projections of executionSuccess=true receipts, never fabricated intentions.

Visual pass:
- autonomy/motor panel;
- richer avatar motor animations and presence glow;
- improved room depth, shadows, ball/block materials, window/rug lighting;
- room objects are passive world state in the user UI rather than puppet controls.

Build gate:
- GitHub Actions run #313 SUCCESS.
- JavaScript syntax PASS.
- previous selector / organism / stable-chat guards PASS.
- AI-owned-body regression guard PASS.
- Python py_compile PASS.
- Gradle assembleDebug PASS.
- APK archive integrity PASS.
- artifact: C4-Nursery-0.50-ai-owned-body
- artifact ID: 11474260570
- artifact ZIP bytes: 33,817,720
- artifact ZIP SHA256: 87102a271f48758c618f808279bea981d778939ae9b7e50622b752ce6a5e946a
- APK bytes: 33,817,302
- APK SHA256: 2f4888e16aec7e518393157f7d00a6b7b089c7950ae2102378107044dd3adf3a


## 2026-10-07 — CP171 Living Home
Reference direction: premium, cinematic living-world UI where Home, thoughts, world, library and senses feel like one organism environment.

Implemented:
- rebuilt Home as a real-state Living Home dashboard;
- large habitat hero with richer lighting, depth, bed, monitor glow and holographic orb;
- runtime presence ring driven only by runtimeInfo();
- latest C4 REPLY / ASK / PUBLISH shown as the Home thought card;
- quick modules for Dialogue, World, Library and Sensory channels;
- real counters for messages, ASK events, stored sources and host save time;
- real capability chips for chat, camera vision, microphone audio and body sensors;
- preserved C4-owned body boundary and user-as-external-actor model;
- kept fake emotion / curiosity / XP / energy metrics explicitly out of the UI;
- hardened navigation and collection selectors after a regression was detected;
- CI now rejects collection-selector misuse and fabricated organism metrics.

Build gate:
- GitHub Actions run #326 SUCCESS.
- WebView JavaScript syntax PASS.
- selector regression guards PASS.
- AI-owned body guard PASS.
- Living Home realism contract PASS.
- Python py_compile PASS.
- Gradle assembleDebug PASS.
- APK archive integrity PASS.
- artifact: C4-Nursery-0.51-living-home
- artifact ID: 11477637912
- artifact ZIP bytes: 33,821,870
- artifact ZIP SHA256: b1a9183f6f07495821de896d39f4a3350d93ad38c9180c973bcdaf63936cd0ce
- APK bytes: 33,821,458
- APK SHA256: 00de8ec1f40b16204618bf7d7f3b8376dd7a64b697860087c479a63f2708433b

Physical-device status:
- not yet visually inspected on-device for CP171;
- previous G266-compatible runtime path remains the known running baseline.


## 2026-10-07 — CP172 Visual Avatar Layer
User direction: replace the geometric/CSS avatar look with high-quality photorealistic-anime presentation while preserving C4 motor ownership.

Implemented:
- added a first-class private visual-avatar asset lane;
- Android SAF import for PNG / JPG / WebP;
- validates MIME, dimensions, non-empty file and 12 MiB size cap;
- copies avatar into private app storage and records SHA-256, filename, MIME, dimensions and bytes;
- exposes avatarInfo(), avatarDataUrl(), pickAvatarAsset() and clearAvatarAsset();
- Home now has a primary PHOTO_ANIME_LAYER_V1 visual body;
- old CSS avatar remains fallback/debug only;
- visual body receives breath/idle presentation plus receipt-driven WAVE, NOD, LOOK_AROUND, STEP_LEFT, STEP_RIGHT and reach projections;
- touching the visual body uses the existing TOUCH sensory lane;
- user can choose appearance but cannot issue C4 motor actions;
- documented the path from image visual body V1 to rigged VRM/GLB V2.

Semantic boundary:
VISUAL_ASSET != COGNITION
ANIMATION != INTENTION
USER APPEARANCE CHOICE != USER MOTOR CONTROL
Only verified C4 motor receipts drive action animations.

Build gate:
- GitHub Actions run #336 SUCCESS.
- WebView JavaScript syntax PASS.
- existing selector / picker / stable-chat / AI-owned-body guards PASS.
- visual-avatar contract guard PASS.
- Python py_compile PASS.
- Gradle assembleDebug PASS.
- APK archive integrity PASS.
- artifact: C4-Nursery-0.52-visual-avatar
- artifact ID: 11478796668
- artifact ZIP bytes: 33,823,656
- artifact ZIP SHA256: 9846535f34c3a23e4ae7385dddc19645a503f65c42a05a340bcbc8496747ca9c
- APK bytes: 33,823,238
- APK SHA256: 1b8639225408a191b19c8e61b4601af81a155ff4095be0d31d07265cdb0790a5

Device gate:
- image avatar import/render still needs physical Android visual inspection;
- compatible G266 runtime boot remains the known running baseline.
