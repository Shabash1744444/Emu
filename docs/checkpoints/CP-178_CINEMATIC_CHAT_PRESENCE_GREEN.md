# CP-178 — CINEMATIC CHAT PRESENCE GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: e8fe8be7953819f6ce6e120ba1b360f0c8234c7a

## Implemented
- Dialogue now opens with a compact living C4 presence header;
- presence uses only real runtime state + last real REPLY / ASK / PUBLISH;
- no synthetic typing/thinking indicator;
- ASK and PUBLISH receive distinct presentation styling without suppression or semantic promotion;
- runtime bar is compact and startup gate disappears once RUNNING;
- sensory controls are a compact toolbar rather than a large debug grid;
- composer is visually primary, keyboard-safe, and preserves the stable-chat scroll rules;
- keyboard mode collapses nonessential presence/sensory chrome;
- shell/page transitions and bottom navigation were polished;
- Home jump from Dialogue added.

## Boundaries
UI PRESENCE != COGNITION
ANIMATION != THINKING
ASK STYLE != URGENCY
PUBLISH STYLE != IMPORTANCE

## Build
GitHub Actions run #404: SUCCESS

Artifact:
- C4-Nursery-0.58-cinematic-chat
- artifact ID: 11492446264
- ZIP bytes: 48,158,176
- ZIP SHA256: 70a388b647cb5d659e3dc5277977be55fc27000e55ee849c612fb14904e7b1a9

APK:
- bytes: 48,157,755
- SHA256: 1574da8a7bb9080b6231b1bfd6b3391e48743b51c99a654752b8623dea38e02b
- unzip integrity PASS

Physical gate:
- inspect message density and composer ergonomics on the user's exact phone;
- verify keyboard height behavior;
- verify ASK/PUBLISH styling with a live G266+ organism.
