# CP-186 — PRE TRACE RECORDER RU UX

Date: 2026-10-08
Parent: CP-185 Cognitive Trace Recorder GREEN
Status: PRE

Goal:
Make the diagnostic recorder understandable to a Russian-speaking user without changing the trace protocol.

Protocol values remain:
OFF / EVENTS / DECISIONS / DEEP
CONTINUOUS / NEXT_INTERACTION

UI must explain:
- what is always recorded;
- what requires runtime trace support;
- which mode to use for a normal UI/transport bug;
- which mode to use for a strange C4 decision;
- how to capture exactly one deep interaction;
- what Snapshot does;
- what Clear deletes;
- what Export contains.

No trace semantics or training policy changes.

Target release:
0.64.3-trace-ru
