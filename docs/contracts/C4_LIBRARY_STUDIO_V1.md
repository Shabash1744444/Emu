# C4 LIBRARY STUDIO V1

Date: 2026-10-07
Status: private-source presentation contract

## Purpose

Present private source material as a polished Library without changing source epistemics.

Categories are display-only:
- document
- image
- audio
- video

DISPLAY CATEGORY != SEMANTIC AUTHORITY
PREVIEW != EVIDENCE
THUMBNAIL != NEW SOURCE

## Storage

Library continues to use the existing private content-addressed source store.
Each source keeps its sourceId / SHA-256 lineage.

## Private image preview

The Android host may return a local data URL only when:
- sourceId is a valid SHA-256 source;
- private source and metadata both exist;
- MIME is image/png, image/jpeg or image/webp;
- file is <= 6 MiB.

The preview is generated from the exact stored bytes and never uploaded.

## Ingestion

Import remains separate from runtime delivery.

IMPORTED != INGESTED
INGESTED != LEARNED
LEARNED != TRUE

“Передать C4” remains an explicit user action.
Library presentation never auto-ingests sources.
