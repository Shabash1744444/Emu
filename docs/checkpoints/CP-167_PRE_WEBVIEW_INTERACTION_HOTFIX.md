# CP-167 — PRE WEBVIEW INTERACTION HOTFIX

Date: 2026-10-07
Parent: CP-166 embodied chat green
Status: PRE

Observed physical symptom:
- UI renders, but buttons do not respond.

Root cause found in WebView JavaScript:
- collection operations (.forEach / indexed collection use) were invoked through the single-element helper $() in several legacy paths;
- initial render reaches renderHeldObject(), where $('#dropTargets button').forEach(...) throws at runtime;
- script execution stops before later click handlers are registered.

Hotfix scope:
- replace all collection-intended $() calls with $$();
- fix retinal preview cell collection;
- add a CI lint which rejects single-element $().forEach collection misuse;
- rebuild as 0.47-interaction-hotfix.

No C4 cognition/runtime laws are changed.
