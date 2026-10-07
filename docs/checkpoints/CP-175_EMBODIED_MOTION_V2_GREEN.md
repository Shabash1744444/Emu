# CP-175 — EMBODIED MOTION V2 GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 5052bfc1b5c533114624d6859ab0396fad07fa3e

## Goal

Make the VRM body behave like one coherent verified body instead of isolated pose impulses.

## Implemented

- full verified ACTION_RECEIPT context reaches VRM motor rendering;
- bounded visual motor queue (max 8);
- later verified receipts no longer destructively overwrite the current gesture;
- queue is renderer-only and is never persisted as cognition or planning;
- locomotion uses pelvis/chest counter-motion, arm swing, knees/feet and verified native body x;
- target-aware reach/gaze uses verified room location context;
- right-hand finger articulation for verified grasp/release;
- verified BALL / BOOK / BLOCK proxy attaches to the right hand;
- ground plane + soft contact shadow grounding;
- renderer telemetry: VRM version, bone count, spring state, current action, queue, held object;
- restart synchronization restores only verified x and held object;
- unfinished visual motions do not resume after process death;
- Android capability reports EMBODIED_MOTION_V2.

## Boundaries

ANIMATION QUEUE != COGNITIVE PLAN
HAND POSE != INTENTION
GAZE POSE != ATTENTION CLAIM
RENDERED PROP != NEW WORLD EVIDENCE
ACTION_REQUEST != VERIFIED OUTCOME

Only executionSuccess=true native receipts may create semantic motor motion.

## Build

GitHub Actions run #369: SUCCESS

Artifact:
- name: C4-Nursery-0.55-embodied-motion-v2
- artifact ID: 11484444114
- ZIP bytes: 48,147,872
- ZIP SHA256: 76cc9aa4e2a99b0b7889598884873b5706e12f1e46af2576ed4850881b15bee1

APK:
- bytes: 48,147,439
- SHA256: 03723ed74d0d187f5e7473eee9fca1f6d1464cfe5fc6adccc8ea017d95707e63
- unzip integrity: PASS

VRM bundle:
- SHA256: e69755c3527736a2b7e1f4a0e87a1dc29e968927ff6f9615124b5ab88698f99a

## Physical Android gate

Still required:
- verify finger bend axes on default VRoid body;
- verify held-object scale/offset;
- verify step sign/direction;
- verify shadow cost and thermal behavior;
- verify touch regions against actual 3D framing.
