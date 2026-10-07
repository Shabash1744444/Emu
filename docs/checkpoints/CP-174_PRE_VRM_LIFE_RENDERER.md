# CP-174 — PRE VRM LIFE RENDERER

Date: 2026-10-07
Parent: CP-173 Rigged GLB Body GREEN
Status: PRE

Physical binary inspection of the bundled default:
- VRoid_Sample_D.glb has 144 nodes, 3 skins, 3 meshes and VRM extension.
- It has 0 embedded animation clips.

Goal:
Make the real humanoid rig live without depending on baked clips.

Renderer:
- Three.js 0.180.0
- @pixiv/three-vrm 3.5.5
- esbuild 0.28.2 pinned and bundled in CI
- no runtime CDN.

Capabilities:
- load VRM0/VRM1 metadata from .vrm or VRM-extended .glb;
- normalized humanoid bone access;
- procedural idle/breathing;
- automatic neutral blink;
- look-at target;
- receipt-driven WAVE / NOD / LOOK_AROUND / STEP / REACH bone motion;
- spring bones update through vrm.update(delta);
- no semantic emotions are synthesized.

Fallback:
VRM life renderer -> model-viewer GLB -> photo avatar -> CSS debug body.

Hard boundary:
BLINK/BREATH = visual embodiment process, not claimed emotion.
PROCEDURAL MOTOR POSE is only started after verified C4 motor receipt.
USER STILL DOES NOT PUPPET C4.

Target release:
0.54-vrm-life
