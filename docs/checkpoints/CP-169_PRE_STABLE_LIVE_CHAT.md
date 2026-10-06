# CP-169 — PRE STABLE LIVE CHAT

Date: 2026-10-07
Parent: CP-168 organism picker hotfix GREEN
Status: PRE

Physical device result:
- current compatible runtime + organism boots successfully: C4 RUNNING.
- autonomous ASK events are visibly arriving.
- chat UX is unstable while those events arrive: the whole UI rerenders, the message feed is forced to bottom, the composer is displaced by the sensor stack/navigation, and typing becomes impractical.

Root causes in host UI:
1. Every persisted runtime event calls full render(), rebuilding Library/Room/Lab/Chat.
2. render() always forces msgs.scrollTop = msgs.scrollHeight.
3. Chat page is sized with a fixed 100vh formula while Android WebView keyboard/visual viewport changes.
4. Composer is after the full sensory stack, so chat-first interaction is not actually prioritized.

Repair:
- isolate conversation rendering from full application rendering;
- incoming C4 events use chat-only render path;
- preserve reader scroll and never steal position while the composer is focused;
- unread/new-message badge instead of forced autoscroll;
- user-send explicitly follows the new message;
- dynamic visualViewport height + keyboard mode;
- composer is ordered directly below the message feed;
- sensory detail becomes secondary/collapsible;
- keep every real C4 event; no fake reply and no suppression of organism cognition.

No C4 cognitive law or checkpoint data is changed.
