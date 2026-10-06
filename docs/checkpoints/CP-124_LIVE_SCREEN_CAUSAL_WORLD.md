# CP-124 — LIVE SCREEN + CAUSAL WORLD MACROITERATION

Build evidence:
- #18 screenshot MediaProjection: Gradle + artifact SUCCESS.
- #20 foreground-service manifest: SUCCESS.
- #21 bounded ScreenStreamService: SUCCESS.
- #22 Activity stream bridge: SUCCESS.
- #23 stream UI controls/receipts: SUCCESS.

Live screen semantics:
- explicit consent/start/stop;
- foreground notification;
- UUID provenance root per session;
- sampled frames transient; durable state stores session aggregate, not every frame;
- no automatic resurrection after process death.

Core integration:
- docs/contracts/C4_APP_TRANSPORT_V1.md added.
- c4Transport remains false until a named core handoff exists.

Causal world:
- World surface now contains PUSH_TARGET_V1.
- prediction is selected before action.
- challengeVariant F1/F2 changes outcome.
- outcome generated after bounded animation delay.
- SANDBOX_RECEIPT contains experiment, challengeVariant, prediction, outcome, success.
- dead old Experience page removed.
- no XP/competence minting in UI.

Next:
build gate latest world commits; then expand world mechanisms and source/media ingestion toward C4 transport.
