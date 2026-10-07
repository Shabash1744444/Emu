# CP-186 — CHAT MULTI-SELECTION GREEN

Date: 2026-10-07
Status: GREEN
Release: 0.64.1-chat-select
versionCode: 66
Binary workflow head: d8b6397272d21c022aee01d3b2a3d8edc1072c38
GitHub Actions run: #472
Run ID: 37664305742

## Goal

Make Dialogue support Telegram-style selective copy without mutating C4 state.

## Implemented

- long press on user / C4 / system message enters selection mode;
- regular taps toggle additional selected messages;
- fixed Telegram-like action bar shows selected count;
- cancel exits selection mode without touching conversation state;
- copy writes selected messages to Android clipboard;
- one selected message copies exact text only;
- multiple selected messages copy in chronological order with speaker label + local time + exact text;
- supported speaker labels:
  - ТЫ
  - C4
  - C4 · ВОПРОС
  - C4 · ИНИЦИАТИВА
  - СИСТЕМА
- selected bubbles get an explicit check mark and highlight;
- incoming messages do not auto-scroll while selection mode is active;
- composer / sensory controls are visually subdued and non-interactive during selection;
- native Android ClipboardManager bridge is used when available;
- WebView textarea copy remains fallback;
- fine-pointer devices retain one-message copy affordance;
- coarse-pointer/mobile UI relies primarily on long press to avoid clutter.

## Regression caught during implementation

The first CP186 UI commit used:
  $('#msgs .msg.selected').forEach(...)

The existing UI contract guard correctly rejected it because $() returns one element.

An attempted literal replacement also collapsed $$ back to $ because JavaScript String.replace replacement strings interpret $$ as one literal $.

Final repair used callback replacement so the source physically contains:
  $$('#msgs .msg.selected').forEach(...)

Final UI guard:
- UI CONTRACT PASS: 164 DOM ids / 50 critical bindings
- LAYOUT CONTRACT PASS: 164 unique ids / 5 pages / 5 nav targets

## Boundaries

MESSAGE SELECTION != MESSAGE MUTATION
COPY != C4 EVENT
COPY != C4 OBSERVATION
CLIPBOARD != MEMORY

CI rejects selection code that routes through:
- runtimeSend
- commit
- transact
- ACTION_RECEIPT

## Build

GitHub Actions run #472: SUCCESS

Artifact:
- C4-Nursery-0.64.1-chat-select
- artifact ID: 11501764313
- artifact ZIP bytes: 49,396,666
- artifact ZIP SHA256: 4e7878d54dac068123ad454ca0e4ad0ba2c10ce8285e4ddf8806563be9d82940

APK:
- bytes: 49,396,248
- SHA256: 03c80b47fd271b5bbb0d0747a680fefec77da63d594012c1b7cb1a13f07fe001
- unzip integrity: PASS
- local re-extraction verification: PASS

## Physical Android gate

Still required on target phone:
- long-press latency/feel;
- selecting own + C4 messages together;
- deselect by tap;
- copy 1 message;
- copy multiple messages;
- clipboard contents in Telegram/Notes;
- keyboard open/closed during selection;
- incoming C4 message while selection mode is active;
- system-message selection if current runtime emits role=system messages.
