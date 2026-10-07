# CP-170 — AI-OWNED BODY GREEN

Date: 2026-10-07
Status: GREEN
Binary code head: 44948d6343c2f020873b01b7107281dcfce67f2b

## Ownership result

C4 owns its avatar/body.

Removed from user control:
- Wave
- direct Move Ball
- direct Take/Place/Look/GRASP/RELEASE controls

User remains an external actor:
- touch avatar
- call C4
- point/touch world objects
- present sensory/source material
- issue a sandbox challenge

These are USER_WORLD events and never become C4 motor actions by UI fiat.

## Motor execution

Only C4 ACTION_REQUEST can drive C4 motor execution.

Native bounded motor vocabulary:
- WAVE
- NOD
- LOOK_AROUND
- STEP_LEFT
- STEP_RIGHT
- IDLE
- plus bounded object actions LOOK/TAKE/PLACE/MOVE/GRASP/RELEASE

ACTION_REQUEST -> native affordance/execution -> ACTION_RECEIPT.

The requested object target is now preserved through the host bridge.

## Runtime/world capability lane

Added capability probes:
- WORLD_EVENT -> world_event / observe_world_event / ingest_world_event
- WORLD_TASK -> world_task / accept_world_task / receive_world_task

Unsupported runtimes must answer RUNTIME_CAPABILITY_UNAVAILABLE.

## UI behavior

- Home explicitly identifies C4 as body owner.
- Latest verified motor action is visible.
- Avatar animations occur only after executionSuccess=true.
- Motor receipts use room-only rendering and cannot destabilize Dialogue.
- Habitat received an additional lighting/material/depth pass.

## Build

- GitHub Actions run #313 SUCCESS
- artifact: C4-Nursery-0.50-ai-owned-body
- artifact ID: 11474260570
- artifact ZIP: 33,817,720 bytes
- artifact ZIP SHA256: 87102a271f48758c618f808279bea981d778939ae9b7e50622b752ce6a5e946a
- APK: 33,817,302 bytes
- APK SHA256: 2f4888e16aec7e518393157f7d00a6b7b089c7950ae2102378107044dd3adf3a

## Gates

- WebView JS syntax PASS
- selector regression guard PASS
- organism picker regression guard PASS
- stable-chat forced-scroll guard PASS
- AI-owned body regression guard PASS
- Python py_compile PASS
- Gradle assembleDebug PASS
- APK unzip integrity PASS

No C4 cognitive laws or checkpoint knowledge were changed.
