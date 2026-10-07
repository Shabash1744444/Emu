# CP-172 — VISUAL AVATAR LAYER GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 0dc4f365d72f422a48aa703d359ae95ebfbf659b

## Goal

Replace the geometric debug body with a high-quality visual-avatar lane without breaking C4 agency.

## Implemented

### Android visual asset lane
- SAF import for image/webp, image/png, image/jpeg
- private app storage
- SHA-256
- filename / MIME / bytes / width / height metadata
- 12 MiB cap
- avatarInfo()
- avatarDataUrl()
- pickAvatarAsset()
- clearAvatarAsset()

### Home renderer
- PHOTO_ANIME_LAYER_V1 primary visual body
- old CSS body is fallback/debug only
- visual avatar can be touched through the existing TOUCH sensory lane
- visual body is animated only after verified motor receipts

Receipt-driven visual projections:
- WAVE
- NOD
- LOOK_AROUND
- STEP_LEFT
- STEP_RIGHT
- TAKE / GRASP / RELEASE / PLACE / MOVE / LOOK -> reach projection
- IDLE / breathing presentation

## Boundaries

VISUAL_ASSET != COGNITION
ANIMATION != INTENTION
USER APPEARANCE CHOICE != USER MOTOR CONTROL
ACTION_REQUEST != VERIFIED_OUTCOME

The user may choose appearance.
The user may not puppet C4.

## Next renderer target

C4_VISUAL_AVATAR_V2:
- VRM / GLB candidate import
- skeletal renderer
- facial blendshapes
- gaze
- mouth/voice coupling
- hair/accessory physics
- mobile LOD
- C4 motor receipt -> animation state machine

## Release

- versionCode 52
- versionName 0.52-visual-avatar
- GitHub Actions run #336 SUCCESS
- artifact ID 11478796668

Artifact ZIP:
- 33,823,656 bytes
- SHA256 9846535f34c3a23e4ae7385dddc19645a503f65c42a05a340bcbc8496747ca9c

APK:
- 33,823,238 bytes
- SHA256 1b8639225408a191b19c8e61b4601af81a155ff4095be0d31d07265cdb0790a5
- unzip integrity PASS

## Device gate

Visual-avatar import/render is not yet physically inspected on Android hardware.
The compatible G266 runtime path remains the current proven organism boot baseline.
