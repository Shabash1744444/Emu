# CP-003 — FLAT ROOT PACKAGE

Date: 2026-10-05

Reason: mobile GitHub upload cannot reliably preserve nested/hidden directories.

Changes:
- UI CSS and JS inlined into root `index.html`.
- docs/checkpoints/tests renamed into root-visible files.
- Android workflow exported as root `BUILD_APK.yml`.
- no runtime semantic change from CP-002.

Constraint:
GitHub itself requires Actions workflows under `.github/workflows/`; this path
cannot be made flat by application design. `BUILD_APK.yml` is the source-of-truth
copy intended to replace the legacy invalid `.github/workflows/build.yml` once.

Next:
install workflow once, run APK build, then continue lifecycle/persistence cascades.
