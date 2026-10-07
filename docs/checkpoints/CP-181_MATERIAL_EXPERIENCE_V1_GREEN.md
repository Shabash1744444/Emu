# CP-181 — MATERIAL EXPERIENCE V1 GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 54ae2b127281b031f0ff44363c19dcc29294fffa

## Implemented

- private source streaming under appassets local origin;
- exact content-addressed SHA source resolution only;
- image viewer;
- audio player;
- video player;
- bounded UTF-8 text/markdown/json/xml reader;
- text reader cap: 262,144 bytes with explicit truncation notice;
- provenance strip shows source SHA / transport state / bytes;
- explicit “Передать C4” remains separate from opening/viewing;
- closing viewer stops audio/video playback;
- unsupported formats remain stored and provenance-visible.

## Boundaries

OPENED != INGESTED
PLAYED != LEARNED
USER VIEW != C4 OBSERVATION
PREVIEW != EVIDENCE
MEDIA PLAYBACK != SOURCE ACCEPTANCE
TEXT RENDER != SEMANTIC UNDERSTANDING

Opening a source emits only USER_VIEW_ONLY UI trace with c4Observation=false and ingested=false.

## Build

GitHub Actions run #424: SUCCESS
Run ID: 37647657469

Artifact:
- C4-Nursery-0.61-material-experience
- artifact ID: 11495440714
- ZIP bytes: 48,168,247
- ZIP SHA256: 7fe384d11932d5a59762d64f1763b26a9d653a0c7b1b79c9e2221a0b360e8a23

APK:
- bytes: 48,167,811
- SHA256: ae5b117952d6950b6e279f7f557cc7a4042f089fdbe4f52259348f63df477683
- unzip integrity PASS

Bundled renderer:
- VRoid Sample D SHA256: 9adf1b44e959d2688d62c2dd558e74315d6aa40e3bf8d281390b7a85dc0df9b7
- three-vrm bundle SHA256: 5f3f0ee8cca9d3d81597c00b6cbe45f94e85790e303e2235ce2bd79e353902db

## Physical gate

- verify audio/video playback through WebViewAssetLoader on target Android;
- verify video seek behavior;
- verify large text scrolling;
- verify back/close stops playback;
- verify unsupported PDF/EPUB UX.
