# CP-152 — NATIVE ROOM CURRICULUM DESCRIPTORS

Date: 2026-10-06

Implemented:
- Replaced the fixed BLOCK_TO_BASKET UI task with native-generated C4_ROOM_TASK_V1 descriptors.
- Generator reads current native world and chooses a portable BALL/BLOCK/BOOK plus a target different from its actual source location.
- Descriptor contains taskId, object, from, target, SANDBOX origin and instruction.
- Active descriptor is durably stored by Android.
- Verifier binds taskId/object/target to the active descriptor and rejects descriptor tampering.
- Existing host outcome/evidence-signature/replay semantics remain.
- UI displays native task and never computes success.
- "New task" can yield varied object/target combinations without rewriting UI.
- Active task is restored after process/app restart, preserving goal continuity.

Build gates:
- #147 SUCCESS: descriptor generator + dynamic task UI.
- #149 SUCCESS: restart-safe active task restoration.

Next:
Introduce curriculum difficulty and task prerequisites (single-step -> two-step -> sequence), while keeping capability progression distinct from fake XP/reward.
