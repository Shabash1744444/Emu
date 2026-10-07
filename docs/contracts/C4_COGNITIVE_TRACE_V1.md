# C4 COGNITIVE TRACE V1

Date: 2026-10-07
Status: diagnostic protocol

## Purpose

Record C4 decisions in a structured, read-only diagnostic lane so live failures can be reproduced without contaminating learning or inventing post-hoc explanations.

## Existing transport trace

Nursery always records boundary traffic in runtime_trace/trace.jsonl:
- APP_TO_RUNTIME
- RUNTIME_COMMAND_RESULT
- RUNTIME_TO_APP
- SENSOR_TO_RUNTIME
- HOST_WORLD / ACTION_RECEIPT
- HOST_ACTUATOR / ACTION_RECEIPT
- HOST_TO_UI

This is useful even when the runtime has no cognitive tracing capability.

## Cognitive trace

When the installed runtime supports TRACE_CONFIG / TRACE_SNAPSHOT and emits TRACE_* events, Nursery stores them separately in:

runtime_trace/cognitive_trace.jsonl

Rotation:
- active file rotates at ~24 MiB;
- previous file retained separately;
- read/export bound is 32 MiB.

## Modes

OFF
- no cognitive TRACE_* persistence.

EVENTS
- cognitive episode/event structure only.

DECISIONS
- owner/influence/decision/basis records.

DEEP
- candidates, evidence roots, provenance, graph deltas and public-event links where runtime exposes them.

## Scope

CONTINUOUS
- keep tracing until disabled.

NEXT_INTERACTION
- arm DEEP trace for one USER_MESSAGE episode.
- runtime, not UI, decides when the causally attached episode closes.

## Expected runtime structure

Preferred TRACE_EVENT fields:
- traceId
- episodeId
- step
- wallTime
- owner: EVAL / COMMIT / DRIVE / MEDIATE
- influence: MASK / VALUE / AVAIL / TRIGGER / STATUS
- phase
- operation
- subject
- candidateId
- decision
- reasonCode
- evidenceRoots
- provenance
- graphDelta
- publicEventId

Stable IDs / reason codes are preferred over generated natural-language rationales.

## Epistemic boundary

TRACE != EVIDENCE
TRACE != MEMORY
TRACE != TRAINING DATA
TRACE != FREE-FORM HIDDEN MONOLOGUE
DEBUG OBSERVATION MUST NOT MUTATE COGNITION

The trace subsystem is an observer beside existing gates. It is not a fifth owner and may not affect EVAL/COMMIT/DRIVE/MEDIATE.

## Export

C4_NURSERY_TRAINING_BUNDLE_V3 keeps four lanes separate:

1. lanes.trainingConversation
2. lanes.uiDiagnostics
3. lanes.nativeTransportTrace
4. lanes.cognitiveTrace

Only trainingConversation is training-eligible by bundle policy.

## Unsupported runtime

If TRACE_CONFIG is unavailable:
- Nursery shows runtime UNSUPPORTED;
- transport trace continues;
- cognitive chain is not synthesized from the final answer.
