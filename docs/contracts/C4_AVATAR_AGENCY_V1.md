# C4 AVATAR AGENCY CONTRACT V1

Date: 2026-10-07
Status: host/body contract
Scope: C4 Nursery Android sandbox

## Ownership

C4 owns its avatar/body decisions.

The user does NOT directly invoke C4 motor verbs from the Home UI.

Valid flow:

C4 ACTION_REQUEST
-> Android affordance/execution check
-> sandbox mutation if executable
-> ACTION_RECEIPT
-> C4

The host may visualize the verified outcome only after executionSuccess=true.

ACTION_REQUEST != VERIFIED_OUTCOME.

## User role

The user is another actor in the environment.

Allowed user-originated interactions include:
- touch/contact with the avatar;
- call/attention event;
- pointing at an environment object;
- presenting files/images/audio/video through source/sensory lanes;
- starting a sandbox challenge.

These are USER_WORLD observations/events. They are not C4 motor actions.

USER_WORLD_EVENT != C4_ACTION.

## Host motor vocabulary V1

Object actions:
- LOOK
- TAKE / GRASP
- PLACE / RELEASE
- MOVE (currently bounded to supported sandbox affordances)

Body actions:
- WAVE
- NOD
- LOOK_AROUND
- STEP_LEFT
- STEP_RIGHT
- IDLE

Unsupported verbs are rejected with ACTION_NOT_ALLOWED.

## Visual rule

Avatar animation is an effect projection of a verified native receipt.
A UI animation must never manufacture an ACTION_REQUEST or count as evidence that C4 intended the action.

ANIMATION != INTENTION.
ANIMATION != ACTION_REQUEST.
RECEIPT != CAUSAL PROOF beyond the bounded sandbox execution.

## Environment/task lane

A user may create a challenge, but solving it belongs to C4.

USER -> WORLD_TASK
C4 -> ACTION_REQUEST*
HOST -> ACTION_RECEIPT*
HOST -> bounded task verification

If the installed runtime does not expose WORLD_TASK or WORLD_EVENT, the host reports RUNTIME_CAPABILITY_UNAVAILABLE rather than silently converting the task into C4 behavior.
