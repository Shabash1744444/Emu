# CP-156 — INTERACTIVE LUMINOUS SCENE + CHAT POLISH
Date: 2026-10-06

Implemented:
- BALL, BLOCK and BOOK are scene objects projected from room state.
- scene object location follows native location: floor-left/right, shelf, desk, basket, held.
- held objects disappear from the room projection and remain represented at C4 body.
- tapping a free portable scene object requests native GRASP.
- while holding, shelf/desk/basket/floor become luminous release targets.
- tapping target requests native RELEASE; floor target resolves left/right from tap position.
- no scene click directly mutates world state.
- chat surface brought into the same luminous/glass visual system without introducing fake replies or cognition.

Build gates:
- #167 SUCCESS interactive native-projected room.
- #168 SUCCESS chat visual pass.

Next:
Polish sensory/library surfaces, then reduce/remove redundant debug-like room controls now that the scene itself is the primary interaction surface.
