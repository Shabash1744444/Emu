# CP-163-PRE — NORMAL BRAIN BOOT
Date: 2026-10-06

Goal: one normal path from a selected .c4m to a continuously running C4 chat.

Required:
- ship an audited baseline C4 runtime in the APK (source snapshot only, not frozen organism weights);
- keep external runtime override for future incompatible generations;
- reconstruct C4LivingRuntime correctly from load_c4m graph/runtime state;
- start only after successful restore;
- always-on tick/poll loop owned by Android host;
- real runtime events only;
- restart remains conservative: no implicit physical/sensory action resume;
- JS syntax + Android build gates must pass.

Reference runtime source: user-provided C4_G208_SOURCE_ATTESTED_GREEN_2026-10-06.zip.
Weights remain replaceable and are not frozen into the APK.
