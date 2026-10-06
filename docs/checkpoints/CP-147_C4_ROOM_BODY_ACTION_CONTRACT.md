# CP-147 — C4 CAN ACT THROUGH THE ROOM BODY CONTRACT

Date: 2026-10-06

Implemented:
- Runtime ACTION_REQUEST now has a real host execution path into the persistent room registry.
- Allowlisted body/world actions: LOOK, TAKE, PLACE, MOVE.
- Host validates requestId, action and object before mutation.
- Affordance failures are explicit and do not claim execution success.
- Successful execution records before/after held/location state.
- Host returns ACTION_RECEIPT through the typed runtime transport using the original requestId.
- Room request IDs are persisted and bounded; replayed requests are rejected before world mutation.
- UI/runtime cannot mint verified success without host world execution.
- No C4 generation-specific code is introduced.

Build:
GitHub Actions run #120 completed SUCCESS for commit 9643ba0028bdcca104402d6beb6e0ebd967007e3.

Next:
- move execution authority for C4-originated actions fully into native Android host rather than WebView;
- add body pose/animation as presentation of verified receipts;
- extend object registry with containers and reach/grasp/release semantics.
