# CP-168 — ORGANISM PICKER HOTFIX GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: b6ddc166abc8a7bfca6bb90a7b35e3bb0879287c

Observed device symptom:
- setup step 2 opened the Android picker;
- selecting a valid .c4m returned to the app with no visible state change.

Verified root cause:
- importer validated ".c4m" against the content:// URI text;
- Android document providers may not expose the original filename in that URI;
- valid .c4m therefore failed EXPECTED_C4M;
- UI did not prominently surface ORGANISM_ERROR.

Fixed:
- resolve OpenableColumns.DISPLAY_NAME;
- validate the actual display filename;
- emit ORGANISM_IMPORTING before hashing/copying;
- persist and display organism name;
- surface import error directly in the setup gate;
- verify non-empty file and copied byte count;
- CI guard prevents URI-based extension validation from returning.

Release:
- versionCode 48
- versionName 0.48-organism-picker-hotfix
- GitHub Actions run #296 SUCCESS
- artifact ID 11441971846
- artifact ZIP 33,815,451 bytes
- artifact ZIP SHA256 edb932de27fabae61159f00d82929b0475458e509f4cf94ad0095712ee272818
- APK 33,815,006 bytes
- APK SHA256 62cd08cae35add096f2f7b5a5266d48ea515b8a29543c21edd07911e15bbc31e

Gates:
- WebView JavaScript syntax PASS
- selector misuse lint PASS
- organism picker regression lint PASS
- Python py_compile PASS
- Gradle assembleDebug PASS
- APK unzip integrity PASS

No C4 cognitive laws or model state changed.
