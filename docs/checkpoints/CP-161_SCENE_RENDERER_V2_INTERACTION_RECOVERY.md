# CP-161 — SCENE RENDERER V2 + INTERACTION RECOVERY
Date: 2026-10-06

Device feedback addressed:
- 0.40 was confirmed visually improved but still too close to original geometric smoke-test.
- all/most controls appeared dead on device.

Root cause of dead UI:
- several NodeList handlers incorrectly used querySelector ($) instead of querySelectorAll ($$), then called .forEach.
- JS initialization aborted before later handlers were attached.
- fixed all identified data-object/data-drop/dropTargets selector-list crashes.
- added visible top-level UI ERROR status for future uncaught WebView JS failures.

Scene renderer V2:
- taller, dominant room viewport;
- multi-layer ambient lighting;
- deeper window, shelf, desk, floor and rug treatment;
- improved avatar proportions, shading, hair/head/eyes/clothing;
- stronger scene/object shadows and depth;
- mobile home hides redundant fact cards so room dominates;
- native room authority and direct-object interaction semantics unchanged.

Milestone:
- versionCode 41
- versionName 0.41-scene-v2
- final build #201 SUCCESS
- artifact: C4-Nursery-0.41-scene-v2
- artifact ID: 11419200648
- ZIP size: 2,289,634 bytes

Next device gate:
Install 0.41, verify nav/buttons/object taps/new task first. If interaction is alive, use screenshots to move from procedural V2 toward richer art-backed/3D-capable renderer without changing native physics.
