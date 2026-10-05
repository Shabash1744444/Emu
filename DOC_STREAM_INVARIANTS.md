# C4 Stream Invariants

- **STREAM-01 No Token/Message Ontology.** Tokens/prompts/completions terminate at adapters; they are never C4 concepts.
- **STREAM-02 Unbounded Logical Input.** A book, 100k-token-equivalent lesson or continuous lecture is a stream. Physical limits cause backpressure, not a context window.
- **STREAM-03 Online Assimilation.** `S(t+1)=F(S(t),E(t))`; consumed experience may alter state before a source ends.
- **STREAM-04 Source Conservation.** Chunking one source into 10,000 fragments does not create 10,000 independent observations.
- **STREAM-05 Boundaries Are Hints.** Send/newline/EOF/silence are temporal cues, never cognition resets.
- **STREAM-06 Interruptible Sources.** A source can pause for a question, sleep, freeze or restart and resume from a durable cursor.
- **STREAM-07 Symmetric Expression.** C4 expression is a stream; publication may be throttled by the host Governor without inventing `max_tokens` inside C4.

## BLUE-100K acceptance probe
Feed a huge lesson about a novel concept, assimilate while ingesting, pause/branch, freeze/restart mid-source, resume the same provenance lineage, then test transfer on unseen examples.
