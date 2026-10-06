# CP-134 — PRE UNIFIED SOURCE SPOOL

Problem:
Current file/photo/audio/screenshot inputs expose heterogeneous URIs and persistence. A real C4 runtime must not depend on provider/media URI lifetime or let UI metadata define evidence identity.

Target:
all durable discrete sources -> private content-addressed spool -> SHA256 sourceId -> metadata/provenance -> bounded reads -> BEGIN/APPEND/END transport.

Live screen remains a sensory session, not a pile of durable independent screenshots.
No source import itself grants learning/evidence credit.
