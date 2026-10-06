# C4 Nursery — Living Project Journal / New Chat Handoff
Updated: 2026-10-06 (CP142). Repo: Shabash1744444/Emu, main.
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
Runs #86-93 were red because new verifier/source code lacked StandardCharsets and Cursor imports. Root cause fixed in commit 8eb57c2317ae60daae6ef62e0489a24f0da45f39.
Run #94 passed Gradle assembleDebug, APK verify/stage and artifact upload when observed. Treat cumulative #86-93 work as accepted only through green #94+.

## Next macroiteration
1. Route screenshot through the unified private source spool.
2. Add source lifecycle: STORED/QUEUED/INGESTING/INGESTED/ERROR without claiming learned/true.
3. Harden verifier: host-owned challenge IDs, requestId/action pairing, anti-replay and WorldEngine separation.
4. Audit remaining direct S mutations and convert core flows to transactions.
5. Improve Library -> queue for C4 UX; progress only from real SOURCE_PROGRESS.
6. Improve organism/runtime diagnostics and recovery.
7. Increase room/avatar/world/constructor product density and visual quality.
8. Harden WebView/ScreenStreamService/security.
9. At meaningful milestone: bump dev version, green Actions, download artifact, verify nonzero bytes/unzip/SHA, then give APK.

## Known debt
Screenshot still uses older attachment path. Live-screen future runtime consumer is incomplete. ScreenStreamService lifecycle needs hardening. POST_NOTIFICATIONS polish remains. WebView bridge is larger than desired. WebView security needs audit. Causal mechanics are simplistic. Challenge generation is still partly DOM-owned. Source sidecar integrity/recovery needs hardening. Organism import should become single-pass digest+promote. recoveryInfo has stale previous.c4m concept. Stable signing is absent.

## Checkpoint discipline
Save a physical CP after every meaningful microstage and BEFORE long/risky work. Unsaved work counts as lost. Update THIS journal after every macroiteration. CP files are detailed history; this file is the canonical one-file handoff.

Recent: CP136 transaction/recovery; CP137 typed runtime socket; CP138 external state-audit integration requirements; CP139 app-only scope; CP140 pre verified-world/library; CP141 verified world + durable Library; CP142 chat wired to typed runtime transport.

## Working style
User works from Android. When user says “делай/дальше/ебош”, take a substantial macroiteration: implement -> negative paths -> test -> checkpoint -> continue. Do not require repeated micro-confirmations.

## Next APK milestone gate
Green build; restart-safe Library; screenshot unified into source spool; native verified receipts with replay protection; core UI mutations transactional; truthful organism/runtime state; no fake cognition; downloaded APK independently checked for size, unzip integrity and SHA.

## End state
Install Nursery, attach a real organism/runtime when available, talk naturally, provide files/photos/audio/screen, let it act in controlled worlds, teach with provenance, inspect status without devtools, kill/restart without corrupting continuity, and later move the same organism to richer Android/PC bodies without changing C4 cognitive physics.
