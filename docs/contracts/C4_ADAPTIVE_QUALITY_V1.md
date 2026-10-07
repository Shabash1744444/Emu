# C4 ADAPTIVE QUALITY V1

Date: 2026-10-07
Status: renderer policy contract

## Purpose

Adapt the visual renderer to mobile thermal/power conditions without changing C4 cognition.

Modes:
- HIGH
- BALANCED
- ECO
- AUTO

## Renderer profiles

HIGH:
- DPR <= 2.0
- target 60 FPS
- dynamic shadows
- 1024 shadow map

BALANCED:
- DPR <= 1.35
- target 45 FPS
- dynamic shadows
- 512 shadow map

ECO:
- DPR <= 0.9
- target 30 FPS
- dynamic shadows disabled
- camera ambience drift disabled

AUTO:
- normally BALANCED;
- power-save or thermal >= SEVERE -> ECO;
- thermal >= CRITICAL -> ECO regardless of requested mode.

## Hard boundary

GRAPHICS QUALITY != COGNITION QUALITY
THERMAL DOWNSHIFT != RUNTIME DOWNSHIFT

Adaptive quality must never:
- pause runtime ticks;
- stop chat;
- stop sensory services;
- rewrite C4 state;
- drop verified motor receipts;
- change source ingestion semantics.

It only changes Three.js renderer presentation cost.

## Telemetry

Android exposes:
- requested mode
- effective mode
- thermal status/name when API supports it
- power-save flag
- rendererOnly=true
- runtimeThrottle=false
