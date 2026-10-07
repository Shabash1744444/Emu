# CP-171 — LIVING HOME GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 50a583763bac52c22276c8d039cbc34293264edb

## Goal

Move C4 Nursery toward a premium "living AI world" feel while preserving architectural honesty.

The reference direction is a dense, cinematic home/world surface where chat, thoughts, library, environment and learning feel integrated.

## Implemented

### Living Home
- Home rebuilt as a central organism dashboard.
- Large habitat hero with richer lighting and depth.
- Added environment dressing: bed, monitor glow, holographic orb, star field and stronger material/shadow treatment.
- Runtime presence ring reflects real runtimeInfo() state only.
- Latest real C4 REPLY / ASK / PUBLISH is projected into the Home thought card.
- Quick modules link to Dialogue, World, Library and Sensory channels.

### Real-state metrics only
Home exposes:
- real message count;
- real ASK count in the visible conversation history;
- stored-source count;
- last host save time;
- chat runtime state;
- camera / microphone / body-sensor availability.

Forbidden from this release:
- fabricated emotion;
- fabricated curiosity;
- fake XP / levels;
- fake energy / mood;
- any synthetic "personality meter" not emitted by C4.

### Agency preserved
- C4 remains owner of its avatar/body.
- User remains an external actor.
- No Wave / Take / Place / Move puppeteering controls returned.

### Regression repair
A collection-selector regression was found before release:
single-element $() calls had reappeared in collection paths.

Repaired and guarded:
- page navigation;
- nav buttons;
- Home module buttons;
- room object collections;
- drop-target collections.

CI now rejects literal selector .forEach misuse.

## Release

- versionCode 51
- versionName 0.51-living-home
- GitHub Actions run #326 SUCCESS
- artifact ID: 11477637912
- artifact: C4-Nursery-0.51-living-home

Artifact ZIP:
- 33,821,870 bytes
- SHA256 b1a9183f6f07495821de896d39f4a3350d93ad38c9180c973bcdaf63936cd0ce

APK:
- 33,821,458 bytes
- SHA256 00de8ec1f40b16204618bf7d7f3b8376dd7a64b697860087c479a63f2708433b
- unzip integrity PASS

## Gates

- WebView JavaScript syntax PASS
- collection selector regression guard PASS
- organism picker regression guard PASS
- stable-chat forced-scroll guard PASS
- AI-owned body regression guard PASS
- Living Home realism guard PASS
- Python py_compile PASS
- Gradle assembleDebug PASS
- APK archive integrity PASS

## Device status

CP171 has not yet been visually inspected on Android hardware.
The previously proven G266-compatible runtime path remains the current physical-device baseline.

No C4 cognitive laws or checkpoint knowledge were changed.
