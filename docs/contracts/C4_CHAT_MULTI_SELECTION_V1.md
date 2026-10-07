# C4 CHAT MULTI-SELECTION V1

Date: 2026-10-07
Status: UI/clipboard contract
Parent: CP-185 Layout Foundation V2

## Purpose

Make Dialogue support Telegram-style selective copy without changing conversation semantics.

## Interaction

- Long press a user / C4 / system message to enter selection mode.
- Tap additional messages to toggle them.
- A fixed action bar shows selected count.
- Copy writes selected text to the Android clipboard.
- Cancel exits selection mode without mutating conversation data.

Single-message quick-copy may remain available on fine-pointer devices.

## Copy format

One selected message:
- exact message text only.

Multiple selected messages:
- speaker label;
- local message time when available;
- exact message text;
- blank line between messages.

Speaker labels:
- ТЫ
- C4
- C4 · ВОПРОС
- C4 · ИНИЦИАТИВА
- СИСТЕМА

## Stable selection identity

Selection keys are derived from:
- S.messages index;
- original message timestamp.

Selection state is UI-only and is not persisted into C4 state.

## Boundaries

MESSAGE SELECTION != MESSAGE MUTATION
COPY != C4 EVENT
COPY != C4 OBSERVATION
CLIPBOARD != MEMORY

Selection/copy code must not call:
- runtimeSend
- commit
- transact
- ACTION_RECEIPT paths

## Android bridge

Native ClipboardManager is preferred.

Fallback:
- hidden textarea + document.execCommand('copy') inside WebView.

Clipboard writes do not create runtime events.
