# CP-123 — LIVE SCREEN SESSION IMPLEMENTED / BUILD GATE

Known green:
- run #18: one-shot MediaProjection screenshot compile + artifact upload SUCCESS.
- run #19 checkpoint commit also SUCCESS.

Implemented after green gate:
- Android foreground service type=mediaProjection;
- explicit user-consented screen stream start;
- non-exported service;
- visible ongoing notification;
- per-session UUID provenance root;
- bounded sampler ~1 frame / 1500 ms, JPEG quality 55;
- cache retention cleanup (~15 seconds);
- START / FRAME / STOP host receipts;
- explicit stop control;
- START_NOT_STICKY; no automatic stream resurrection after process death;
- UI exposes Stream only when screenCapture capability exists;
- individual frames are transient telemetry, not durable evidence;
- durable journal stores session start/stop + aggregate frame count.

Build gate:
runs #20-24 pending at checkpoint creation. Do not call live screen accepted until latest build is green.

Next after green:
C4 event transport contract + source ingestion contract, then richer causal world/minigame environment.
