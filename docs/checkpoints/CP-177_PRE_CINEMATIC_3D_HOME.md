# CP-177 — PRE CINEMATIC 3D HOME

Date: 2026-10-07
Parent: CP-176 Parametric Motor Voice GREEN
Status: PRE

Goal:
Move the Living Home from a CSS-backed stage toward an actual lightweight 3D habitat around the VRM body.

Scope:
- real Three.js room geometry behind/around the avatar;
- grounded floor/back wall/window/bed/desk/shelves;
- emissive monitor + holographic orb;
- soft PBR materials and contact shadows;
- native-room BALL / BLOCK / BOOK visualized in 3D at their verified locations;
- renderer world sync from verified host room state;
- subtle presentation-only camera breathing;
- capability/body manifest surface in UI.

Boundaries:
3D ROOM != WORLD EVIDENCE
RENDERER PROP != NATIVE WORLD STATE
CAMERA PRESENTATION != C4 ATTENTION
VISUAL AMBIENCE != EMOTION

Native verified room state remains authoritative.
Renderer never mutates C4 world state.

Target release:
0.57-cinematic-home
