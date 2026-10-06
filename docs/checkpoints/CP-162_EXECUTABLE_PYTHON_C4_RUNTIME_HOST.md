# CP-162 — EXECUTABLE PYTHON C4 RUNTIME HOST
Date: 2026-10-06

Priority achieved at build level:
- Android APK now embeds Python 3.13 execution via Chaquopy 17.
- arm64-v8a target.
- NumPy bundled for current C4 runtime dependencies.
- C4 runtime code is NOT frozen into Emu.
- User can import a runtime ZIP containing c4child/runtime.py.
- Runtime ZIP is extracted into private app storage and dynamically imported.
- User separately imports/activates .c4m organism weights/state.
- OPEN_SESSION loads selected .c4m through runtime load_c4m and instantiates C4LivingRuntime.
- runtime_running is set only after Python load/constructor succeeds.
- USER_MESSAGE/TICK route into Python; emitted events are forwarded to window.C4RuntimeEvent.
- chat still renders only actual REPLY/ASK runtime events.
- runtime transport events/results remain traced.
- System UI now has Import runtime ZIP + Start C4 controls.

Critical UI repair:
- fixed fatal selector helper syntax ($ / $$).
- GitHub Actions now runs node --check against WebView JavaScript before Gradle.
- build failures are propagated with pipefail and build logs retained.

Build gate:
- #219 SUCCESS.
- Artifact C4-Nursery-0.42-runtime-host
- Artifact ID 11426202840
- ZIP size 33,774,009 bytes (Python/NumPy runtime explains size increase).

Device test sequence:
1. Install 0.42.
2. System -> Import runtime ZIP (G208-compatible source archive containing c4child/runtime.py).
3. Import/activate desired .c4m.
4. Tap Start C4; UI may say RUNNING only if real Python load succeeds.
5. Open Dialogue and send a message; only actual runtime events appear.

Known compatibility risk:
Current dynamic adapter targets the G208-reference API shape. Newer runtime packages may require adapter compatibility updates if load_c4m/C4LivingRuntime signatures changed.
