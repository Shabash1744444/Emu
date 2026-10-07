# C4 CINEMATIC HOME 3D V1

Date: 2026-10-07
Status: renderer/presentation contract

## Purpose

Give the VRM body a real lightweight 3D habitat rather than a flat CSS stage.

Three.js environment contains:
- floor and walls;
- window / skyline glow;
- bed;
- desk;
- monitor;
- shelves/books;
- rug;
- holographic orb;
- bounded lights / fog / contact shadows.

Native room state remains authoritative.

## Verified world projection

BALL / BLOCK / BOOK positions are derived only from S.room objects that were themselves updated from native verified room receipts.

RENDERER PROP != NATIVE WORLD STATE
3D ROOM != WORLD EVIDENCE
VISUAL POSITION != NEW OBSERVATION

Renderer updateWorld() may project:
- roomObjects;
- heldObject.

It cannot mutate native state.

## Presentation motion

Allowed presentation-only motion:
- tiny camera drift;
- holographic orb float;
- monitor emissive breathing;
- shadow/light presentation.

CAMERA PRESENTATION != C4 ATTENTION
AMBIENCE != EMOTION
LIGHTING != WORLD FACT

## Fallback

VRM 3D room -> existing CSS Living Home fallback.
