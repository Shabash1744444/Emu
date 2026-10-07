# C4 BODY MANIFEST V1

Date: 2026-10-07
Status: host/body capability contract

## Purpose

Describe the physical/digital organs provided by the Android body to the C4 runtime.

The manifest is a capability description. It is not an observation and not evidence about the external world.

BODY_MANIFEST != OBSERVATION
AVAILABLE != RUNTIME_SUPPORTED
CAPABILITY != ACTION
CAPABILITY != VERIFIED OUTCOME

## Handshake

After a real runtime reaches OPEN_SESSION/RUNNING, the host offers BODY_MANIFEST.

If the runtime supports one of:
- handle_runtime_command / runtime_command;
- body_manifest;
- set_body_manifest;
- capability_manifest;
- receive_body_manifest;

it may accept the manifest.

If unsupported:
- organism launch stays RUNNING;
- bodyManifestAccepted=false;
- no capability is fabricated.

## Organs

Current host descriptions include:
- VISION_CAMERA
- AUDIO_MIC
- BODY_ACCELEROMETER
- BODY_GYROSCOPE
- BODY_LIGHT
- BODY_PROXIMITY
- SCREEN_VISION
- TOUCH_BODY
- HUMANOID_BODY
- VOCAL_MOTOR

The manifest is generated from actual Android package/sensor availability where applicable.

## Motor vocabulary

Host advertises bounded available body verbs:
WAVE / NOD / LOOK_AROUND / STEP_LEFT / STEP_RIGHT / IDLE
LOOK / TAKE / PLACE / MOVE / GRASP / RELEASE
VOCALIZE

This does not cause any action.

C4 still owns action selection.
Native host still owns execution verification.
