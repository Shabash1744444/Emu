# CP-149-PRE — NATIVE ROOM RECONCILIATION + GRASP SEMANTICS
Date: 2026-10-06

Starting point: CP-148 / build #126 green.

Goal:
Extend native-owned room physics with reach zones/containers and GRASP/CARRY/RELEASE semantics, then make native world authoritative during startup reconciliation.

Invariants:
- native_room_world wins over stale WebView projection.
- body pose follows verified receipt only.
- held object has exactly one holder/location.
- release target must be an allowlisted reachable zone/container.
- replay cannot mutate twice.
