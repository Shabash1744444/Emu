# CP-121 — MOBILE MEDIA VERTICAL SLICE

Implemented after CP-120:
- capability registry exposed by Android host;
- ACTION_OPEN_DOCUMENT file selection with best-effort persistable URI grant;
- camera capture through MediaStore content URI;
- microphone permission-on-use and AAC/M4A recording;
- media host callbacks via typed C4HostEvent;
- chat attachment UI appears only for host-advertised capabilities;
- attachment enters durable app journal only after ATTACHMENT_READY host receipt;
- MediaProjection one-shot screen capture implemented to internal PNG;
- cancelled camera cleans reserved MediaStore URI;
- recording stops on onPause;
- no fake C4 response/competence/learning signal introduced.

Build evidence:
- run #12 (native file/camera/mic host): SUCCESS.
- screen-capture commits #15/#16 pending at checkpoint time; must reach green before live-screen work is accepted.

Next macroblock:
foreground live screen session + bounded sampler + lifecycle receipts; then C4 transport boundary.
