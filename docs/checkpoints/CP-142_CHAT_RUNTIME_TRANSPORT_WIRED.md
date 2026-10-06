# CP-142 — CHAT WIRED TO RUNTIME CONTRACT

Date: 2026-10-06

Scope: app-side transport only. No particular C4 generation is embedded or treated as canonical.

Implemented:
- chat submit no longer mutates the visible user timeline as if delivery happened before runtime acceptance;
- submit requires runtimeInfo().state == RUNNING;
- USER_MESSAGE is sent through the typed runtimeCommand bridge with requestId, appTimestamp and USER provenance;
- rejected/missing runtime is recorded truthfully as USER_MESSAGE_REJECTED;
- accepted messages are persisted to the timeline only after host/runtime acceptance;
- runtime event ingress now accepts the full adapter event allowlist: REPLY, ASK, PUBLISH, STATUS, ERROR, ACTION_REQUEST, SOURCE_PROGRESS, CHECKPOINT_COMMITTED;
- frontend still cannot synthesize C4 cognition.

Important:
G208 was used only to understand the living-runtime shape. It is not frozen into the app. The app remains generation/runtime agnostic so a later trained C4 release can bind without rewriting chat UI.

Next:
- implement host-side runtime adapter/session state machine behind runtimeCommand;
- keep c4Transport false until a real executable runtime handshake reaches RUNNING;
- add OPEN_SESSION/CLOSE_SESSION UI/host flow and adapter diagnostics;
- then bind the eventual canonical executable C4 runtime package.
