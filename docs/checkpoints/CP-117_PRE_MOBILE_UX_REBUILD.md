# CP-117 — PRE MOBILE UX REBUILD

Date: 2026-10-06
Baseline: GitHub Actions run 37408385773 = SUCCESS; artifact C4-Nursery-DEV37-APK.
Device acceptance: APK installs/opens on user's Android device.
Observed UX failures from physical device screenshot:
- no meaningful navigation or interactive product surface;
- content collides with Android system navigation area;
- room dominates viewport while offering no useful interaction;
- developer/smoke-test copy is exposed to the user;
- weak information hierarchy and no obvious next action.

Invariant guardrails:
- UI must not mint evidence, competence, receipts, XP, or learning state.
- ACTION != VERIFIED_OUTCOME.
- AWAKE/SLEEP/FROZEN remain model/runtime state, not decorative labels.
- World/body actions remain mediated by runtime contracts; UI only requests actions.
- No token/chat/context-window ontology.
- Do not fabricate trainable-core behavior not actually connected.

Goal for next APK: real mobile-first Nursery shell with safe areas, thumb navigation, usable Home/World/Learn/Files/More surfaces, clear empty/disabled states, and touch-friendly interaction.
