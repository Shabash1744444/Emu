"""C004 host-trust boundary: WebView cannot impersonate a C4 DRIVE request.
A static structural test; separate from on-device behavioral attestation.
"""
from pathlib import Path
import re

java=Path("app/src/main/java/com/singularity/c4nursery/MainActivity.java").read_text(encoding="utf-8")
public=re.search(
    r'@JavascriptInterface\s+public String executeRoomAction\(String json\)\s*\{([\s\S]*?)\n\s*\}\s*private String executeRoomActionTrusted',
    java,
)
assert public, "Public WebView room executor and private native room executor must be separate methods"
body=public.group(1)
assert 'requestId.startsWith("trial:")' in body, "C4-owned IDs must be blocked from WebView"
assert 'req.optString("requestId","").trim()' in body, "Reject trial IDs after the same normalization as the private executor"
assert '"C4_HOST_OWNED_REQUEST_ID"' in body, "Rejection must be visible, not silent"
assert 'return executeRoomActionTrusted(json);' in body, "Ordinary UI game commands must retain executor"
assert 'private String executeRoomActionTrusted(String json)' in java
assert 'c4NativeHostBridge.executeRoomActionTrusted(cmd.toString())' in java, "C4 Java dispatcher must use private executor"
assert 'c4NativeHostBridge.executeRoomAction(cmd.toString())' not in java
native=java.split("private String executeRoomActionTrusted(String json)",1)[0]
assert not re.search(r'@JavascriptInterface\s+private String executeRoomActionTrusted',native), "Private executor must not be exposed to JS"
assert 'pyCallHost("native_room_receipt",roomReceipt.toString(),sid)' in java, "Trusted Java receipt path required"
print("C004_PRIVATE_EXECUTOR_CONTRACT PASS")
