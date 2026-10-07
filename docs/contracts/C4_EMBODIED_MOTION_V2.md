# C4 EMBODIED MOTION V2

Date: 2026-10-07
Status: visual embodiment contract
Parent: C4_VRM_LIFE_V1

## Purpose

Turn verified C4 motor receipts into coherent humanoid motion without creating a second controller in the UI.

Flow:
C4 ACTION_REQUEST
-> Android bounded execution
-> executionSuccess=true ACTION_RECEIPT
-> renderer motor queue
-> humanoid pose / locomotion / grasp projection

The queue is renderer scheduling only.

ANIMATION QUEUE != COGNITIVE PLAN
HAND POSE != INTENTION
GAZE POSE != ATTENTION CLAIM
RENDERED PROP != NEW WORLD EVIDENCE

## Receipt context

The renderer receives the complete verified receipt, not just an action string.

It may use:
- action
- object
- target
- before
- after
- verified host x / held state

It must never use renderer output to overwrite the native world receipt.

## Motion queue

- active motor motions are not destructively overwritten by later verified receipts;
- later receipts are queued in arrival order;
- queue is bounded to 8 visual actions;
- IDLE clears the visual queue;
- the queue is not persisted across process death.

## Persistent verified state

After renderer reload:
- host-confirmed body x may be restored;
- host-confirmed heldObject may be restored.

Unfinished gestures are never resumed after restart.

## Humanoid improvements

V2 adds:
- pelvis/chest counter-motion during steps;
- arm swing and foot articulation;
- root translation from verified native body x;
- target-aware reach and gaze based on verified room locations;
- right-hand finger curl during verified grasp;
- release/opening during verified place/release;
- persistent held-object proxy attached to the right hand;
- floor/grounding geometry and contact shadows.

The prop is a projection of native room state only.

## Telemetry

Home may display truthful renderer diagnostics:
- VRM version
- normalized bone count
- spring-bone availability
- current visual action
- queue length
- held object

These are renderer state, not organism psychology.
