# CP-159 — TRUTHFUL AMBIENT SENSORY PRESENCE
Date: 2026-10-06

Implemented:
- Ambient sensor/source strip in chat.
- Host-side physical activity is visually distinct from runtime ingestion.
- MIC capturing -> host activity only.
- SCREEN streaming -> host activity only.
- SOURCE stored -> host activity only.
- C4 ingestion indicator is activated only by runtime SOURCE_PROGRESS / CHECKPOINT_COMMITTED events.
- UI explicitly states Host capture != C4 perception.
- Runtime STATUS can update runtime presence text.
- Runtime ERROR is presented as runtime error, never converted into an organism emotion/mood.
- No capture event mints C4 perception or independent evidence.

Build gates:
- #181 SUCCESS ambient sensory presence.
- #182 SUCCESS runtime status/error presentation.

Next:
Make source ingestion contract more explicit in adapter docs/trace, then continue visual polish and prepare a fresh distributable APK milestone.
