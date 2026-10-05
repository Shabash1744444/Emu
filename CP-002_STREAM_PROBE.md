# CP-002 — Stream/provenance probe
Date: 2026-10-05

Deterministic Node probe passed:
- 10,000 text fragments ingested under exactly one provenance source.
- Cursor reached 50,000 characters without message/context-window semantics.
- Freeze rejected mutation and preserved byte-identical serialized state during rejected ingest.
- New runtime instance restored FROZEN state and durable cursor.
- After resume, same source continued from cursor 50,000 to 50,006.

Note: runtime retains only a bounded recent event tail (500) as an inspection buffer; source cursor/provenance remains durable. This is deliberate separation of history inspection from logical stream length.

Next: package validation and release ZIP.
