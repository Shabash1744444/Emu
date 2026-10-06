# CP-122 — SCREEN CAPTURE COMPILE REPAIR

Failure isolated from GitHub Actions run #15:
- javac illegal character '\\' at MainActivity.java line 32.
- cause: patch inserted literal backslash-n between two @JavascriptInterface methods.
- no architectural/media API failure observed before javac.

Repair:
- literal \\n replaced by a real source newline.
- commit f1cf07a980f9d3ecc78a992665057541001d6719.
- run #18 started; screen capture is not accepted until this run is green.

Rollback-safe known green: run #14, file/camera/microphone + attachment UI.
