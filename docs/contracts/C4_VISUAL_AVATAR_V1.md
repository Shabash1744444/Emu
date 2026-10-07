# C4 VISUAL AVATAR V1

Date: 2026-10-07
Status: host/body contract
Scope: C4 Nursery Android visual body layer

## Purpose

Replace the geometric debug avatar with a high-quality visual representation while preserving C4 agency.

The visual body is presentation. It is not cognition, memory, evidence, emotion, or intent.

VISUAL_ASSET != COGNITION
ANIMATION != INTENTION
USER APPEARANCE CHOICE != USER MOTOR CONTROL

## V1 asset lane

Supported private visual assets:
- image/webp
- image/png
- image/jpeg

The Android host:
1. opens the image through SAF;
2. validates MIME and dimensions;
3. copies it into private app storage;
4. computes SHA-256;
5. exposes only the private copy to the WebView;
6. records filename, MIME, bytes, dimensions and digest.

The WebView uses the visual asset as the primary avatar body.
The old CSS body is fallback/debug only.

## Motor projection

C4 remains the sole owner of motor decisions.

C4 ACTION_REQUEST
-> native execution / affordance check
-> ACTION_RECEIPT executionSuccess=true
-> visual pose projection

V1 pose projection may use whole-image transforms because this is not yet a skeletal rig.

Supported visual projection tags:
- WAVE
- NOD
- LOOK_AROUND
- STEP_LEFT
- STEP_RIGHT
- TAKE / GRASP / RELEASE / PLACE / MOVE / LOOK
- IDLE

The visual renderer must never generate ACTION_REQUEST.

## Touch

Touching the visual avatar creates the same bounded TOUCH sensory contact as the fallback body.
Normalized coordinates are mapped to coarse host anatomy metadata.

TOUCH CONTACT != PAIN
TOUCH CONTACT != EMOTION
TOUCH CONTACT != SOCIAL INTENT

## Next renderer target

V2 should support a rigged avatar package:
- VRM / GLB candidate import;
- skeletal bones;
- facial blendshapes;
- gaze;
- mouth/voice coupling;
- verified motor action -> animation state;
- physics accessories / hair;
- LOD for mobile GPUs.

The renderer remains downstream of C4 motor receipts.

## Privacy

Avatar assets remain private app data and are not automatically uploaded or treated as training material.
