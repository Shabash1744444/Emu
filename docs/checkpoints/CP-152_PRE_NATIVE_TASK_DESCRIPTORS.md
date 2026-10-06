# CP-152-PRE — NATIVE ROOM TASK DESCRIPTORS
Date: 2026-10-06
Starting point: CP-151 / build #143 green.

Goal:
Replace the one-off BLOCK_TO_BASKET task with native-generated task descriptors derived from current room state.

Invariants:
- task generation reads native world only;
- descriptor names concrete object/from/target and carries a stable taskId;
- verifier checks the same descriptor, not UI claims;
- generated task is SANDBOX curriculum, not real-world evidence;
- UI displays descriptor but does not decide success.
