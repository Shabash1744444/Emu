# C4 Nursery 0.65.0 — native research ABI integration

C4 is primary; Emu is a host. EVAL / COMMIT / DRIVE / MEDIATE and every upstream Python source are unchanged. G2.9 living life and G3.0C/G3.0D research states remain separate. This release does not claim free Russian conversation, canonical language merge, speech recognition, or sensor/world learning.

## Use on Android

1. Install the APK from this branch's Actions artifact. Keep existing app data; uninstalling destroys private working lives unless exported first. The original signing cache did not persist. World 0.66.1 uses a separate package to preserve the old installation, and an explicitly cached ci-signing key for future World updates; see CP-188 for migration. Older APKs from uncached jobs can have a different certificate; if Android reports a signature conflict, export the old app data before considering uninstall.
2. Import `C4_G29_G30C_G30D_EMU_RUNTIME_2026-10-11.zip` from the artifact or the original kit. Sources are identical and verified against all 42 source-file hashes (see actual profile for the authoritative count).
3. Import the original `C4_G29_G30C_G30D_DIALOGUE_RESEARCH_ORGANISM_2026-10-11.c4m`.
   Original SHA-256: `e33115a59f5521ede0e6a2dafdad5e862bb7827af329618d823103aacca1efb0`.
4. Start the brain. Check System → Life and boundaries. The initial life has 49,819 journal records, world time 12,000, journal head `34109b8e4a7d3ed1e77d74511e6e32141687779f76febb30558c98015b97a4e3`.
5. Write normal text. Own `ASK` remains an own event; adapter analysis/coach text goes into the separate research diagnostic lane and is excluded from exported assistant training conversation.
6. Save and stop before changing runtime/organism. Restart resumes the private working life, rather than a fresh import.
7. Copy/export full diagnostics when anything fails. Export living `.c4m` for a portable copy of native journal/knowledge/lab. Upstream portable format omits ephemeral transport dialogue context; same-install continuation additionally preserves that context.

## API before / after

| Boundary | Before | After |
| --- | --- | --- |
| Runtime installation | Any `c4child/runtime.py`, delete prior runtime before checking methods | Exact reviewed source profile; stage + atomic promote; unsupported builds rejected, prior installed runtime retained |
| Organism ABI | Guess compact/noncompact loader from schema | Explicit `C4M_G29_G30C_G30D_DIALOGUE_LAB_V1`; other schema rejected |
| UI transport | `runtimeSend` called with no definition in diagnostic branch HTML | Defined typed transport, async FIFO for user messages and lifecycle; request IDs and results |
| Research `REPLY` / coach `ASK` | Displayed as assistant speech | `DIAGNOSTIC`, original type/origin retained; no assistant-training eligibility |
| Native `ASK` | Runtime's own journal-derived question | Preserved verbatim, no synthetic question added by Emu |
| Imported `.c4m` | Checkpoint overwrote content-addressed import | Immutable import; separate persistent life keyed by SHA-256 |
| Small ticks | Repack 35 MB journal + 18 MB snapshot every 20 ticks or event | Native append-only journal + fsynced write-ahead operations; periodic checkpoint does not rewrite journal |
| Checkpoint | Single full ZIP | Immutable native snapshot/lab/context generation; digest-checked atomic CURRENT; last two generations retained |
| Process death | Fresh loader discarded private extracted tail/context | Replay pending WAL against original kernel's journal-tail hash checks |
| Unsupported sensor/world | Method guessing and retry after TypeError | Explicit `UNSUPPORTED`, no journal mutation or fabricated learning |
| Host world | Discrete room + toy predicate exercises | Existing room retained; additional mass/gravity/contact sphere solver and separate user marker, host-only |
| Physical Android | Not demonstrated | Still not demonstrated until handset verification |

## Persistence and integrity

`life-<import SHA>/journal.jsonl` is the native journal. It is never rotated or replaced by Emu after initial copy. Native append fsync is enabled. `transport.jsonl` records operations before execution, with sequence/previous-hash linkage. Snapshots are 18 MB on the original full organism; cadence is five minutes / explicit save / pause / stop, not each small tick. Snapshot generations hold native `snapshot.json`, language lab payload, G3.0D state, and ABI-specific transport context. CURRENT is atomically published after durable writes. Older derived snapshots can be removed; historical journal and WAL are kept.

On restart, snapshot digests, runtime build, organism identity and the entire native journal are checked before `Life.resume`. A torn/corrupt native journal or WAL is preserved and rejected; no silent truncation or fresh-life fallback. Unexplained tail also fails closed. Original checkpoint digest validation is performed by upstream loader on initial import.

Native output is stored in `outbound.jsonl` as well as native journal. Exactly-once UI delivery across process death between polling and rendering is **not certified**. No record of knowledge/input history is removed. A transport queue request is acknowledged only after execution; queued requests not yet written to WAL can be lost on process death and have not been reported as accepted.

## Full-organism verification (local Python)

10/10 integration tests passed on the user's exact full organism (see CP-187 build evidence):
identity/native-vs-diagnostic events/UNKNOWN; ambiguous raw text without false grammar learning; exact restart head; 12 concurrent messages + 12 ticks with preserved inputs; unsupported-command no-mutation; incompatible runtime preservation; corrupt generation preserved/rejected/full traceback; abrupt subprocess death + deterministic native-tail replay; corrupt native journal preserved/rejected; corrupt import/incompatible organism schema rejected.

Initial source kit/old bridge also booted locally without AttributeError. The **original handset AttributeError has not been reproduced or attributed**: full phone traceback is still required. The source evidence does not justify guessing a missing attribute from `C4Li…`. This branch locks exact sources and exposes full ABI/state/traceback to establish the handset cause.

CI uses an explicitly labeled small synthetic transport fixture, never the user's deployed organism. CI additionally checks upstream source hashes, JavaScript syntax/transport binding, existing UI/layout guards, Java physics invariants, and a real headless browser with an isolated Native test double (input queue, ASK deduplication, diagnostic exclusion, 393px viewport). CI PASS is separate from the full-organism local tests and from physical Android verification.

## World, avatar and voice boundaries

The physics engine is host infrastructure: metre/kg/second units, fixed step 1/120 s, gravity, restitution, floor friction, sphere contacts and room bounds. It is a simple rigid-sphere sandbox, not complete furniture/hand/body physics. Its observations and user impulse receipts are marked SANDBOX/SENSOR_OBSERVATION/VERIFIED_OUTCOME; current core delivery is UNSUPPORTED. No research learner is modified to pretend it can ingest them.

Teacher movement uses a separate marker. Buttons and standard browser gamepad axes with adjustable dead zone never call C4's motor executor. Existing VRM renderer, avatar model import, sensor services and parametric vocal actuator remain. No hidden LLM or text-to-speech response generator is added. G29/G30D does not yet support acoustic or visual ingestion; preserving host acquisition is not a claim of recognition.

The requested reference image remains a visual target. Existing cinematic 3D room is retained; this patch adds diagnostics, separated analysis, host spheres and teacher marker. It is **not** a photorealistic room, full custom humanoid teacher, articulated body physics, complete YouTube learning platform or finished product.

The old `github` branch at `880ad411d5f74f55f1d78b884bd074cfddfa36a3` has an empty tree; its parent contains a JavaScript app in `workflows/build.yml`. No claim is made that unavailable character controls were ported. Current teacher controls are a distinct host implementation.

## Handset checklist (all pending physical verification)

Clean APK install/import; start without AttributeError; compare exact SHA/build/journal; Привет; ambiguity and diagnostic hypotheses; explanation without false learning; stop/restart; input spam/background ASK; corrupt/incompatible files; camera/mic/room boundaries; copy/export diagnostics and live organism. Record device/Android/WebView version and actual outcomes. Until that happens, status is `PHYSICAL ANDROID NOT VERIFIED`.

## Future ABI upgrades

A new kernel build needs an explicitly reviewed profile + adapter contract. No silent schema conversion, text parser, synthetic answer, source elevation or cognition fallback. Add world/sensor/receipt bindings only to documented native entry points with counterexamples proving source/provenance/type handling. Original G3.0D language-methodology research remains outside Emu scope.
