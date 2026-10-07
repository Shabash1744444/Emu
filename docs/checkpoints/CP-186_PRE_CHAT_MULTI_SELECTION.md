# CP-186 — PRE CHAT MULTI-SELECTION

Date: 2026-10-07
Parent: CP-185 Layout Foundation V2 GREEN
Baseline: 0.64-layout-foundation
Status: PRE

Goal:
Make Dialogue behave like a normal mobile messenger for copying conversation fragments.

UX:
- long press any user / C4 / system message -> enter selection mode;
- tap additional messages -> toggle selection;
- fixed Telegram-like action bar with selected count;
- copy selected messages as one clipboard block in chronological order;
- cancel selection without touching conversation state;
- single-message quick copy remains available where appropriate.

Copy formatting:
- one selected message -> exact message text;
- multiple selected messages -> speaker label + local time + exact text.

Speaker labels:
- ТЫ
- C4
- C4 · ВОПРОС
- C4 · ИНИЦИАТИВА
- СИСТЕМА

Boundaries:
MESSAGE SELECTION != MESSAGE MUTATION
COPY != C4 EVENT
COPY != C4 OBSERVATION
CLIPBOARD != MEMORY

No runtime command, C4 state, evidence, or message ordering may change due to selection/copy.

Target release:
0.64.1-chat-select
