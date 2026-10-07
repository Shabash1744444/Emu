# C4 RIGGED GLB BODY V1

Date: 2026-10-07
Status: host/body renderer contract
Scope: C4 Nursery Android

## Goal

Render a real rigged glTF/GLB avatar as C4's visual body.

This renderer is downstream of cognition and motor execution.

C4 ACTION_REQUEST
-> Android sandbox execution
-> ACTION_RECEIPT executionSuccess=true
-> GLB animation clip / visual fallback

MODEL FILE != COGNITION
ANIMATION CLIP != INTENTION
RENDER SUCCESS != ACTION SUCCESS

## Storage and origin

- User imports .glb through Android Storage Access Framework.
- Host validates GLB magic "glTF".
- Host stores a private atomic copy.
- Host stores SHA-256 and byte size.
- Private model is exposed only under the local WebViewAssetLoader origin:
  https://appassets.androidplatform.net/private/avatar-model.glb

No public-storage URL is passed to the renderer.

## Renderer

Pinned build dependency:
@google/model-viewer 4.3.1

The library is bundled into the APK during CI.
Runtime does not require CDN access.

## Animation mapping

The renderer discovers model-provided animation names.

C4 motor receipts are matched conservatively to clip aliases:
- IDLE -> idle / stand / breath / waiting
- WAVE -> wave / waving / hello
- NOD -> nod / yes
- LOOK_AROUND -> lookaround / look / scan
- STEP_LEFT / STEP_RIGHT -> corresponding step/walk clips
- TAKE / GRASP -> take / grab / grasp / reach
- RELEASE / PLACE -> release / place / put / reach
- LOOK -> look / inspect / observe

If no matching clip exists:
- C4 action is NOT changed;
- renderer may use a bounded whole-body visual transform;
- UI reports the absence of a matching clip.

## Fallback hierarchy

1. rigged GLB body
2. PHOTO_ANIME_LAYER_V1 image
3. CSS debug silhouette

## Future V2

VRM-specific support:
- VRM humanoid metadata
- spring bones
- expressions / blendshapes
- gaze
- visemes
- VRMA motion clips
- per-model embedded license metadata
- mobile LOD and thermal policy
