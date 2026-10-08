# CP-186 — TRACE RECORDER RU UX GREEN

Date: 2026-10-08
Status: GREEN
Release: 0.64.3-trace-ru
versionCode: 68
Binary workflow head: 5ba06678899ab21896cb6b5b7e31a8ada23ca24f
GitHub Actions run: #489
Run ID: 37751723736

## Implemented

The trace recorder is now understandable without protocol jargon.

User-facing Russian modes:
- Выкл — cognitive trace off, technical transport log still records;
- События — light structured runtime trace;
- Решения — recommended mode for strange C4 answers/actions;
- Глубоко — maximum structured diagnostic detail.

Protocol values remain unchanged:
OFF / EVENTS / DECISIONS / DEEP.

## In-app guide

The System page now explains:
1. UI/startup/connection bug -> do not enable anything; technical log already records.
2. Strange C4 answer/decision -> enable “Решения”, reproduce, export.
3. One problematic interaction -> tap “Следующая реплика подробно”, then send exactly one message.

Buttons renamed/explained:
- Следующая реплика подробно
- Снимок состояния
- Очистить логи
- Выгрузить пакет для разбора

Clear explicitly states it does NOT delete chat, memory or .c4m.

Export explains that the bundle contains separate lanes:
- conversation
- UI diagnostics
- technical transport trace
- cognitive trace

Diagnostics remain excluded from training.

## Regression caught during build

The first RU UX build reintroduced a single-element selector bug:
$('[data-trace-mode]').forEach

The existing CP184 UI contract guard caught it before APK build.
It was corrected to collection selector:
$$('[data-trace-mode]').forEach

Repository-wide exact check:
single-element $().forEach collection misuse = 0.

This confirms the CP184 guard prevents recurrence of the dead-buttons class of bug.

## Boundaries

TRACE != EVIDENCE
TRACE != MEMORY
TRACE != TRAINING DATA
TRACE != FREE-FORM HIDDEN MONOLOGUE
DEBUG OBSERVATION MUST NOT MUTATE COGNITION

## Build verification

GitHub Actions run #489: SUCCESS
- pinned 3D/vendor assets: PASS
- WebView JavaScript syntax: PASS
- CP184 UI/bootstrap selector guard: PASS
- Russian trace UX guard: PASS
- trace protocol value preservation: PASS
- Python py_compile: PASS
- Gradle assembleDebug: PASS
- APK staging/integrity: PASS
- artifact upload: PASS

Artifact:
- C4-Nursery-0.64.3-trace-ru
- artifact ID: 11537774204
- ZIP bytes: 49,400,657
- ZIP SHA256: c4a6bd3735d6b17bae2518415e69259a3bca00ef600452e4328b881a469625fb

APK:
- bytes: 49,400,248
- SHA256: 7c287f4241e5d7441ce394334d351bf92b7dcef7c1fdec9bf6e8e5af8bc501ac

Bundled VRoid Sample D SHA256:
9adf1b44e959d2688d62c2dd558e74315d6aa40e3bf8d281390b7a85dc0df9b7

three-vrm bundle SHA256:
e2a2f07c5090b32a31bb9493ecc1209b45c8d1f23da2eb829eed9685d3ead55d

## Physical gate

- verify Russian trace card layout on the target phone;
- verify “Решения” and “Следующая реплика подробно” with a runtime that supports C4_COGNITIVE_TRACE_V1;
- verify unsupported runtime message remains understandable;
- export one diagnostic bundle and inspect all four lanes.
