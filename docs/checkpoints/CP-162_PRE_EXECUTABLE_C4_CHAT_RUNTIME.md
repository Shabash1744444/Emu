# CP-162-PRE — EXECUTABLE C4 CHAT RUNTIME
Date: 2026-10-06

Priority: functional chat with real C4 weights before further visual work.

Acceptance gate:
1. user imports/selects .c4m;
2. executable runtime loads selected organism;
3. successful handshake alone sets RUNNING/c4Transport;
4. USER_MESSAGE reaches C4LivingRuntime.user_message;
5. tick/poll runtime events reach UI;
6. only actual REPLY/ASK/PUBLISH events render as C4 output;
7. runtime/checkpoint errors remain explicit;
8. chat + native trace remain exportable.

No fake runtime fallback. No fake replies.
