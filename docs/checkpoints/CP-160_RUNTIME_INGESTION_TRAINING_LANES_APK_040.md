# CP-160 — RUNTIME INGESTION + TRAINING LANES + APK 0.40
Date: 2026-10-06

Completed in one large pass:

## Runtime/source contract
- Added explicit CAPTURED -> STORED -> INGESTING -> INGESTED host/runtime source state model.
- Explicitly preserved INGESTED != LEARNED != ACCEPTED_AS_TRUE.
- SOURCE_PROGRESS is runtime-owned; UI cannot infer ingestion from host storage.
- CHECKPOINT_COMMITTED is not evidence that a source was learned/believed.

## Trace integrity
- Every runtime command attempt remains APP_TO_RUNTIME.
- Added separate RUNTIME_COMMAND_RESULT trace entry for rejection/result.
- Native HOST_TO_UI events are durably traced before WebView delivery.
- This distinguishes attempted command, host/runtime result, and delivered host event.

## Training export V2
- Bundle format bumped to C4_NURSERY_TRAINING_BUNDLE_V2.
- Explicit lanes:
  - lanes.trainingConversation
  - lanes.uiDiagnostics
  - lanes.nativeTransportTrace
- Diagnostic lanes are marked excluded from training.
- Stored/imported sources remain excluded by default.
- Policy records STORED != INGESTED and INGESTED != LEARNED/TRUE.

## Protocol cleanup
- Removed attempted ROOM_INTERACTION runtimeCommand calls.
- ROOM_INTERACTION remains local UI journal only.
- Verified world effects continue through contract-defined ACTION_RECEIPT.

## Android milestone
- versionCode 40
- versionName 0.40-dev40
- Workflow artifact naming updated.
- Build #190 SUCCESS before artifact rename.
- Final milestone build #191 SUCCESS.
- Artifact ID: 11416736392
- Artifact name: C4-Nursery-0.40-dev40
- Artifact ZIP size: 2,288,085 bytes.

Next:
On-device visual smoke test of 0.40; then fix real UX/layout issues found on hardware and continue toward runtime adapter implementation when the evolving C4 core exposes an attested executable/runtime artifact.
