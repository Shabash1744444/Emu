# CP-157 — WORLD-FIRST MOBILE SHELL
Date: 2026-10-06

Implemented:
- Room object list/debug panel removed from normal presentation; scene is now primary manipulation surface.
- Chat sensory controls consolidated into a compact glass dock for file/camera/mic/screenshot/live-screen capabilities.
- Capability truthfulness preserved: unavailable controls remain hidden.
- Library redesigned as a visual source shelf with source-type icon, display name, size, provenance/origin and physical availability.
- Library copy explicitly preserves imported != learned != true.
- Home curriculum controls compressed into a small mission panel instead of a large developer card.
- Redundant Move Ball control hidden because direct scene interaction supersedes it.
- Manual verify button hidden from product surface; native verifier remains available in flow.
- No changes to source-store authority or native room authority.

Build gates:
- #172 SUCCESS: sensory dock + Library source shelf.
- #173 SUCCESS: compact mission panel / world-first home.

Next:
Polish navigation and system/runtime presentation, then expose source/sensor activity as ambient in-world status without pretending C4 perceived anything until runtime ingestion confirms it.
