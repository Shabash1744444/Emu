# CP-184 — UI BOOTSTRAP HOTFIX GREEN

Date: 2026-10-07
Status: GREEN
Release: 0.63.1-ui-hotfix
versionCode: 64
Binary workflow head: 87be9e0282727a1355086cf640963a6d7e47406c
GitHub Actions run: #451
Run ID: 37652170357

## User-reported symptom

0.60 rendered UI but buttons appeared dead / interactions did not work.

## Root causes reproduced from exact 0.60 and 0.63 APK assets

1. Collection-selector misuse:
   - $() returns one Element.
   - code called .forEach() on it.
   - affected organ map, World tabs/panels; later 0.63 also quality controls and media-stop query.

2. Premature bootstrap:
   - a top-level renderHomeDashboard() ran before const DEFAULT_GLB initialization.
   - after the selector crash was repaired, this produced a TDZ ReferenceError.

3. Stale DOM references:
   - render() directly wrote to #touches and #saved after those elements had been removed from the redesigned UI.
   - this produced null.textContent startup crashes.

These faults executed before/inside startup rendering and prevented later button handlers from becoming reliably usable.

## Repairs

- all collection queries use $$();
- removed premature renderHomeDashboard() bootstrap call;
- stale #touches / #saved writes are null-safe;
- added tools/ui_contract_guard.py;
- CI now rejects:
  - $() used with collection methods;
  - direct dereference of removed static DOM IDs;
  - the known early renderHomeDashboard()/DEFAULT_GLB TDZ regression;
  - missing critical button/group bindings.

## Exact packaged APK validation

Artifact:
- C4-Nursery-0.63.1-ui-hotfix
- artifact ID: 11497455484
- ZIP bytes: 49,390,704
- ZIP SHA256: 01ce20ec41a68863c5b8fb4a118c0bf315e54de7cd8c5463941792d99e9a4265

APK:
- bytes: 49,390,292
- SHA256: b26808f55d718f8528eca943fa94b648b7cd5d8ceab9831707e4bc37c86e03c3
- unzip integrity: PASS

Packaged assets/index.html:
- UI contract guard: PASS
- 160 static DOM IDs validated
- startup smoke with Android-bridge stub: PASS
- chat form submit smoke: PASS

Direct click smoke PASS:
- Library import
- Runtime start
- Brain start / gate start
- File / photo / live eye / mic / body / screenshot / screen stream
- New world task / verify game
- prediction / force / experiment
- sequence memory
- avatar model pick / clear
- organism pick / clear
- runtime pick
- export
- Home jump / sensory jump
- Material viewer close / explicit C4 send

Grouped-control smoke PASS:
- bottom navigation: Home / Dialogue / World / Library / System
- Home modules
- World Overview / Physics / Memory
- Library filters
- AUTO / HIGH / BALANCED / ECO quality
- PUSH / RAMP / SPRING mechanics

## Remaining physical-device gate

This checkpoint proves packaged UI/bootstrap/button wiring and build integrity.
It does not replace Android hardware validation for:
- Storage Access Framework picker behavior;
- microphone/camera/screen-capture permissions;
- WebView media decoding on the target phone;
- current runtime ZIP + .c4m compatibility;
- foreground service lifecycle under OEM battery management.

Old 0.60 and old 0.63 APKs are superseded for testing by 0.63.1-ui-hotfix.
