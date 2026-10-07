# C4 MATERIAL EXPERIENCE V1

Date: 2026-10-07
Status: private-source viewing contract
Parent: C4_LIBRARY_STUDIO_V1

## Purpose

Allow the user to open stored material inside C4 Nursery without silently promoting the material into C4 cognition.

Supported user-side views:
- image: private local stream
- audio: private local player
- video: private local player
- UTF-8 text/markdown/json/xml: bounded local reader

Unsupported formats remain stored and provenance-visible.

## Private source transport

A valid sourceId SHA-256 may be exposed only under:

https://appassets.androidplatform.net/private/source/<sha256>

The handler resolves only the exact private content-addressed bytes in the source store.

No external URL is created.
No source is uploaded.
Cache-Control is no-store.

## Text reader

Text preview:
- only text/*, application/json, markdown-like and xml-like MIME;
- max 262,144 bytes;
- exact source bytes remain unchanged;
- truncation is explicitly surfaced.

## Epistemic boundaries

OPENED != INGESTED
PLAYED != LEARNED
USER VIEW != C4 OBSERVATION
PREVIEW != EVIDENCE
MEDIA PLAYBACK != SOURCE ACCEPTANCE
TEXT RENDER != SEMANTIC UNDERSTANDING

Opening a source creates a UI-local USER_VIEW_ONLY trace.
It does not send SOURCE_* runtime commands.

“Передать C4” remains a separate explicit action.
