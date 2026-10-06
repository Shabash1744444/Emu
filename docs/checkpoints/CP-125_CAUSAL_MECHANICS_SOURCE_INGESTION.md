# CP-125 — CAUSAL MECHANICS + SOURCE INGESTION

World:
- mechanisms PUSH / RAMP / SPRING;
- force variants produce distinct outcomes;
- prediction remains before action;
- SANDBOX_RECEIPT uses CAUSAL_MECHANICS_V2;
- challengeVariant encodes mechanism + force;
- verifiedVariants tracks distinct variants;
- repeats remain logged but do not inflate distinct evidence count;
- bounded trial history exposed to user.

Source ingestion host:
- bounded source chunk reader, max 256 KiB per bridge call;
- offset-based reads for streaming;
- SHA-256 stable source identity;
- digest scan refuses >256 MiB in this first mobile implementation;
- UI source inspection reads only first 64 KiB after digest;
- SOURCE_INSPECTED records sourceId/mime/chunk facts;
- chunk boundaries are transport only, not cognitive episodes.

Build gate:
- previous World baseline #27-29 SUCCESS.
- #30-32 pending for new mechanics/source ingestion; do not call accepted until green.
