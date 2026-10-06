# CP-153 — VERIFIED CURRICULUM GATES + L2 SEQUENCES

Date: 2026-10-06

Implemented:
- Native C4_ROOM_CURRICULUM_V1 state.
- L1 mastery counts distinct verified successful object->target capabilities, not clicks or XP.
- Replayed task receipts cannot increase mastery.
- Failures remain receipts and do not subtract a synthetic score.
- L2 unlock requires 3 distinct verified L1 successes.
- Curriculum state is persisted in Android SharedPreferences and exposed read-only to UI.
- UI displays verified mastery progress and gate state.
- Once L2 is unlocked, native generator can issue C4_ROOM_SEQUENCE_TASK_V1 with two object transfers.
- Sequence verification requires both native final object locations to match their descriptor targets.
- Sequence descriptor fields are bound to the active native task to prevent UI/runtime substitution.
- All curriculum outcomes remain SANDBOX.

Build gates:
- #153 SUCCESS: verified mastery gate UI/state.
- #155 SUCCESS: native L2 sequence generation and verification.

Next:
Record ordered step receipts for sequence tasks so L2 verifies not only final state but causal order; then expose curriculum/task events directly through the future runtime adapter.
