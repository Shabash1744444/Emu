# CP-138 — EXTERNAL G182 STATE AUDIT INGESTED

External adversarial review supplied by user is accepted as a STATE-ONLY audit, not as a runtime verdict.

Grounded findings from the supplied review:
- shipped G182 package under review contained persisted graph/runtime-state but not runtime code, so claimed 213/213 behavioral tests could not be independently reproduced from that package;
- 1,402/1,407 facts were CREATOR_PRIOR/TEACHER;
- all persisted propositions had one origin family under the auditor's origin-family metric;
- 31 multi-source propositions used the same origin family;
- correction_of targets were absent from hot/cold and audit was empty;
- orphan entities existed;
- competency requirements were mostly answerable from the same curriculum group;
- facts had no validity-time fields;
- privacy/principal semantics looked mixed;
- serialized container size must not be described as neural parameter capacity.

Interpretation:
This does NOT prove the wider C4 architecture has no neural/dynamical runtime. It proves the reviewed .c4m artifact is persisted state and that runtime behavior cannot be inferred from that state alone. App architecture therefore MUST continue to separate Organism State from Runtime and must never label a selected .c4m as a running neural model.

Action for current G207+ integration:
- treat these as regression/adversarial requirements;
- expose runtime build/test identity separately from organism identity;
- preserve correction/tombstone history in future full-export diagnostics;
- preserve source-family/provenance fields;
- support held-out evaluation sets distinct from curriculum;
- never infer independent evidence from source-group count;
- keep temporal validity available in future source/fact diagnostics;
- model bay UI must say state/runtime/session separately.
