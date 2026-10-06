# CP-169 — STABLE LIVE CHAT GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 34b2cccba0d0633078cb3f8016751e149f09432a

Physical device evidence before repair:
- compatible runtime + current organism reached C4 RUNNING;
- autonomous ASK events were visibly emitted;
- repeated ASK events made the chat viewport jump and displaced the composer.

Verified host causes:
- full application render() on each persisted chat event;
- unconditional force-scroll to the bottom;
- fixed 100vh assumptions in Android WebView;
- sensory chrome ordered ahead of the primary text composer.

Repairs:
- isolated renderConversation() from full render();
- C4 REPLY/ASK/PUBLISH -> chat-incoming render mode;
- USER_MESSAGE -> chat-bottom render mode;
- scroll remains anchored while typing/reading;
- unread badge replaces forced autoscroll;
- visualViewport controls dynamic height and keyboard mode;
- keyboard hides nonessential nav/sensor chrome;
- composer ordered immediately after the message feed;
- sensory details collapsed by default.

Important semantic boundary:
- no organism event is deleted, hidden from state, coalesced into fake semantics, or prevented from occurring;
- this is presentation/backpressure UX only, not a C4 cognitive-law change.

Release:
- versionCode 49
- versionName 0.49-stable-live-chat
- GitHub Actions run #303 SUCCESS
- artifact ID 11442428033
- artifact ZIP 33,816,613 bytes
- artifact ZIP SHA256 495e55dbdde99d4dcc0a108c8c23263f59b779571eecdc836d0e23bf3ae97bb3
- APK 33,816,186 bytes
- APK SHA256 deaa05dab40505982aa62b27c75f5ebce55f3eebdb4022fa229c417b5847e083

Gates:
- WebView JavaScript syntax PASS
- selector misuse lint PASS
- organism picker regression lint PASS
- stable-chat forced-scroll guard PASS
- Python py_compile PASS
- Gradle assembleDebug PASS
- APK archive integrity PASS

Separate observation for core work:
G266 is currently emitting a series of unresolved g223-world ASK events. That behavior is preserved for analysis; CP169 only makes the UI resilient to it.
