# CP-172 — PRE VISUAL AVATAR LAYER

Date: 2026-10-07
Parent: CP-171 Living Home GREEN
Status: PRE

User direction:
Replace the geometric/CSS avatar look with high-quality photorealistic-anime presentation and keep improving the app itself.

Scope:
- add a first-class visual-avatar asset lane;
- support user-selected PNG/JPG/WebP as a private Android avatar asset;
- show that asset as the primary C4 visual body in Home;
- keep the old CSS body only as a fallback/debug silhouette;
- bind verified C4 motor receipts to visual-body transforms/poses;
- add truthful avatar metadata (filename/hash/bytes), not fake emotions;
- prepare the contract for later VRM/GLB/rigged-body renderer.

Hard boundaries:
VISUAL_ASSET != COGNITION
AVATAR_ANIMATION != INTENTION
C4 ACTION_REQUEST -> HOST EXECUTION -> RECEIPT -> VISUAL PROJECTION
USER MAY CHOOSE APPEARANCE, BUT USER DOES NOT CONTROL C4 MOTOR ACTIONS

Target release:
0.52-visual-avatar
