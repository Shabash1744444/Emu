# Architecture C0

Layers: C4 Core → Runtime → Runtime Governor → Android Host → Nursery UI.

The UI and Android host must never leak chat/token ontology into the core. The runtime carries ordered events and durable source cursors. The Governor owns CPU/battery/thermal/publication budgets and is not a fifth cognitive law.

Lifecycle invariant: FREEZE commits durable state and then permits zero cognitive state mutation until restore/resume. SLEEP is not freeze: it is reserved for consolidation/replay.

Input families: Observation, EpisodeFragment, HumanTextFragment, TeachingSignal, TimeEvent, SensorEvent, StreamBoundaryHint, Wake, Sleep, Freeze.

Output families: ExpressionFragment, Initiative, Prediction, Question, ActionIntent, LearningEvent, Discovery, Conflict, StateChange, CheckpointRequest.
