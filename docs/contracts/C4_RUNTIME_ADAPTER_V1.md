# C4 RUNTIME ADAPTER V1

Narrow Android/runtime boundary. This is an ABI contract, not an implementation of cognition.

## Commands accepted from host
- OPEN_SESSION {organismPath, organismSha, requestedTransport:"C4_APP_TRANSPORT_V1"}
- CLOSE_SESSION {sessionId, checkpointPolicy}
- USER_MESSAGE {sessionId,eventId,text,metadata,evidenceEnvelope}
- BEGIN_SOURCE {sessionId,eventId,sourceId,mime,size,evidenceEnvelope}
- APPEND_SOURCE {sessionId,eventId,sourceId,offset,bytes}
- END_SOURCE {sessionId,eventId,sourceId,digest}
- TICK {sessionId,count}
- ACTION_RECEIPT {sessionId,requestId,receipt,evidenceEnvelope}
- SENSORY_SESSION_START / FRAME / STOP
- CHECKPOINT {sessionId,reason}

Unknown command types are rejected. No arbitrary method/class/file invocation.

## Runtime handshake
OPEN_SESSION must return/emit:
- runtimeId + buildId/checkpoint id;
- runtime ABI;
- supported organism schema range;
- transport protocol version;
- body/action ABI;
- checkpoint ABI;
- organism manifest identity/digest;
- sessionId;
- capabilities.

Host enables c4Transport only after all required ABI/schema/digest checks pass and session state is RUNNING.

## Events accepted from runtime
Allowlist:
REPLY, ASK, PUBLISH, STATUS, ERROR, ACTION_REQUEST, SOURCE_PROGRESS, CHECKPOINT_COMMITTED.

G207 epistemic status values must remain distinct when surfaced:
DERIVED, UNKNOWN, CONFLICT, QUARANTINED, NEEDS_CHALLENGE, NEEDS_REVALIDATION.
The app must not collapse them to true/false or "learned".

## Ownership
Runtime owns cognition and organism mutation.
Host owns Android permissions, durable source spool, body/sensor execution and transport.
Environment owns physical/sandbox outcome receipts.
UI owns presentation only.

## Recovery
Process death invalidates RUNNING session ownership. Host restarts STOPPED/RECOVERY; it never auto-replays unfinished ACTION_REQUEST or resumes screen capture.

## Source ingestion state machine
A source crosses explicit states; none imply the next:

`CAPTURED -> STORED -> INGESTING -> INGESTED`

Semantic/epistemic interpretation is outside this host state machine:

`INGESTED != LEARNED != ACCEPTED_AS_TRUE`

Rules:
- Android may emit/store a source only after durable spool commit and digest identity.
- BEGIN_SOURCE references the immutable stored sourceId/digest and declares metadata/evidence envelope.
- APPEND_SOURCE offsets must be monotonic for that ingestion session; runtime may reject/resume explicitly.
- END_SOURCE carries the expected digest. Runtime must verify completion before SOURCE_PROGRESS can report an INGESTED terminal phase.
- SOURCE_PROGRESS is runtime-owned and must include sourceId plus phase/progress sufficient to correlate with the stored source.
- UI may show STORED from host receipts, but may show INGESTING/INGESTED only from runtime events.
- CHECKPOINT_COMMITTED is not proof that any particular source was learned or believed.
- imported/replayed/self-generated material cannot gain independent-evidence status merely by ingestion.

## Trace symmetry
For every transport command/event, host trace should retain direction, type, session/request/event identity, organism identity and timestamp. Command acceptance, command result and runtime event are separate facts. Absence of an event must not be synthesized into success.


## Sensory feature boundary — V1 host cortex

The Android host may reduce raw sensor bandwidth before transport, but the reduction must remain non-semantic.

Current host feature schema: `C4_SENSORY_FEATURES_V1`.

AUDIO V1:
- PCM16 mono physical frames;
- sample rate/count/duration;
- RMS / mean absolute amplitude / peak;
- zero-crossing rate;
- fixed-frequency spectral probes and probe centroid.

VISION V1:
- source/timestamp;
- input dimensions;
- 12x8 RGB+luma retinal lattice;
- mean luma / luma variance / local edge-change measure.

Forbidden in this layer:
- object/category labels;
- ASR transcript presented as observation;
- emotion/intent/scene labels;
- hidden LLM/VLM inference;
- promotion of a host feature to learned/true state.

`SENSORY_SESSION_START / SENSORY_FRAME / SENSORY_SESSION_STOP` may be rejected with `RUNTIME_CAPABILITY_UNAVAILABLE` when the installed C4 runtime does not yet expose the sensory ABI. The host must show that honestly rather than synthesize perception.

SIGNAL != SOURCE. CAPTURED != PERCEIVED. PERCEIVED != LEARNED. FEATURE != CONCEPT.


## Android binary chunk envelope

The WebView/Android/Python JSON boundary may carry an APPEND_SOURCE chunk as:
- `encoding: "base64"`
- `bytes: "<base64>"`
- monotonic `offset`

This is a transport encoding only. Before calling a concrete Python runtime `append_source` / `source_append` method, the host adapter decodes the payload back to raw bytes and removes the transport-only `encoding` field.

Base64 text is never semantic source content and must never be stored as the source itself.

## Foreground organism continuity

When a session reaches RUNNING, Android may keep the local runtime alive with a foreground service. The service:
- owns autonomous TICK cadence while the Activity is backgrounded;
- serializes Python calls through the same process-wide gate as the Activity;
- checkpoints after autonomous emissions and periodically;
- persists real runtime events to a durable pending inbox when no UI is visible;
- may surface actual ASK/PUBLISH events as Android notifications.

Foreground continuity does not authorize auto-resuming a dead-process physical action or sensory session. After process death, stale heartbeat -> STOPPED/RECOVERY remains the rule.
