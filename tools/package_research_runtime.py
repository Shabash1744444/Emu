from pathlib import Path
import zipfile,json,hashlib
root=Path('payload/research_runtime');profile=json.loads(Path('app/src/main/python/c4_runtime_profile.json').read_text())
files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*.py')}
assert files==profile['files'], 'upstream runtime modified'
Path('release').mkdir(exist_ok=True)
with zipfile.ZipFile('release/C4_G29_G30C_G30D_EMU_RUNTIME_2026-10-11.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(root.rglob('*.py')):z.write(p,p.relative_to(root))
print('EXACT UPSTREAM PYTHON SOURCES VERIFIED',len(files))
