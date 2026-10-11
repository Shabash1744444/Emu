from pathlib import Path
import re, subprocess, tempfile
html=Path('app/src/main/assets/index.html').read_text()
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'ui.js';p.write_text('\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',html,re.S)))
 subprocess.run(['node','--check',str(p)],check=True)
 assert 'function runtimeSend(' in p.read_text(), 'runtimeSend calls need a definition'
 assert "type==='DIAGNOSTIC'" in p.read_text(), 'research diagnostics need their own lane'
 assert 'isNativeGeneratedSpeech===false' in p.read_text()
 print('UI JAVASCRIPT PASS')
