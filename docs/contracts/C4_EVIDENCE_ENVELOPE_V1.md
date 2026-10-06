# C4 EVIDENCE ENVELOPE V1 — App/World boundary

Every source/world item crossing into C4 carries provenance independently from display text.

Required envelope fields:
- eventId: unique transport id.
- sourceId: stable source/session/environment id.
- phase: LIVE | REPLAY.
- origin: USER | TEACHER | SENSOR | SANDBOX | SIMULATION | C4_SELF | DERIVED.
- observationClass: OBSERVATION | RECEIPT | MESSAGE | RULE_DERIVATION | SELF_OUTPUT.
- independentEvidence: boolean, default false.
- parentEventId / requestId when causal ancestry exists.
- contentDigest/evidenceSignature where bytes/outcome can be canonicalized.

Hard gates:
- DERIVED => independentEvidence=false and observationClass=RULE_DERIVATION.
- C4_SELF => independentEvidence=false.
- REPLAY => independentEvidence=false.
- SIMULATION => independentEvidence=false unless core explicitly defines a separate simulation-learning lane; it never becomes real-world observation.
- repeated content from the same source does not become independent merely because it has another eventId.
- ACTION_REQUEST never has outcome/evidence credit.
- SANDBOX_RECEIPT may verify sandbox competence only after matching requestId/action/environment-owned outcome.
- teacher naming is a teaching/binding event, not automatic independent physical evidence.
- UI cannot promote or rewrite provenance.

G156 compatibility:
Rule explanations/results are DERIVED and not observations. Missing rule evidence requests continue to use ASK; the app must not invent another cognitive outbound type. Suspended rules remain inspectable history.

G157-G161 forward compatibility:
The envelope explicitly reserves quarantine semantics so teacher/self-output/replay/simulation/derived can remain non-independent without UI special cases.
