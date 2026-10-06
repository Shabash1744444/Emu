# CP-129 — ORGANISM MANAGER SOCKET

Purpose: prepare real network/organism selection without pretending state == runtime.

Neighbor-branch facts used:
- canonical .c4m is organism state, not executable runtime;
- latest observed canonical size ~125,922 bytes;
- laws/runtime remain external;
- late G77-G96 work is not yet fully merged into one canonical release.

Implemented:
- Android system picker for organism file;
- persistent URI grant where provider supports it;
- background SHA-256 and size identity;
- 64 MiB safety ceiling for organism picker;
- persistent selected organism registry across restart;
- clear/disconnect action;
- non-.c4m selection rejected;
- System UI separates Organism from Runtime;
- selected .c4m may become STATE READY;
- Runtime remains NOT INSTALLED and c4Transport remains false;
- no selected file can make frontend synthesize AI output.

Current validation limitation:
- exact .c4m manifest/schema parser is NOT implemented because current canonical format/runtime handoff is not yet frozen.
- current format probe is extension + bounded identity only; UI must not claim runtime compatibility from it.

Next:
build gate; then add exact compatibility parser when canonical handoff lands, followed by actual runtime loader/service.
