# CP-120 — PERSISTED HOME + CHAT SURFACE

Implemented:
- interactive room with articulated avatar: 2 arms/hands + 2 legs;
- WAVE, MOVE_BALL, RESET_ROOM are real local world-state actions;
- each action appends a bounded event journal entry;
- authoritative state committed through NurseryNative before save indication;
- user chat messages are durable and bounded;
- frontend emits zero fake assistant/model messages;
- Experience page reports only factual local event/message counts;
- System page reports actual Android host/device info;
- bottom nav reduced to surfaces with implemented behavior;
- safe-area aware layout.

Device acceptance:
1. move ball and wave;
2. send a chat message;
3. kill process / remove app from recents;
4. reopen;
5. ball position, counters and chat history must restore.
Next: media capture/file ingestion and actual C4 event transport, preserving typed boundary.
