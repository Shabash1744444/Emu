# CP-146 — PERSISTENT ROOM OBJECT REGISTRY

Date: 2026-10-06

Implemented:
- Nursery state schema v4 adds persistent room object registry.
- Initial objects: BALL, BOOK, PLANT, LAMP with typed kind/location/portable state.
- Room tracks selected and held object.
- Unified room action path replaces overlapping legacy handlers.
- LOOK, TAKE, PLACE and MOVE execute through state transaction and emit a separate ROOM_ACTION_RECEIPT.
- Failed affordances do not mutate world state.
- Portable constraints are enforced; stationary objects cannot be taken.
- UI renders the registry with inspect/take/place controls from state rather than hard-coded per-object action logic.
- Ball visual position derives from persistent object location.
- Receipts are forwarded to runtime transport as room events, but no cognition/outcome is fabricated.

Build:
GitHub Actions run #117 completed SUCCESS for commit 0753a2a7e70d24695a8144e6efe2970e58401b9f.

Next:
Host-owned execution of C4 ACTION_REQUEST against the same room registry, followed by verified ACTION_RECEIPT back to runtime.
