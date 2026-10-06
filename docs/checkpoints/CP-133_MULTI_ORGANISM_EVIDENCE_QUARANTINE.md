# CP-133 — MULTI-ORGANISM BAY + EVIDENCE QUARANTINE

Completed macroiteration:
- content-addressed organism store: organisms/store/<sha256>.c4m;
- duplicate imports deduplicate by digest;
- installed organisms survive switching;
- native listOrganisms() enumerates actual files;
- activateOrganism(sha) selects an installed organism;
- System UI lists installed states and active selection;
- organism mutation is refused while a future runtime_running session owns state;
- recovery diagnostics expose active/temp state;
- C4_EVIDENCE_ENVELOPE_V1 reserves provenance quarantine compatible with G156 and G157-G161 direction;
- DERIVED/C4_SELF/REPLAY/SIMULATION cannot be silently promoted to independent evidence by UI.

Build gates already passed for native store/enumeration commits (#61-63). Remaining current commits must pass hardened APK verification before acceptance.

Next macroiteration:
- reconcile recovery temp/private registry at process start;
- source private spool + digest registry for all media;
- typed runtime adapter/service boundary;
- transactional UI state helper;
- build/download/hash gate.
