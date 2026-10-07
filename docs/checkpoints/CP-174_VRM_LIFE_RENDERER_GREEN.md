# CP-174 — VRM LIFE RENDERER GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 237f88905d6ea25bb38f0dae6ba7be46c16fe48c

## Why this macro existed

The bundled default anime body in CP173 was a real skinned VRoid GLB, but binary inspection showed zero baked animation clips.

CP174 therefore makes the humanoid rig itself move.

Default body inspection:
- nodes: 144
- skins: 3
- meshes: 3
- VRM extension: present
- baked animation clips: 0

## Local renderer stack

Pinned and bundled during CI:
- Three.js 0.180.0
- @pixiv/three-vrm 3.5.5
- esbuild 0.28.2

No runtime CDN is required.

Bundle:
- assets/vendor/vrm-renderer.bundle.js
- 720,226 bytes
- SHA256 d0b6e43b31d9307c6a88c7103bf5f8aa147c654217970ef8795ba6bfc0f4b429

## VRM loading

Private avatar model lane accepts:
- .glb
- .vrm

Both require GLB magic "glTF".

VRM Life attempts to parse VRM metadata first.
If the model is not VRM:
- model-viewer GLB renderer is used.

Fallback hierarchy:
1. VRM Life humanoid renderer
2. model-viewer GLB renderer
3. photo-anime layer
4. CSS debug silhouette

## Neutral embodiment

The VRM renderer supplies:
- neutral breathing micro-motion
- neutral periodic blink where the model exposes a blink expression
- look-at target
- spring-bone / node-constraint update through vrm.update(delta)

These are presentation/body dynamics only.

BLINK != EMOTION
BREATHING VISUAL != BIOLOGICAL CLAIM
LOOK-AT RENDER != ATTENTION CLAIM

## Receipt-driven normalized humanoid motion

Only executionSuccess=true C4 motor receipts may start motor poses.

Supported V1:
- WAVE
- NOD
- LOOK_AROUND
- STEP_LEFT
- STEP_RIGHT
- TAKE / GRASP
- RELEASE / PLACE
- MOVE
- LOOK
- IDLE

Normalized VRM bones are used so VRM0 and VRM1 can share bounded pose logic.

User still cannot puppet C4.

## Release

- versionCode 54
- versionName 0.54-vrm-life
- GitHub Actions run #356 SUCCESS
- artifact ID 11480715132

Artifact ZIP:
- 48,142,398 bytes
- SHA256 468bbd666dced054c0bd6ef1bd9577a2daaa06b679dba404cd5fb5ed3f2ccc9c

APK:
- 48,141,995 bytes
- SHA256 aa0345a495afceca5e55cd3a3e194fa0566457440178e93d4f9eac7cab367037
- unzip integrity PASS

Bundled default:
- VRoid_Sample_D.glb
- 16,851,352 bytes
- SHA256 9adf1b44e959d2688d62c2dd558e74315d6aa40e3bf8d281390b7a85dc0df9b7
- CC0 1.0 provenance retained

## Build gates

- pinned model-viewer PASS
- pinned default VRoid GLB PASS
- pinned three / three-vrm / esbuild bundle PASS
- WebView JS syntax PASS
- selector regression PASS
- organism picker regression PASS
- stable chat regression PASS
- AI-owned body regression PASS
- Living Home realism PASS
- visual avatar V1 PASS
- GLB body PASS
- VRM Life PASS
- Python py_compile PASS
- Gradle assembleDebug PASS
- APK integrity PASS

## Physical device gate

Still required:
- verify exact avatar framing on the user's phone;
- verify default VRoid orientation;
- verify blink expression mapping on this model;
- verify WAVE/NOD/LOOK/STEP normalized bone signs;
- verify spring-bone behavior and thermal cost;
- verify fallback to model-viewer for non-VRM GLB.

Compatible G266 runtime remains the proven organism boot baseline.
