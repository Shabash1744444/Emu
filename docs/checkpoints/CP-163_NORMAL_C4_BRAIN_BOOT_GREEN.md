# CP-163 — NORMAL C4 BRAIN BOOT GREEN

Date: 2026-10-06

Status: GREEN.

Implemented:
- real compact C4M restore via load_c4m_compact(..., with_runtime=True);
- graph -> C4ChildDialogue -> C4LivingRuntime -> load_runtime_state;
- fallback loader for supported non-compact checkpoints;
- Android autonomous tick loop every 1.5 s while process is alive;
- runtime calls serialized through one Python bridge;
- RUNNING only after successful organism restore;
- real runtime events only;
- atomic C4M checkpoint after user messages;
- additional checkpoint after emitted autonomous events / periodic unsaved steps;
- checkpoint on app pause;
- direct "Запустить мозг" control in Dialogue;
- visible ready / missing runtime / missing organism / RUNNING / error states;
- JS syntax gate and Python py_compile gate in CI.

Real G208 cold-start smoke was executed with child_g208_source_attested.c4m and produced a real REPLY through poll().

Release:
- versionCode 43
- versionName 0.43-brain-boot
- GitHub Actions run #232: SUCCESS
- artifact C4-Nursery-0.43-brain-boot
- artifact id 11427498441
- APK bytes 33774002

Boundary:
true indefinite cognition after Android suspends/kills the app process still requires a foreground runtime service. Current build does not pretend otherwise.
