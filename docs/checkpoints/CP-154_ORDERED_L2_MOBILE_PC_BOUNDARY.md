# CP-154 — ORDERED L2 + MOBILE/PC WORLD BOUNDARY
Date: 2026-10-06

Product boundary:
- Mobile Nursery: compact home, body, chat, learning tasks, files and sensors.
- Large surrounding world: intentionally deferred to future PC environment.

Implemented:
- Native L2 tasks now persist progressStep.
- Successful room actions are matched against the active sequence in order.
- Step 2 before step 1 produces sequenceOrderMismatch and does not advance progress.
- L2 verification requires both final native locations AND progressStep >= 2.
- Active task remains restart-safe, so ordered progress survives process restart.
- UI shows live sequence progress after verified native receipts.
- Progress bar is projection only; Android owns causal progress.

Build:
GitHub Actions run #159 SUCCESS.

Next mobile work:
Improve body/object presentation and room usability, then sensory/chat/runtime readiness rather than expanding into a large mobile world.
