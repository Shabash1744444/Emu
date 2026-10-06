# CP-148-PRE — MOVE ROOM EXECUTION AUTHORITY NATIVE

Date: 2026-10-06

Starting point:
CP-147 / build #120 green.

Goal:
Move C4-originated room action validation and execution authority from WebView JavaScript into Android host. WebView remains presentation and state projection only.

Invariants:
- ACTION_REQUEST != VERIFIED_OUTCOME.
- UI cannot declare execution success.
- Duplicate requestId must not mutate world twice.
- Host receipt must preserve requestId and before/after world facts.
- No generation-specific C4 code.

Planned microsteps:
1. Native persistent room registry + action verifier/executor.
2. JavaScript ACTION_REQUEST delegates to native executor.
3. UI projects native receipt into room state/animation.
4. Build gate + post checkpoint.
