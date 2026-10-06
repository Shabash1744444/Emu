# CP-131 — FUTURE MODEL BAY FOUNDATION

Goal: make the Android product ready for the real C4 network/runtime without future architectural surgery.

Implemented:
- selected .c4m is copied into app-private organism storage;
- temp file + close + fsync before promotion;
- external document URI is provenance, not runtime dependency;
- organism registry exposes privateCopy and validationState;
- UI no longer labels an unvalidated selected state as READY;
- explicit runtime diagnostics endpoint;
- capabilities advertise organism manager/lifecycle support, but c4Transport remains false;
- formal C4_ORGANISM_RUNTIME_LIFECYCLE_V1 contract.

Lifecycle:
EMPTY → IMPORTED_UNVERIFIED → VALIDATING → COMPATIBLE → STARTING → RUNNING.
Only RUNNING may enable c4Transport.

Planned failure states are contractually reserved:
CORRUPT, INCOMPATIBLE_SCHEMA, INCOMPATIBLE_RUNTIME, RUNTIME_MISSING, START_FAILED, CRASHED, CHECKPOINT_FAILED.

Required before real runtime integration:
- frozen canonical .c4m magic/manifest/schema;
- named runtime build/checkpoint;
- supported schema/ABI range;
- transport/body/checkpoint ABI;
- memory/storage preflight requirements.

No fake runtime or compatibility inference was added.
