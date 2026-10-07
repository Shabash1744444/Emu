# C4 CINEMATIC CHAT PRESENCE V1

Date: 2026-10-07
Status: UI/presentation contract

## Purpose

Make Dialogue the primary living interaction surface without inventing organism state.

The chat presence header may display only:
- runtime RUNNING / STOPPED state;
- body-manifest handshake state;
- the last real C4 REPLY / ASK / PUBLISH text;
- real sensory/tool availability.

It must not synthesize:
- typing indicators;
- fake thinking state;
- emotion;
- urgency;
- importance;
- hidden chain-of-thought.

UI PRESENCE != COGNITION
ANIMATION != THINKING
ASK STYLE != URGENCY
PUBLISH STYLE != IMPORTANCE

## Timeline

All real C4 events remain visible.
ASK and PUBLISH may receive distinct presentation styles but are not filtered, merged or promoted semantically.

## Composer

- keyboard-safe;
- preserves chat reader position;
- incoming events do not force-scroll while composing;
- sensory tools remain reachable but visually subordinate to conversation.

## Keyboard mode

When the soft keyboard is open:
- presence/gate chrome collapses;
- sensory chrome hides;
- conversation + composer take priority.

No runtime or event is paused by UI compaction.
