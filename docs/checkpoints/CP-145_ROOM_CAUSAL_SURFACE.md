# CP-145 — ROOM AS A CAUSAL SURFACE

Date: 2026-10-06

Purpose:
Move Nursery from a dashboard with a decorative avatar toward a persistent place where C4 can perceive and participate.

Implemented:
- Home evolved into a richer local room scene while remaining asset-light/procedural.
- Room contains environmental surfaces (window, floor, desk, lamp, plant, rug) and the existing procedural body.
- CALL emits typed ROOM_INTERACTION through the same runtime transport used by chat.
- Ball interaction now emits a causal MOVE/BALL event with from/to state instead of being only an animation.
- Room interaction is committed to the journal before runtime dispatch.
- No fake C4 reaction is generated when runtime is absent; UI explicitly says the interaction can be heard after C4 starts.
- Room remains generation-agnostic: no G208-specific behavior or weights.

Design research:
Borrow principles, not code/assets: unified persistent world across surfaces; procedural lightweight body; behavior/runtime separated from rendering. Do not copy unlicensed repository assets.

Next:
- world-object registry and inspect/use affordances;
- body pose/event contract driven by real C4 output;
- room state persistence/replay;
- later sandbox/mini-games as additional causal surfaces.
