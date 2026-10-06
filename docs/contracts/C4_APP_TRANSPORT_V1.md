# C4 APP TRANSPORT CONTRACT v1

Status: app-side integration contract. This file does not claim that the trainable core is embedded yet.

## Runtime nature
C4 is a living event-driven organism, not request/response inference.

## App -> C4 commands
All commands carry `requestId`, monotonic app timestamp, and provenance.

- `USER_MESSAGE {requestId, text, sourceId}`
- `BEGIN_SOURCE {requestId, sourceId, sourceKind, mime, declaredBytes?}`
- `APPEND_SOURCE {requestId, sourceId, offset, bytesRef, final:false}`
- `END_SOURCE {requestId, sourceId, finalOffset, digest?}`
- `TICK {requestId, budget}`
- `ACTION_RECEIPT {requestId, actionRequestId, environment, success, outcomeRef}`
- `SENSORY_SESSION_START {requestId, sessionId, modality, provenance}`
- `SENSORY_FRAME {sessionId, sequence, capturedAt, payloadRef}`
- `SENSORY_SESSION_STOP {requestId, sessionId, frameCount}`

A sensory session is one provenance root. Frames are samples, not independent evidence.

## C4 -> App events
- `REPLY {eventId, text, causedBy?}`
- `ASK {eventId, text, causedBy?}`
- `PUBLISH {eventId, payload, causedBy?}`
- `STATUS {eventId, runtimeState}`
- `ACTION_REQUEST {eventId, actionRequestId, action, params}`
- `SOURCE_PROGRESS {eventId, sourceId, acceptedOffset}`
- `ERROR {eventId, code, recoverable}`

The frontend MUST NOT synthesize any of these events.

## Persistence
Transport delivery acknowledgement is not cognitive evidence.
UI may mark a command as locally queued/delivered, but competence/learning changes require C4-owned state plus appropriate environment receipts.

## Physical world
ACTION_REQUEST -> environment executes -> ACTION_RECEIPT.
Never award physical competence at request time.

## Source streaming
Chunk boundaries are transport boundaries only.
Repeated/retried chunks from the same sourceId+offset must be idempotent and must not multiply evidence.

## Capability gate
Until an actual named C4 build exposes this contract, Android reports `c4Transport=false`.
