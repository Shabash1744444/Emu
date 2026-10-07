# CP-185 — PRE COGNITIVE TRACE RECORDER

Date: 2026-10-07
Parent: CP-184 UI Bootstrap Hotfix GREEN
Status: PRE

Goal:
Make live failures reproducible by collecting transport logs and, when the runtime supports it, structured C4 decision traces.

Existing:
- runtime_trace/trace.jsonl already records app/runtime/sensory/action boundaries.
- chat export already separates training conversation from diagnostics.

Add:
- C4_COGNITIVE_TRACE_V1 protocol;
- trace modes OFF / EVENTS / DECISIONS / DEEP;
- structured TRACE_EVENT capture;
- one-interaction armed capture;
- separate cognitive_trace.jsonl;
- trace status and clear controls;
- export cognitive trace in diagnostic lane, never training lane.

Structured trace fields may include:
traceId, episodeId, step, owner, influence, phase, operation,
candidateId, subject, decision, reasonCode, evidenceRoots,
provenance, graphDelta, publicEventId.

Hard boundaries:
TRACE != EVIDENCE
TRACE != C4 MEMORY
TRACE != TRAINING DATA
TRACE != FREE-FORM HIDDEN MONOLOGUE
DEBUG OBSERVATION MUST NOT MUTATE COGNITION

If the installed runtime does not support trace commands/events, UI must say RUNTIME UNSUPPORTED rather than fabricate a chain.

Target release:
0.63.2-cognitive-trace
