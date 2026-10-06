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
Runs #108/#109 exposed and preserved the compile failure caused by a literal escaped newline in MainActivity. Fixed in c5b07e1a7b29dd140bf6b354991ee86cd4a87a10. Run #110 completed SUCCESS, including assembleDebug, APK verify/stage and artifact upload. Artifact C4-Nursery-DEV38: 2,274,698 bytes; workflow artifact digest sha256:7eda0893ffbddff26328f6bbac7c4c3a626118de2f47e482dc6e8c0edd26bc72.
