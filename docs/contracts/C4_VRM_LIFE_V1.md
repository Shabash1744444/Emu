# C4 VRM LIFE V1

Date: 2026-10-07
Status: visual embodiment contract
Scope: C4 Nursery Android

## Purpose

Give a VRM humanoid visual body low-level life-like motion without fabricating cognition, intention or emotion.

Renderer stack:
- Three.js 0.180.0
- @pixiv/three-vrm 3.5.5
- local bundled ESM build
- WebViewAssetLoader secure local origin

## Load path

The renderer accepts:
- VRM-extended GLB
- .vrm
- VRM0 and VRM1 metadata through VRMLoaderPlugin

The default bundled VRoid Sample D contains VRM metadata and can therefore use this renderer even though its file extension is .glb.

If VRM metadata is absent:
VRM Life -> model-viewer GLB -> photo layer -> CSS fallback.

## Neutral embodiment loop

Allowed autonomous visual-only processes:
- breathing micro-motion
- neutral periodic blink
- spring-bone update
- neutral gaze toward the current look-at target

These do not assert C4 mental state.

BLINK != EMOTION
BREATH MOTION != BIOLOGICAL CLAIM
GAZE RENDER != ATTENTION CLAIM
SPRING BONE PHYSICS != COGNITION

## C4-owned procedural motor poses

Only a verified motor receipt may start a semantic motor pose.

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

Flow:
C4 ACTION_REQUEST
-> native bounded execution
-> executionSuccess=true ACTION_RECEIPT
-> VRM normalized humanoid bone motion

User cannot call these motor poses directly.

## Humanoid layer

Renderer uses normalized VRM bones so VRM0/VRM1 models can share the same bounded pose logic.

The frame loop:
1. resets normalized pose;
2. applies neutral breathing;
3. applies active verified motor pose;
4. applies blink expression if available;
5. runs vrm.update(delta), including spring-bone / constraints;
6. renders the frame.

## Facial policy

V1 may use:
- blink
- look-at

V1 does NOT synthesize:
- happy
- sad
- angry
- surprised
- mood

Those require an explicit future C4-owned expression/action contract.

## Voice path later

Mouth visemes must be driven by the future C4 voice actuator or verified speech-render state, not by arbitrary UI text.
