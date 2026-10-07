# CP-185 — LAYOUT FOUNDATION V2 GREEN

Date: 2026-10-07
Status: GREEN
Release: 0.64-layout-foundation
versionCode: 65
Binary workflow head: 729d6731d73ca6d07f491dabece8230489ae2d25
GitHub Actions run: #460
Run ID: 37658814766

## Goal

Make layout stability a release contract before adding more visual complexity.

## Implemented

- app shell now uses flex-column geometry as final layout authority;
- VisualViewport controls --vvh / --vvw;
- portrait and landscape maintain separate viewport baselines;
- rotation no longer masquerades as keyboard opening;
- keyboard mode requires composer focus + real viewport contraction;
- main/page horizontal overflow is bounded;
- bottom nav is centered, max-width bounded and reserves page space;
- 5 nav columns are an explicit contract;
- safe-area handling covers app top, nav, keyboard composer and material viewer;
- long messages / filenames / runtime errors / hashes wrap without forcing page width;
- major horizontal strips use contained x-scrolling;
- primary touch controls have >=44px touch targets;
- decorative glow/pseudo layers cannot intercept touches;
- compact <=380px layout;
- short-viewport mode;
- landscape mode;
- centered tablet shell up to 760px;
- material viewer bounded to actual VisualViewport;
- chat composer remains inside visible keyboard viewport.

## Runtime layout diagnostics

Nonfatal layoutHealthCheck() checks the real device for:
- document horizontal overflow;
- main right overflow;
- active-page horizontal overflow;
- bottom nav outside viewport;
- composer outside keyboard viewport.

Failures emit UI-only LAYOUT_WARNING with:
- viewport width/height
- current page
- keyboard state
- concrete issue list

LAYOUT_WARNING != C4 OBSERVATION
LAYOUT_WARNING != C4 EVIDENCE

## Regression discovered during CP185

The first layout-diagnostics patch accidentally collapsed:
  $$().forEach
back into:
  $().forEach
inside setPage().

Root cause was JavaScript String.replace replacement-string semantics:
  $$ in a replacement string means one literal $.

The UI contract guard correctly blocked the build.
Repair uses callback replacement so literal $$ survives.
Exact repository scan at the final source: 0 single-element collection selectors.

## CI contracts

UI CONTRACT PASS:
- 160 DOM ids
- 41 critical bindings

LAYOUT CONTRACT PASS:
- 160 unique ids
- 5 pages
- 5 nav targets

Additional checks include:
- duplicate DOM ids forbidden;
- page/nav set equality;
- responsive CSS foundation required;
- obsolete viewportMax heuristic forbidden;
- composer cannot become position:fixed;
- layout foundation must remain the final style authority.

## Build

GitHub Actions run #460: SUCCESS

Artifact:
- C4-Nursery-0.64-layout-foundation
- artifact ID: 11499188616
- ZIP bytes: 49,394,086
- ZIP SHA256: 40b63d840b52fe567a3165b3c27d69966db0b25e382d00fec84bfc84137462b0

APK:
- bytes: 49,393,656
- SHA256: 0e59ed2425c1583577b253706c0194aa3930bb0d7cdf9b76b3376d75ad3393b3
- unzip integrity: PASS

Bundled assets verified by CI:
- VRoid Sample D: 16,851,352 bytes
- VRoid SHA256: 9adf1b44e959d2688d62c2dd558e74315d6aa40e3bf8d281390b7a85dc0df9b7
- Poly Haven Studio Small 09 HDRI: 1,615,248 bytes
- HDRI SHA256: e7cfda5f4e98e623db12b8bfd0184e048488e4855d9c83e2751fb44a32e80c45
- three-vrm bundle SHA256: e2a2f07c5090b32a31bb9493ecc1209b45c8d1f23da2eb829eed9685d3ead55d

## Physical Android gate

Still required on target phone:
- portrait tabs and fixed bottom nav;
- soft keyboard / composer visibility;
- rotate portrait <-> landscape with keyboard closed;
- rotate with chat focused;
- long C4 replies;
- long source filenames;
- compact width behavior;
- material viewer;
- safe-area / gesture navigation;
- inspect any LAYOUT_WARNING events.

0.63.1 remains the functional bootstrap baseline.
0.64 supersedes it for layout/device testing.
