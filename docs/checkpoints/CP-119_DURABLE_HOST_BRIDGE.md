# CP-119 — DURABLE HOST BRIDGE

Implemented in main:
- NurseryNative.loadState()
- NurseryNative.commitState(json): JSON validation + synchronous durable SharedPreferences commit
- NurseryNative.now()
- NurseryNative.hostInfo()
- DOM storage enabled only as web-runtime facility; authoritative Nursery state uses native commit.
- file/content access disabled for current shell.

Acceptance invariant:
UI may claim a local state mutation only after commitState returns true.
No AI/model response is fabricated by the frontend.
Next: replace stub/toast UI with working persisted Home + event/chat surface.
