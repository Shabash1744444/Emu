# CP-186 — G327 Android import compatibility audit (2026-10-08)

**Status:** PYTHON CONTRACT SMOKE PASS / PHYSICAL DEVICE NOT TESTED / NOT CANONICAL.

## Repo truth

- The native Android host application is **Shabash1744444/Emu**, `main` branch, NOT the separate C4 core repository `Shabash1744444/-`. The `Emu/github` branch is currently empty.
- `Emu/main` has Android/Gradle app versionName `0.64.3-trace-ru`, Chaquopy Python 3.13 + NumPy, ARM64, Android WebView shell, a native foreground OrganismService, sensor services, a live room, runtime/organism import UI and trace export.
- `app/src/main/python/c4_mobile_bridge.py` implements `install_runtime(zip_path, home)` which discovers `**/c4child/runtime.py` and extracts that package's Python sources, then `open_organism(path)` which dispatches `C4M_CHILD_V0.4_COMPACT` through `load_c4m_compact(..., with_runtime=True)`, constructs `C4LivingRuntime(C4ChildDialogue(graph))`, and calls `load_runtime_state(rs)`.
- UI: `Импорт runtime ZIP`, organism `.c4m` import/select, `Запустить C4`. Android app itself does **not** require a Windows launcher.
- Distinct repositories were intentionally chosen to keep organism/runtime and Android body separate.

## Exact G327 import artifacts

G327 source base: isolated `C4_G327_P0_REVISED_DIALOGUE_RUNTIME_PLUS_G326_WEIGHTS_2026-10-08.zip`.
The combined source archive contains `runtime/c4child/runtime.py` and `model/child_g327_runtime_compatible_weights_UNCHANGED.c4m`. G327 runtime adjusts dialogue while preserving the already trained G326 model; no new weight training happened in G327.

Split Android import files, generated without code editing:

- `C4_G327_ANDROID_RUNTIME.zip` — 231140 bytes; 53 `c4child/*.py` source modules; SHA256 `527476ae884594d77d4f82e942ceccb552d1ecf2a2a777ecde462b982bf04316`.
- `C4_G327_ANDROID_ORGANISM.c4m` — 2065628 bytes; `C4M_CHILD_V0.4_COMPACT`; SHA256 `dfe4b40211b1ce2d3400e95217ecc9210fc1f0a93076ee42a51e55f0be0b090f`.

The exact artifact bytes were created in the originating conversation sandbox, and should be transferred into Android device Downloads. **Do not reconstruct a presumed binary from this documentation**; always verify downloaded SHA. The artifacts are not committed as binaries to this repository.

## Local host-contract smoke actually executed

The contract test emulated the existing Python bridge in a clean temporary folder:

1. Extract runtime package to `c4_runtime/c4child/*.py`.
2. Import `c4child`, validate `C4LivingRuntime` and `C4ChildDialogue`.
3. Load `.c4m` using `load_c4m_compact(...,with_runtime=True)`.
4. Construct `C4LivingRuntime(C4ChildDialogue(g))` and `load_runtime_state(rs)`.
5. Send Russian `user_message` inputs and `poll(100)`.
6. Save with `save_c4m_compact(...,runtime_state=runtime.runtime_state(),include_cold=True)`.
7. Load that saved file again; validate runtime step and seven preserved causal studies.

Output: **PASS**; 53 modules; checkpoints before/after are ZIP-valid; G327 model loaded with seven stored learned studies; responses generated; cold state loaded. No UI or ARM64 device execution was claimed.

## Recommended device live test (explicit steps)

1. In installed C4 Nursery, stop any currently running C4 session and back up the prior `.c4m` before replacing the runtime.
2. Download both `C4_G327_ANDROID_RUNTIME.zip` and `C4_G327_ANDROID_ORGANISM.c4m` to phone.
3. Open app System page; select **Импорт runtime ZIP** -> choose `C4_G327_ANDROID_RUNTIME.zip`.
4. Import/activate organism via existing organism selector -> `C4_G327_ANDROID_ORGANISM.c4m`.
5. Tap **Запустить C4** and verify actual `RUNNING` status; any import failure is a failure, not a success.
6. In chat: `Маша думает, что Иван опоздал.` -> `Что думает Маша?` -> `Маша думает, что Луна — сыр.` -> `Это правда?`. Verify attributed belief remains distinct from world fact.
7. Enable transport log, and test runtime-native cognitive trace controls only if supported. Trace unsupported must be reported honestly (G327 did not claim full `TRACE_CONFIG`/`TRACE_SNAPSHOT` support).
8. Export app's training/diagnostics bundle; send results for live review.

## Device blockers / debt

- **NOT** tested on Android device/Chaquopy ABI, APK build not run in this audit.
- `Emu/main` already implements runtime ZIP and `.c4m` import; therefore do **not** introduce a second web-chat app or new fake fallback.
- The main importer copies Python modules from selected ZIP; other files are ignored; thus model import must use separate `.c4m` path.
- The plugin/main host native TRACE recorder may report unsupported on current G327 because cognitive trace API is a separate requirement.
- Mobile install error handling and atomic package replacement should be adversarially tested before calling hot swap safe.
- Earlier G326/G327 full Python package regressions had 27 unavailable historical model fixture errors. G327 is a live-test candidate, not canonical.
- No claim of complete natural Russian understanding, multimodal perception, hardware TTS, G323 binary merge or AGI.

## Required next gate

Run actual Android import/OPEN_SESSION/USER_MESSAGE/TICK/SAVE/COLD_RELOAD and capture all native trace and cognitive status. Only then mark MOBILE_GREEN. App version should advance only after genuine APK build with working native host compatibility checks. Preserve core/host repository separation.
