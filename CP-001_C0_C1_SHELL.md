# CP-001 — C0/C1 executable shell
Date: 2026-10-05

Implemented:
- Capacitor Android package definition.
- One-button GitHub Actions debug APK factory.
- Mobile chat-first Nursery UI with state-driven motion/haptics.
- Runtime lifecycle shell: AWAKE / SLEEP / FROZEN / restore.
- Durable local state.
- Human text represented as `HumanTextFragment` stream events with source ID + durable cursor.
- Send is `boundaryHint`, not cognition reset.
- Freeze commits checkpoint before sealing mutations.

Known limitation: this is the host/runtime contract shell; the actual C4 cognitive core is intentionally not faked. SLEEP currently exposes the lifecycle slot but does not yet run consolidation physics.

Next: deterministic runtime tests, atomic/native persistence adapter, source pause/resume probes, then learning/provenance ledger interface.
