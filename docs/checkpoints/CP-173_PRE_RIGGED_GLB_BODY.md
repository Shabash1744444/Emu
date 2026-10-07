# CP-173 — PRE RIGGED GLB BODY

Date: 2026-10-07
Parent: CP-172 Visual Avatar Layer GREEN
Status: PRE

User direction:
Move beyond flat/geometric avatars to real high-quality anime 3D models.

Goal:
C4_VISUAL_AVATAR_V2 — rigged GLB body renderer.

Architecture:
- secure local WebView origin through WebViewAssetLoader;
- bundle pinned @google/model-viewer 4.3.1 into APK at build time;
- private .glb import through Android SAF;
- private model exposed to WebView through appassets path, not public storage and not base64;
- model-viewer renders PBR glTF/GLB;
- discover animation clips from the imported model;
- C4 ACTION_REQUEST -> native execution -> ACTION_RECEIPT -> matching animation clip;
- if a model lacks a requested clip, visual fallback transform may run, but no motor action is fabricated.

Ownership:
C4 owns motor actions.
User may choose appearance/model, not puppet it.

Fallback hierarchy:
1. GLB rigged body
2. photo-anime image body V1
3. CSS debug silhouette

No cognitive/runtime law changes.

Target release:
0.53-rigged-glb-body
