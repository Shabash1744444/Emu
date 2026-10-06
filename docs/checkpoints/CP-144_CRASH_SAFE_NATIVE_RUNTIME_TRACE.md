# CP-144 — CRASH-SAFE NATIVE RUNTIME TRACE

Date: 2026-10-06

Implemented:
- Android host owns append-only runtime trace at private files/runtime_trace/trace.jsonl.
- Every runtimeCommand is logged before dispatch.
- Each record carries timestamp, direction, command type, requestId, current sessionId, organism SHA and original payload.
- Every append is fsynced so a future runtime crash cannot erase the last dispatched command.
- Training export includes nativeRuntimeTrace separately from UI trace and training conversation.
- Native trace is diagnostic only; it is never silently treated as training dialogue.
- Read path has a 16 MiB safety ceiling.

Current runtime truth:
No executable C4 engine is embedded. Adapter remains generation-agnostic and NOT_INSTALLED until a canonical runtime is bound.

Build gate:
GitHub Actions run #108 started for the cumulative CP142-144 code. Do not mark green until completed successfully.
