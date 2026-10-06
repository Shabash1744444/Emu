# CP-126 — ASYNC SOURCE PIPELINE + TRUTHFUL RUNTIME UI

Accepted build evidence:
- #30 causal mechanics: SUCCESS.
- #31 bounded chunk reader + SHA identity implementation: SUCCESS.
- #32 attachment source inspection UI: SUCCESS.

Hardening:
- expensive SHA-256 scan moved from synchronous JS bridge call to background thread;
- native SOURCE_INSPECTED_NATIVE callback returns identity/error;
- first chunk remains bounded to 64 KiB in current UI;
- host refuses digest scan beyond 256 MiB in mobile v1;
- source cards distinguish received vs identified;
- top runtime status no longer claims AWAKE/Bodrstvuet without core;
- when c4Transport=false UI says Host ready / C4 not connected.

Pending build gate at checkpoint:
- async source commits #34/#35 and truthful-status commit after them.
