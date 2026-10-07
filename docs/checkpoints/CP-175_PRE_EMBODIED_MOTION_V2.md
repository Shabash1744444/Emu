# CP-175 — PRE EMBODIED MOTION V2

Date: 2026-10-07
Parent: CP-174 VRM Life GREEN
Status: PRE

Goal:
Turn the working VRM humanoid renderer into a coherent embodied motion system rather than isolated pose impulses.

Scope:
- receipt-aware motor queue;
- target-aware gaze and reach context;
- persistent hand/grasp state after verified TAKE/GRASP and RELEASE/PLACE;
- finger articulation for grasp/release;
- better locomotion with root translation, pelvis/chest counter-motion and arm swing;
- small 3D habitat grounding plane/contact visual so the body is spatially anchored;
- verified held-object proxy attached to the hand;
- truthful renderer telemetry (rig/expressions/spring/current action/queue);
- no user puppeteering and no fabricated emotion.

Boundary:
ACTION_REQUEST -> native execution -> executionSuccess=true receipt -> motor queue -> visual embodiment

RENDERED PROP != NEW WORLD EVIDENCE
GAZE POSE != ATTENTION CLAIM
HAND POSE != INTENTION
ANIMATION QUEUE != COGNITIVE PLAN

Target release:
0.55-embodied-motion-v2
