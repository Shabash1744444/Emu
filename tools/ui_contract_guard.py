from html.parser import HTMLParser
from pathlib import Path
import re,sys

p=Path(sys.argv[1] if len(sys.argv)>1 else 'app/src/main/assets/index.html')
s=p.read_text(encoding='utf-8')

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=set()
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if d.get('id'): self.ids.add(d['id'])

h=P(); h.feed(s)
errs=[]

# $() returns one element. Collection methods require $$().
for pat in [
    r"(?<!\$)\$\('[^'\n]*'\)\.(forEach|map|filter|slice|some|every|find)\b",
    r'(?<!\$)\$\("[^"\n]*"\)\.(forEach|map|filter|slice|some|every|find)\b',
]:
    for m in re.finditer(pat,s):
        errs.append(f'single-element $() used as collection near offset {m.start()}: {m.group(0)[:120]}')

# Direct dereference of a removed static id is a startup hazard.
for m in re.finditer(r"\$\('#([A-Za-z0-9_-]+)'\)\.([A-Za-z_$][\w$]*)",s):
    ident,prop=m.group(1),m.group(2)
    if ident not in h.ids:
        errs.append(f'direct dereference of missing DOM id #{ident}.{prop} near offset {m.start()}')

# Known TDZ/bootstrap regression.
early=s.find('};renderHomeDashboard()')
default=s.find('const DEFAULT_GLB')
if early!=-1 and default!=-1 and early<default:
    errs.append('renderHomeDashboard() executes before DEFAULT_GLB initialization')

required=[
    "$$('[data-go]').forEach",
    "$$('[data-home-go]').forEach",
    "$$('[data-world-mode]').forEach",
    "$$('[data-world-panel]').forEach",
    "$$('[data-library-filter]').forEach",
    "$$('[data-quality]').forEach",
    "$$('#organMap [data-organ]').forEach",
    "$('#runtimeStart').onclick",
    "$('#brainStartChat').onclick",
    "$('#gateRuntime').onclick",
    "$('#gateOrganism').onclick",
    "$('#gateStart').onclick",
    "$('#libraryImport').onclick",
    "$('#fileBtn').onclick",
    "$('#camBtn').onclick",
    "$('#eyeBtn').onclick",
    "$('#micBtn').onclick",
    "$('#bodyBtn').onclick",
    "$('#screenBtn').onclick",
    "$('#streamBtn').onclick",
    "$('#newGame').onclick",
    "$('#verifyGame').onclick",
    "$('#predictHit').onclick",
    "$('#predictMiss').onclick",
    "$('#forceLow').onclick",
    "$('#forceHigh').onclick",
    "$('#pushPuck').onclick",
    "$('#memoryStart').onclick",
    "$('#avatarModelPick').onclick",
    "$('#avatarModelClear').onclick",
    "$('#avatarPick').onclick",
    "$('#roomTalk').onclick",
    "$('#organismPick').onclick",
    "$('#organismClear').onclick",
    "$('#runtimePick').onclick",
    "$('#exportChat').onclick",
    "const hs=$('#homeSenses');if(hs)hs.onclick",
    "const ch=$('#chatGoHome');if(ch)ch.onclick",
    "const wnt=$('#worldNewTask');if(wnt)wnt.onclick",
    "const materialClose=$('#materialClose');if(materialClose)materialClose.onclick",
    "const materialSend=$('#materialSend');if(materialSend)materialSend.onclick",
]
for x in required:
    if x not in s: errs.append(f'missing critical UI binding: {x}')

if errs:
    print('UI CONTRACT FAIL')
    for e in errs: print(' -',e)
    raise SystemExit(1)

print('UI CONTRACT PASS',len(h.ids),'ids',len(required),'critical bindings')
