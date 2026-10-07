# CP-185 — COGNITIVE TRACE RECORDER GREEN

Date: 2026-10-07
Status: GREEN
Release: 0.64.2-cognitive-trace
versionCode: 67
Binary workflow head: 81929eb4f2c175b719ce7297c1417e9439781d5d
GitHub Actions run: #481
Run ID: 37678628337

## Implemented

### Existing transport trace retained
runtime_trace/trace.jsonl continues to record:
- APP_TO_RUNTIME
- RUNTIME_COMMAND_RESULT
- RUNTIME_TO_APP
- SENSOR_TO_RUNTIME
- HOST_WORLD / ACTION_RECEIPT
- HOST_ACTUATOR / ACTION_RECEIPT
- HOST_TO_UI

### New cognitive trace lane
- separate runtime_trace/cognitive_trace.jsonl;
- TRACE_* runtime events only;
- schema C4_COGNITIVE_TRACE_V1;
- modes OFF / EVENTS / DECISIONS / DEEP;
- scopes CONTINUOUS / NEXT_INTERACTION;
- active file rotates at ~24 MiB;
- previous cognitive trace retained;
- export read bound 32 MiB.

### Runtime protocol
Nursery now supports:
- TRACE_CONFIG
- TRACE_SNAPSHOT

Python adapter feature-detects:
- generic handle_runtime_command/runtime_command;
- trace_config / configure_trace / set_trace_config;
- trace_snapshot / get_trace_snapshot / diagnostic_snapshot.

Unsupported runtimes remain explicit RUNTIME_CAPABILITY_UNAVAILABLE.

### UI
System page now exposes C4 Trace Recorder:
- transport bytes;
- cognitive bytes;
- runtime support state;
- mode controls;
- “Следующая реплика” one-episode DEEP arm;
- runtime snapshot;
- clear diagnostics;
- last TRACE event summary.

### Export
C4_NURSERY_TRAINING_BUNDLE_V3 lanes:
1. trainingConversation
2. uiDiagnostics
3. nativeTransportTrace
4. cognitiveTrace

Only trainingConversation is training-eligible.

## Boundaries
TRACE != EVIDENCE
TRACE != MEMORY
TRACE != TRAINING DATA
TRACE != FREE-FORM HIDDEN MONOLOGUE
DEBUG OBSERVATION MUST NOT MUTATE COGNITION

No cognitive chain is synthesized from the final answer when runtime tracing is unsupported.

## Runtime-side task
Core repository now contains:
C4_COGNITIVE_TRACE_RUNTIME_TASK.md

Expected structured chain:
input/event
-> candidates
-> EVAL / COMMIT / DRIVE / MEDIATE
-> influence
-> evidence roots / provenance
-> graph delta or no-delta
-> public event/action.

## Build verification
- WebView JS syntax: PASS
- UI contract: PASS (172 IDs / 50 critical bindings)
- Python py_compile: PASS
- Gradle assembleDebug: PASS
- APK staging/integrity: PASS

Artifact:
- C4-Nursery-0.64.2-cognitive-trace
- artifact ID: 11507931835
- ZIP bytes: 49,399,274
- ZIP SHA256: d7f2060ce89e235cfdfa91275e019ab43e88f72bc0eac9c9829d608154170642

APK:
- bytes: 49,398,844
- SHA256: f22ee4ddbcac9d13887557c3e94b0be52b24e81d3325b9057346a7794c4fe8d4

## Physical/runtime gate
- verify System trace controls on target phone;
- verify transport trace export with current runtime;
- current runtime may report cognitive trace unsupported until it implements C4_COGNITIVE_TRACE_RUNTIME_TASK.md;
- once supported, verify trace-off vs trace-on does not alter deterministic graph/public output.
