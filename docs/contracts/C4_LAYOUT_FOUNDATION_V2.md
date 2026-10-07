# C4 LAYOUT FOUNDATION V2

Date: 2026-10-07
Status: UI layout contract
Parent: CP-184 UI Bootstrap Hotfix

## Goal

Make layout stability a release-level invariant across Android phones instead of fixing individual screens after regressions.

## App shell

The app uses a flex column shell:
- app height follows VisualViewport (--vvh);
- top bar is a fixed flex row;
- main is flex:1 with min-height:0;
- bottom nav is fixed and page content reserves its height;
- all main pages are width-bounded and horizontally clipped.

This replaces fragile global height arithmetic as the final layout authority.

## Viewport and keyboard

VisualViewport drives:
- --vvh
- --vvw
- portrait/landscape-specific height baseline
- keyboardOpen only while the chat composer is focused and viewport height contracts enough
- layoutLandscape
- layoutCompact
- layoutShort

Rotation is not treated as keyboard opening.

Keyboard mode:
- hides top/nav/nonessential sensory chrome;
- keeps chatStage and composer inside the visible viewport;
- does not pause runtime, sensory input or chat events.

## Safe areas

Top and bottom Android/iOS safe-area insets are respected for:
- app shell;
- nav;
- keyboard composer;
- material viewer.

## Overflow

Critical text containers use bounded wrapping.
Long:
- runtime errors
- messages
- filenames
- hashes
- source state
must not force horizontal page scrolling.

Scrollable horizontal tool strips use contained x scrolling instead.

## Touch

Primary interactive controls have a minimum 44px touch target.
Decorative pseudo-elements and glow layers are pointer-events:none.

## Responsive modes

Compact:
- width <= 380px
- reduced gutters and header density
- two-column organ/library layouts

Landscape:
- shorter top/nav shell
- shorter cinematic/world surfaces
- compact presence copy

Tablet:
- shell max width 760px
- centered content/nav

## Runtime layout health

A nonfatal layoutHealthCheck() checks the real device viewport for:
- document horizontal overflow;
- active-page overflow;
- main overflow;
- bottom-nav leaving the viewport;
- composer leaving the visible keyboard viewport.

Failures emit UI diagnostic LAYOUT_WARNING only.

LAYOUT_WARNING != C4 OBSERVATION
LAYOUT_WARNING != C4 EVIDENCE
LAYOUT WARNING MUST NOT THROW OR BLOCK UI

## Invariants

LAYOUT POLISH MUST NOT CHANGE C4 SEMANTICS
DECORATION MUST NOT CAPTURE INPUT
KEYBOARD MODE MUST NOT HIDE COMPOSER
BOTTOM NAV MUST NOT COVER PAGE CONTENT
LONG CONTENT MUST NOT FORCE HORIZONTAL SCROLL
