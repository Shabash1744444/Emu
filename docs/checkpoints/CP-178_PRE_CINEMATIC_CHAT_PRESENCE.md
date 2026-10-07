# CP-178 — PRE CINEMATIC CHAT PRESENCE

Date: 2026-10-07
Parent: CP-177 Cinematic 3D Home GREEN
Status: PRE

Goal:
Make Dialogue feel like the primary living interaction surface rather than a runtime/debug console.

Scope:
- compact living C4 presence header;
- preserve honest RUNNING / STOPPED / manifest state;
- visually distinguish REPLY / ASK / PUBLISH without suppressing events;
- reduce engineering chrome while keeping diagnostics reachable;
- make sensory controls compact and immediately reachable;
- stronger glass composer and keyboard-safe layout;
- no forced scroll regressions;
- no fake avatar emotions / activity / typing indicators.

Boundaries:
UI PRESENCE != COGNITION
ANIMATION != THINKING
PUBLISH STYLE != IMPORTANCE
ASK STYLE != URGENCY
NO SYNTHETIC TYPING INDICATOR

Target release:
0.58-cinematic-chat
