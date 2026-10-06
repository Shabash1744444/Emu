# C4 CORE HANDOFF — integration notes

> Coordination note for the C4 Nursery app branch.  
> This file is intentionally documentation-only: do **not** treat it as a request to redesign the cognitive core.

## Repo state observed

Current `main` is an Android shell:

- `app/src/main/java/com/singularity/c4nursery/MainActivity.java` creates a local `WebView`.
- `app/src/main/assets/index.html` is a static DEV37 smoke UI.
- `.github/workflows/build-apk.yml` builds `:app:assembleDebug` directly from the repo.
- Root `c4-build.yml` is an older payload-oriented workflow description and currently expects `C4_PAYLOAD.txt`; do not assume it is the workflow actually used by GitHub Actions.
- `payload/C4_PAYLOAD.part00` exists, but the current APK workflow does not consume it.

## Hard C4 runtime invariants

### 1. C4 is not request/response

Do not implement the app as:

```
user -> model.generate() -> reply
```

The organism is an always-living event-driven runtime. The app is a body/UI around it.

Stable conceptual surface:

```
user_message(text, metadata?)
tick(n=1)
poll(limit?)
runtime_state()
```

The runtime may emit output without a fresh user message.

Expected outbound event classes include ordinary replies plus initiative such as `ASK`, `PUBLISH`, and `STATUS`.

**Frontend timers must never fake initiative.** If the avatar speaks first, the event must have been produced by the runtime.

### 2. MESSAGE != COGNITIVE EPISODE

A chat bubble is transport, not a cognitive boundary.

A long input may contain many semantic episodes and must be processed incrementally. Do not build a cognitive `max_tokens` / fixed context-window concept into the UI.

For long lessons/sources, preserve a streaming shape such as:

```
begin_source(...)
append_source(chunk, offset, ...)
end_source(...)
```

The organism may learn/respond/ask while the source is still arriving.

### 3. Durable mutation must be atomic

A durable state change is not complete until its checkpoint is safely written.

Required pattern:

```
write temp
-> close/fsync
-> validate load + checksums
-> atomic replace
-> optional backup
```

Do not let UI success imply persistence before the checkpoint succeeds.

### 4. No hidden intelligence fallback

Do not silently add:

- OpenAI/Claude/other LLM fallback;
- vector DB as canonical memory;
- frontend heuristics that invent cognitive state;
- fake progress/XP that unlocks world content independently of C4 competence.

If a capability is not in C4 yet, surface that honestly.

### 5. UI reflects function

Animation/state must correspond to real runtime state.

Examples:

- pulse only if actual runtime cycles are active;
- contradiction indicator only from actual unresolved contradiction;
- learning/progress only from actual curriculum/competence state;
- world-level unlock only from a real capability transition, never elapsed time / fake XP.

## Nursery / sandbox boundary

Future 3D world should be treated as an external environment.

Keep these distinctions:

```
ACTION_REQUEST != VERIFIED_OUTCOME
SANDBOX_OBS != REAL_WORLD_OBS
SANDBOX_RECEIPT != SELF_REPORT
SIMULATION != OBSERVATION
PREDICTION != EVIDENCE
```

A body action teaches nothing at send time. Learning may occur only after a matching environment receipt.

A future body bridge should therefore look conceptually like:

```
C4 -> ACTION_REQUEST(request_id, action, params)
world executes
world -> SANDBOX_RECEIPT(request_id, action, params, outcome, success, ...)
C4 validates receipt
C4 updates skill/competence
```

Do not auto-resume an unfinished physical action after process restart; reconcile with the world first.

## Progressive world

World progression should be capability-gated, not level/XP-gated.

Example progression:

- look / turn;
- move / stop;
- reach / grasp / release;
- containers / push / pull;
- simple mechanics;
- causal experiments;
- self-directed experiments.

The environment may become richer after verified competence, but UI should not award competence itself.

## Sensory integration

Do not make the environment teach by sending semantic labels such as:

```
class = "cube"
```

Preferred flow:

```
camera/world sensor
-> compact sensory features
-> C4 sensory concept/hypothesis
-> optional later teacher naming/binding
```

A simulator may expose compact feature vectors before raw pixels/audio, but provenance must remain sandbox/synthetic rather than pretending the organism saw it in the real world.

## Current app integration advice

The current `WebView + local asset` shell is fine for smoke tests, but the next boundary should be narrow and explicit.

Avoid a giant unrestricted `addJavascriptInterface` object. Prefer either:

1. a small typed Android bridge with an allow-listed message protocol, or
2. a local runtime service with an event stream (WebSocket/SSE) and explicit commands.

The UI should subscribe to runtime events rather than poll/fake life.

## Source-version caution

C4 core development is ahead of the app repo and is being checkpointed separately. Do not copy an arbitrary old payload/core snapshot into the APK and call it canonical.

Before wiring the actual organism, require a named core handoff containing:

- source version / checkpoint id;
- clean `.c4m`;
- tests + expected pass count;
- checkpoint/schema version;
- SHA256 manifest;
- exact app-facing API contract.

## Build note

At the time of this handoff:

- actual GitHub Actions file: `.github/workflows/build-apk.yml`;
- legacy-looking root file: `c4-build.yml`;
- current `app/build.gradle.kts` reports `versionName="0.38-dev37"` / `versionCode=38`.

Please keep the build path single-source-of-truth to avoid shipping a stale payload by accident.

---

If another ChatGPT thread is working on this repository: treat this file as the integration contract from the C4-core thread. Update app code around these invariants, not the other way around.
