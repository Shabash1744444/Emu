# CP-164 — PRE SENSORY CORTEX / DIGITAL BODY

Date: 2026-10-06
Parent: ca1792e4d9e5965315c42a96ac45bbed5e10c584 (CP-163 brain boot green)
Status: PRE / architecture-preserving checkpoint

Goal of this macroiteration:
- stop treating microphone/camera/screen as file-attachment conveniences only;
- add a host-side non-semantic sensory cortex which converts physical signals into compact typed observations;
- wire SENSORY_SESSION_START / SENSORY_FRAME / SENSORY_SESSION_STOP through the Android -> Python runtime boundary without faking support in C4;
- preserve raw captured material in the private source store;
- keep SIGNAL != SOURCE, CAPTURED != PERCEIVED, and host feature extraction != cognition;
- add no object labels, ASR text, emotion labels, or hidden model inference.

Planned first modalities:
- AUDIO: PCM16 mono frames with timing, RMS/peak, zero-crossing rate and fixed spectral probes;
- VISION: downsampled color/luma lattice plus global light/contrast/edge measures for photo/screenshot/live-screen frames.

Acceptance gates:
- runtime absent/unsupported must be reported honestly;
- existing chat/brain boot remains functional;
- Java + Python + WebView syntax/build gates green;
- physical post-checkpoint and release artifact after successful build.
