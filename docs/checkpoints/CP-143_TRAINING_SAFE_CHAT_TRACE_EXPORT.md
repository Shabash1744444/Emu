# CP-143 — TRAINING-SAFE CHAT + TRACE EXPORT

Date: 2026-10-06

Goal:
Make real C4 conversations exportable for later training/review without contaminating dialogue data with UI/runtime diagnostics.

Implemented:
- System page gets "Выгрузить chat + logs".
- Native Android bridge writes a private export file, fsyncs it, and shares it through FileProvider/content URI with temporary read permission.
- Bundle format: C4_NURSERY_TRAINING_BUNDLE_V1.
- conversation lane contains accepted USER_MESSAGE plus real C4 REPLY/ASK only.
- trace lane contains app/runtime diagnostic events and is explicitly trainingEligible=false.
- imported sources/attachments are excluded from conversation by default.
- manifest captures organism SHA/size/validation state and runtime/session/protocol identity when available.
- requestId/eventId/timestamps are retained for causal replay and debugging.
- no diagnostic STATUS/ERROR/sandbox/UI event is silently converted into training dialogue.

Reason:
A readable transcript alone is insufficient for trustworthy continual training. The exported artifact must preserve what was actual dialogue versus host diagnostics and which organism/runtime produced it.

Next:
- verify Android build after FileProvider/AndroidX addition;
- add append-only native transport trace once executable runtime adapter exists;
- optionally add user review/approval flags before feeding exported turns back into training.
