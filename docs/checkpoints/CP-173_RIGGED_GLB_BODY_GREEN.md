# CP-173 — RIGGED GLB BODY GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 1a9a358c36c3fae8495ae31de0bc5cf58b9beedb

## Goal

Replace the geometric debug avatar path with a real 3D anime body while preserving C4 motor ownership and host epistemic boundaries.

## Implemented

### Secure local renderer
- WebViewAssetLoader local HTTPS origin
- app entrypoint: https://appassets.androidplatform.net/assets/index.html
- legacy file:// origin removed
- AndroidX WebKit 1.17.1
- @google/model-viewer 4.3.1 pinned and bundled during CI
- no runtime CDN dependency

### Private custom GLB lane
- Android SAF import
- .glb DISPLAY_NAME validation
- GLB magic validation: glTF
- 96 MiB cap
- private atomic copy
- SHA-256
- local private model URL:
  https://appassets.androidplatform.net/private/avatar-model.glb

### Rigged renderer
- GLB_RIGGED_BODY_V1
- reads availableAnimations from imported/bundled model
- receipt-driven clip matching
- real animation clip preferred
- bounded visual transform fallback only when no matching clip exists
- no visual action creates or changes C4 intent

Motor aliases include:
- IDLE
- WAVE
- NOD
- LOOK_AROUND
- STEP_LEFT
- STEP_RIGHT
- TAKE / GRASP
- RELEASE / PLACE
- MOVE
- LOOK

### Fallback hierarchy
1. rigged GLB body
2. PHOTO_ANIME_LAYER_V1 image
3. CSS debug silhouette

### Bundled default 3D anime body
- VRoid_Sample_D.glb
- long-haired VRoid sample
- CC0 1.0
- pixiv Inc. / VRoid Studio Team
- pinned upstream mirror commit:
  5e368bfff897d73090519f9f696c631a52d77397
- bytes in APK: 16,851,352
- SHA256:
  9adf1b44e959d2688d62c2dd558e74315d6aa40e3bf8d281390b7a85dc0df9b7

Bundled model-viewer:
- 1,068,903 bytes
- SHA256:
  283b0672384614b4847636c306fc93fe4b1fcadc76d668b4e47f0ca76bcf033b

## Semantic boundary

MODEL FILE != COGNITION
ANIMATION CLIP != INTENTION
USER APPEARANCE CHOICE != USER MOTOR CONTROL
ACTION_REQUEST != VERIFIED_OUTCOME

Only executionSuccess=true motor receipts may trigger action animation.

## Release

- versionCode 53
- versionName 0.53-rigged-glb-body
- GitHub Actions run #348 SUCCESS
- artifact ID 11479558415

Artifact ZIP:
- 47,902,807 bytes
- SHA256 6ac394846fcfb4859903865f16f7b95344dd18003d0d7396af72596ad704e2d8

APK:
- 47,902,383 bytes
- SHA256 86365fde9d705df8bff349c64f8f7d86927420e6377227a7b53bf255065c692c
- unzip integrity PASS

## Build gates

- pinned model-viewer vendor PASS
- pinned default GLB exact-byte check PASS
- WebView JavaScript syntax PASS
- selector regression PASS
- organism picker regression PASS
- stable chat regression PASS
- AI-owned body regression PASS
- Living Home realism PASS
- visual avatar V1 PASS
- rigged GLB body PASS
- Python py_compile PASS
- Gradle assembleDebug PASS
- APK archive integrity PASS

## Device gate

Exact 0.53 3D rendering and animation behavior still require a physical Android smoke-test.
The compatible G266 runtime path remains the proven organism boot baseline.

## Next

VRM-focused V2:
- humanoid bone mapping
- spring bones / hair physics
- expressions / blendshapes
- gaze
- visemes / voice coupling
- VRMA clips
- per-model license metadata
- mobile LOD / thermal policy
