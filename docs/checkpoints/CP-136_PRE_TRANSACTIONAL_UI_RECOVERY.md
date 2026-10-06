# CP-136 — PRE TRANSACTIONAL UI + RECOVERY

Before long mutation pass.

Targets:
1. UI durable mutations use candidate state: clone -> mutate/event -> native commit -> publish candidate. Failed commit must not leave in-memory/rendered state ahead of disk.
2. Host startup reconciles organism/source temporary files and stale runtime ownership without auto-resuming physical/sensory actions.
3. Runtime integration gets a narrow typed command/event boundary; WebView must not gain arbitrary native execution.
4. Existing C4 transport remains false until a real runtime handshake reaches RUNNING.
