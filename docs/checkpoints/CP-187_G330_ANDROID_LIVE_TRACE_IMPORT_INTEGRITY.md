# CP-187 — G330 ANDROID IMPORT / TRACE INTEGRITY — EXPERIMENTAL BUILD GREEN
Date: 2026-10-08. Not canonical. C4 core cognitive analysis remains RED.

## Grounded real-device observations from user export
- `C4_NURSERY_TRAINING_BUNDLE_V3`, timestamp 1791469053197.
- `DIGEST_COLLISION_SIZE_MISMATCH` on `C4_G329_ANDROID_CLEAN_ORGANISM.c4m` import; did not become selected clean organism.
- Live `TRACE_CONFIG` DEEP accepted, 46 cognitive records.
- 51,243,387-byte native transport trace was not exported: `TRACE_TOO_LARGE` at 16,777,216-byte read gate.
- User-visible C4 chat events had `eventId:null`, whereas runtime trace used `event_id`; join integrity lost.

## Repairs implemented in MainActivity.java (this branch only)
1. Do not put a mutable working checkpoint at `organisms/store/<sha256>.c4m`: verify the existing immutable store object's full SHA (not merely length) on every import, archive an existing mismatched legacy mutable object under `organisms/recovered` and restore the true imported original; create a unique working copy under `organisms/working`; use the working copy as `organism_private_path` for future checkpoint saves. Deny import during an active runtime session. Old copies are not silently deleted.
2. During `dispatchPyEvents`, normalize `event_id` to `eventId` in outgoing JSON, preserving the Python event reference through Android to the UI/conversation exporter.
3. For transport JSONL larger than 16 MiB, export the last complete-line-aligned 16 MiB with a leading `TRANSPORT_EXPORT_TRUNCATED` marker and original file size instead of only `TRACE_TOO_LARGE`. The full on-device log is left intact. This is still a partial export; a later separate raw archive/export mechanism is needed for full history.

## CI evidence
- First two patch attempts failed CI due Java syntax/scope and an unimported exception class; errors reproduced in GitHub Actions and repaired. These failures are part of the audit, not concealed.
- Final commit `41c83738c01609dedc77918aa5556aeaf51de285`.
- GitHub Actions run #37793496076 **SUCCESS**.
- Artifact id `11557516625`: `C4-Nursery-0.64.3-trace-ru`, 49,417,001-byte Actions artifact archive.
- Physical phone test not performed with patched APK, and no claim it solves C4 semantic reasoning.

## Independent core RED evidence
- In C4/G329 runtime, `episodic_memory.py:answer_batch` mechanically emits a generic refusal for every non-memory question. This is responsible for 13 boilerplate refusals in 19 question spans in the live export.
- Incorrect recall: USER-authored exam interrogative is returned in response to a request for C4's own prior ASK.
- Core negative controls: 3/3 tests FAIL (as expected) under G329 source, with different entities and no hardcoded answers.
- Core source audit and red regression: `Shabash1744444/-`, branch `experiments/c4-g330-device-red-cascade`.
- Don't promote C4/G329 and do not request another live test until structured same-message event inference and role-authoritative query resolution pass old and new suites.

## Next necessary cascade gates
- Verify working snapshots survive restart/re-import and archive recovers old state.
- Trace exact input event IDs and graph deltas across EVAL/COMMIT/DRIVE/MEDIATE.
- Android trace export must retain error/truncation provenance, never fabricate complete transport history.
- Finish C4 core structural scene/frame reasoning; never replace the generic refusal with named-entity-specific answer keys.
