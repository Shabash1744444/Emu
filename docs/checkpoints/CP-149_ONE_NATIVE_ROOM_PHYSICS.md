# CP-149 — ONE NATIVE ROOM PHYSICS

Date: 2026-10-06

Implemented:
- Native room action vocabulary adds GRASP and RELEASE.
- RELEASE target is constrained to host-owned reachable zones: floor-left, floor-right, shelf, desk.
- Held-object invariant remains single-holder.
- Native room world is reconciled into WebView projection at startup; Android state wins over stale UI state.
- User room actions now use the same native executeRoomAction authority as C4-originated actions.
- Human and organism therefore share one room physics and one anti-replay/affordance path.
- WebView remains projection/presentation; native host owns execution facts.
- Verified body animation continues to follow successful native receipts only.

Build gates:
- #130 SUCCESS: grasp/release + startup native reconciliation.
- #131 SUCCESS: unified human/C4 native room execution.

Next:
Expose release targets/container UI; held-object visual; native world schema/version + migration; then richer room inventory and mini-game surfaces.
