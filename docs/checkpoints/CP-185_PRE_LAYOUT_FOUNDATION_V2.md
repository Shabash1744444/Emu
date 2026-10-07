# CP-185 — PRE LAYOUT FOUNDATION V2

Date: 2026-10-07
Parent: CP-184 UI Bootstrap Hotfix GREEN
Status: PRE

Goal:
Make layout stability a release contract, not an afterthought.

Scope:
- flex app shell instead of fragile fixed-height arithmetic;
- Android safe-area handling;
- VisualViewport-driven keyboard mode;
- no horizontal page overflow;
- long message / filename / runtime-error wrapping;
- stable fixed bottom navigation;
- 44px minimum primary touch targets;
- compact-phone layout;
- landscape layout;
- tablet/max-width layout;
- modal/material viewer bounds;
- chat composer remains visible with keyboard;
- decorative layers never intercept taps.

Hard requirements:
LAYOUT POLISH MUST NOT CHANGE C4 SEMANTICS
DECORATION MUST NOT CAPTURE INPUT
KEYBOARD MODE MUST NOT HIDE COMPOSER
BOTTOM NAV MUST NOT COVER PAGE CONTENT
LONG CONTENT MUST NOT FORCE HORIZONTAL SCROLL

Target release:
0.64-layout-foundation
