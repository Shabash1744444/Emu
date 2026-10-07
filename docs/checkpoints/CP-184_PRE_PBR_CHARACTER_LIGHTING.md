# CP-184 — PRE PBR CHARACTER LIGHTING

Date: 2026-10-07
Parent: CP-183 Character Presence V2 GREEN
Status: PRE

Goal:
Improve real 3D material/character rendering quality using bundled offline image-based lighting.

Planned:
- bundle Poly Haven Studio Small 09 1K HDRI;
- CC0 provenance stored in repo;
- RGBELoader + PMREMGenerator;
- scene.environment from local appassets HDRI;
- keep cinematic key/rim/fill lights;
- quality modes control reflection/light cost where useful;
- no network required at runtime.

Boundaries:
LIGHTING != WORLD OBSERVATION
HDRI != C4 VISION
RENDER REFLECTION != EVIDENCE
LIGHTING PRESET != EMOTION

Target release:
0.64-pbr-lighting
