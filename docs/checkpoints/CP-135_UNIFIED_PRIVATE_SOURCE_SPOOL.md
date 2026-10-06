# CP-135 — UNIFIED PRIVATE SOURCE SPOOL

Implemented:
- file/photo/audio durable discrete inputs copy into app-private sources/store;
- SHA-256 computed during bounded copy;
- fsync before promotion;
- content-addressed dedupe;
- SOURCE_IMPORTED contains sourceId, size, MIME, origin, phase;
- source import is explicitly independentEvidence=false;
- UI consumes durable source receipt rather than treating provider URI as canonical source;
- live screen intentionally remains one sensory session, not N independent durable observations.

Known next repair:
UI shell commit() still mutates in-memory S before native persistence. A failed SharedPreferences commit can therefore leave rendered memory ahead of durable state. Next pass replaces this with candidate-state transaction semantics.
