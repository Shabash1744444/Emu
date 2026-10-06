# CP-137 — TRANSACTIONAL SHELL + RECOVERY + TYPED RUNTIME SOCKET

Accepted build gates:
- #73 candidate transaction primitive SUCCESS
- #74 room/runtime/media migration SUCCESS
- #75 world outcome transaction + execution/prediction split SUCCESS
- #77 startup recovery SUCCESS

Implemented:
- clone/mutate/persist/publish transaction primitive;
- USER_MESSAGE, room actions, C4 messages, durable source/media additions use transactional state publication;
- sandbox receipts distinguish executionSuccess from predictionCorrect;
- causal distinct variant carries sandbox-lane independentEvidence; repeats do not;
- sequence-memory receipt never claims independent world evidence;
- startup deletes orphan import temps;
- stale runtime_running is downgraded to stopped recovery state;
- missing active private organism is surfaced as MISSING_PRIVATE_COPY;
- C4_RUNTIME_ADAPTER_V1 aligned to repository G207 handoff;
- narrow runtimeCommand allowlist exists;
- with no engine installed every allowed command returns RUNTIME_NOT_INSTALLED;
- no arbitrary native command execution and no fake model response.

G207 UI semantic requirement reserved:
DERIVED, UNKNOWN, CONFLICT, QUARANTINED, NEEDS_CHALLENGE, NEEDS_REVALIDATION remain distinct.

Next:
- remove remaining pre-transaction direct mutation sites (source inspection metadata);
- move sandbox receipt minting out of DOM into host/world verifier;
- runtime service implementation once canonical executable handoff exists;
- product UX expansion and hardened APK end-to-end gate.
