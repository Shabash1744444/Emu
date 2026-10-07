# C4 CHARACTER PRESENCE V2

Date: 2026-10-07
Status: renderer presentation contract

## Purpose

Give the VRM body physically natural idle presence without inventing C4 psychology.

Presentation-only behavior:
- irregular blink cadence;
- tiny forward gaze drift;
- breathing through chest/spine/shoulders;
- slow bounded weight transfer;
- tiny neck/head micro-motion;
- smoother amplitude-driven vocal mouth envelope;
- VRM spring bones continue through normal vrm.update().

## Priority

Verified motor actions override idle presentation.

IDLE PRESENTATION < VERIFIED MOTOR RECEIPT

LOOK / LOOK_AROUND / TAKE / PLACE / WAVE / NOD / STEP etc. keep their existing receipt-driven semantics.

## Boundaries

IDLE MICRO-MOTION != C4 ACTION
GAZE DRIFT != ATTENTION
BLINK != EMOTION
POSTURE != INTERNAL STATE
MOUTH MOTION != LANGUAGE
SPRING PHYSICS != INTENTION

No emotion, mood, curiosity or cognitive state is inferred from presentation motion.

## Vocal projection

VRM mouth uses:
- actuator duration
- actuator amplitude
- actuator f0 only to vary visual cadence slightly

It does not decode phonemes or words.
