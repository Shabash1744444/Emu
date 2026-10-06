# CP-150 — HELD OBJECT + TARGETED RELEASE + VERSIONED ROOM WORLD

Date: 2026-10-06

Implemented:
- Held portable object is visibly projected next to C4 body.
- Room UI exposes explicit release targets: floor-left, floor-right, shelf, desk.
- Target buttons are enabled only while an object is held.
- Taking uses GRASP; placing uses RELEASE with explicit target.
- Android host validates every release target against native reachable zones.
- Object list no longer performs ambiguous default PLACE; held state is explicit.
- Native room world now carries _schema=1 and migrates older CP-148/149 state by adding missing zones/schema without resetting existing objects.
- Existing native room remains authority; visual state is projection only.

Build:
GitHub Actions run #137 completed SUCCESS for commit 2632cdfdf9f960a187868bfe6255da84f8e8a125.

Next:
Add richer native inventory/container model and first causal mini-game surface sharing the same action/receipt physics.
