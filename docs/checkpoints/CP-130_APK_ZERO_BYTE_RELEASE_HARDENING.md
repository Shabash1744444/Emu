# CP-130 — APK ZERO-BYTE INCIDENT / END-TO-END RELEASE HARDENING

User report: downloaded/built artifact appeared as 0 KB.

Forensic check of run #50 artifact 11391742732:
- GitHub artifact ZIP: 33,401 bytes.
- GitHub artifact digest: sha256:4b173d49be35e12e0aa5bce86a5499d73a1b50e20b294030462d23e4ae212bd2.
- downloaded ZIP hash matched GitHub exactly.
- ZIP contained app-debug.apk: 36,960 bytes.
- file(1): Android package (APK), APK Signing Block present.
- unzip -t APK: no errors.
- APK SHA256: aa912415f70e5b2b73310e2a6a96a11974f69d4a5a773d8e71893814448f6263.

Conclusion:
0 KB was not produced by Gradle/run #50. Failure occurred downstream of GitHub artifact bytes (download/extract/share path), but release UX allowed ambiguity.

Hardening:
- delete orphan nursery-v2.html from package;
- workflow test -s APK;
- unzip -t APK before upload;
- require APK >10,000 bytes;
- stage explicit C4-Nursery-DEV38.apk;
- generate SHA256.txt with exact bytes + SHA;
- upload both with compression-level 0;
- next acceptance requires downloading artifact back from Actions and matching SHA256.txt.

No release is accepted solely from a green Gradle step anymore.
