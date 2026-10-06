# C4 ORGANISM + RUNTIME LIFECYCLE V1

## Separation
The Android app treats these as separate objects:
1. **Organism state** — durable `.c4m`.
2. **Runtime** — executable engine implementing the four-law machine.
3. **Session** — one live binding of a compatible organism to a runtime.
4. **Bodies/sources** — phone sensors, sandbox, future PC body, files/media.

Selecting a `.c4m` never means the organism is running.

## Organism states
`EMPTY`
→ `IMPORTING`
→ `IMPORTED_UNVERIFIED`
→ `VALIDATING`
→ `COMPATIBLE`
→ `STARTING`
→ `RUNNING`
→ `STOPPING`
→ `COMPATIBLE`.

Failure states:
- `IMPORT_FAILED`
- `CORRUPT`
- `INCOMPATIBLE_SCHEMA`
- `INCOMPATIBLE_RUNTIME`
- `RUNTIME_MISSING`
- `START_FAILED`
- `CRASHED`
- `CHECKPOINT_FAILED`.

Only `RUNNING` may set `c4Transport=true`.

## Import transaction
1. User selects external document.
2. Stream-read with hard size ceiling while computing SHA-256.
3. Copy to app-private temporary file.
4. Flush + fsync.
5. Validate copied byte count/digest.
6. Atomically promote temp to active candidate.
7. Persist registry metadata.
8. Exact schema/runtime validation happens before COMPATIBLE.

External URI is provenance, not runtime dependency.

## Compatibility handshake
Runtime must expose:
- runtimeId / buildId
- supported organism schema range
- transport protocol version
- supported event types
- body/action ABI versions
- checkpoint format version
- optional acceleration/capability flags.

Organism manifest must eventually expose:
- format magic
- schemaVersion
- organismId
- createdBy build/checkpoint
- state sections + checksums
- required law/runtime ABI
- optional learned tensor/graph metadata.

Until canonical manifest is frozen, imported files remain `IMPORTED_UNVERIFIED`.

## Start gate
A session may start only if:
- private organism copy exists;
- digest matches registry;
- manifest validates;
- runtime handshake succeeds;
- schema and ABI overlap;
- memory/storage preflight passes;
- no other session owns active organism;
- recovery state is resolved.

## Crash/restart
Never claim RUNNING merely because it was running before process death.
On app restart:
- organism durable state remains;
- session becomes stopped/recovery-needed;
- unfinished physical ACTION_REQUEST is not replayed automatically;
- sandbox/world action must be reconciled before retry;
- live screen capture never auto-resumes.

## Checkpoint
Runtime checkpoint is a transaction:
1. request quiescent/checkpoint-safe boundary;
2. write new `.c4m.tmp`;
3. fsync;
4. validate checksums/schema;
5. preserve previous known-good backup;
6. atomic replace;
7. update registry digest/version;
8. emit CHECKPOINT_COMMITTED.

Frontend UI state is not organism state.

## Switching organisms
Stop current session → checkpoint if requested/possible → close runtime binding → import/validate target → start target.
No two organisms share mutable state by accident.

## Transport truth
Frontend sends USER_MESSAGE/source/body events only through an established RUNNING session.
Runtime outbound REPLY/ASK/PUBLISH/STATUS is accepted only from that session.
Delivery acknowledgement is not evidence.
ACTION_REQUEST is not outcome.
Only environment-owned receipt may report verified outcome.

## Future model bay
The UI may later support multiple installed organisms and multiple runtimes. Registry entries are keyed by organismId/digest; runtime selection is compatibility-based, never inferred from filename.
