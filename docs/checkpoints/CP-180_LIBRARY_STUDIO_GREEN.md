# CP-180 — LIBRARY STUDIO GREEN

Date: 2026-10-07
Status: GREEN
Release head: e60c271a71c81675d6dbcb79eba73be9147f28ca
Build mechanism: one-shot CI release workflow due temporary GitHub connector update_file failure

## Implemented

- Library rebuilt as a private material studio;
- filters: all / documents / images / audio / video;
- real source count, private stored bytes and category count;
- source cards now show type-specific visual covers;
- exact private PNG/JPEG/WebP sources up to 6 MiB may render local thumbnails;
- thumbnails come from the existing content-addressed private source store;
- source SHA lineage remains visible;
- STORED / runtime transport state is visually separated;
- explicit “Передать C4” remains required;
- no auto-ingestion was introduced.

## Boundaries

IMPORTED != INGESTED
INGESTED != LEARNED
LEARNED != TRUE
PREVIEW != EVIDENCE
THUMBNAIL != NEW SOURCE
DISPLAY CATEGORY != SEMANTIC AUTHORITY

## Build

GitHub Actions custom Library Studio run #1: SUCCESS
Run ID: 37645167570

Artifact:
- C4-Nursery-0.60-library-studio
- artifact ID: 11493982376
- ZIP bytes: 48,164,520
- ZIP SHA256: 045f34acfb237dbfb6bd083bf9daeb4a28427a5de28a38a45fdef1a5118ba614

APK:
- bytes: 48,164,099
- SHA256: 2e441876470a4f1fead931e762d0c224406dae2ed3bf4f9ee18113de7f55431c
- unzip integrity: PASS

Bundled renderer:
- VRoid Sample D bytes: 16,851,352
- VRoid Sample D SHA256: 9adf1b44e959d2688d62c2dd558e74315d6aa40e3bf8d281390b7a85dc0df9b7
- three-vrm bundle SHA256: 5f3f0ee8cca9d3d81597c00b6cbe45f94e85790e303e2235ce2bd79e353902db

## Temporary release note

Repository app/build.gradle.kts still reports 0.59 because GitHub connector update_file/create_blob endpoints were failing during this pass.
The release workflow patches versionCode=60 and versionName=0.60-library-studio before Gradle.
The produced APK is therefore a real 0.60 build.
Sync build.gradle back to canonical main once the connector mutation endpoint is healthy.

## Physical gate

- inspect image thumbnail memory use on phone;
- inspect two-column card density;
- verify filters with mixed document/image/audio/video imports;
- verify runtime SOURCE_PROGRESS and “Передать C4” UX with current runtime.
