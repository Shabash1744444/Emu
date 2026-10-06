# CP-168 — PRE ORGANISM PICKER HOTFIX

Date: 2026-10-07
Parent: CP-167 interaction hotfix
Status: PRE

Physical symptom:
- Runtime step can be selected.
- Choosing the .c4m organism on step 2 returns to the app with no visible change.

Verified root cause:
- organism import tested ".c4m" against the content:// URI string;
- Android document providers commonly hide the original filename inside the URI;
- valid .c4m files therefore reached EXPECTED_C4M;
- ORGANISM_ERROR was persisted to diagnostics but not surfaced prominently in the setup gate.

Fix scope:
- resolve OpenableColumns.DISPLAY_NAME and validate the actual filename;
- show ORGANISM_IMPORTING immediately while hashing/copying;
- persist organism display name;
- expose import errors directly in the brain setup gate;
- rebuild as 0.48-organism-picker-hotfix.

No C4 model/runtime semantics changed.
