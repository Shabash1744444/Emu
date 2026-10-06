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
