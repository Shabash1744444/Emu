from html.parser import HTMLParser
from pathlib import Path
import re,sys

p=Path(sys.argv[1] if len(sys.argv)>1 else 'app/src/main/assets/index.html')
s=p.read_text(encoding='utf-8')
errs=[]

class LayoutParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.pages=[]
        self.nav_targets=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if d.get('id'): self.ids.append(d['id'])
        if 'page' in (d.get('class') or '').split() and d.get('data-page'):
            self.pages.append(d['data-page'])
        if tag=='button' and d.get('data-go'):
            self.nav_targets.append(d['data-go'])

h=LayoutParser(); h.feed(s)

# Duplicate IDs are catastrophic for deterministic binding/layout.
dups=sorted({x for x in h.ids if h.ids.count(x)>1})
if dups:
    errs.append('duplicate DOM ids: '+repr(dups))

expected={'home','chat','world','library','system'}
if set(h.pages)!=expected:
    errs.append(f'page set mismatch: expected {sorted(expected)}, got {sorted(set(h.pages))}')
if set(h.nav_targets)!=expected:
    errs.append(f'bottom nav mismatch: expected {sorted(expected)}, got {sorted(set(h.nav_targets))}')
if len(h.nav_targets)!=5:
    errs.append(f'expected exactly 5 bottom-nav buttons, got {len(h.nav_targets)}')

required_markup=[
    'viewport-fit=cover',
    'interactive-widget=resizes-content',
    'id="input"',
    'id="form"',
    'class="nav"',
]
for x in required_markup:
    if x not in s: errs.append('missing layout markup contract: '+x)

required_css=[
    '/* CP185 Layout Foundation V2 */',
    '--shell-max:760px',
    '.app{\n height:var(--vvh)!important;',
    'display:flex;\n flex-direction:column;',
    '.main{\n flex:1 1 auto;',
    'overflow-x:hidden;',
    'grid-template-columns:repeat(5,minmax(0,1fr))!important;',
    'body.keyboardOpen .main{',
    'body.keyboardOpen .compose{',
    'body.layoutLandscape:not(.keyboardOpen)',
    'body.layoutCompact .nav',
    'overflow-wrap:anywhere;',
    'pointer-events:none!important;',
]
for x in required_css:
    if x not in s: errs.append('missing responsive CSS contract: '+x)

required_js=[
    "const viewportBaseline={portrait:0,landscape:0}",
    "document.body.classList.toggle('keyboardOpen',keyboard)",
    "document.body.classList.toggle('layoutLandscape',orientation==='landscape')",
    "document.body.classList.toggle('layoutCompact',w<=380)",
    "document.documentElement.style.setProperty('--vvh',h+'px')",
    "document.documentElement.style.setProperty('--vvw',w+'px')",
]
for x in required_js:
    if x not in s: errs.append('missing viewport JS contract: '+x)

# Old global-max heuristic breaks on orientation changes.
if 'let viewportMax=0' in s or "h<viewportMax*.78" in s:
    errs.append('obsolete global viewportMax keyboard heuristic still present')

# Composer must remain in the chat DOM and must not become a fixed overlay.
if re.search(r'\.compose\s*\{[^}]*position\s*:\s*fixed',s,re.S):
    errs.append('composer must not be position:fixed')
if 'body.keyboardOpen .nav{display:none!important}' not in s and 'body.keyboardOpen .nav' not in s:
    errs.append('keyboard mode must hide bottom nav')
if 'body.keyboardOpen .chatStage' not in s:
    errs.append('keyboard mode must explicitly size chat stage')

# The final layout layer must be late enough to override historical CSS.
layout_at=s.find('/* CP185 Layout Foundation V2 */')
style_end=s.rfind('</style>')
if layout_at<0 or style_end<0 or layout_at>style_end:
    errs.append('layout foundation is not inside final style block')
elif style_end-layout_at<3000:
    errs.append('layout foundation block unexpectedly short/incomplete')

if errs:
    print('LAYOUT CONTRACT FAIL')
    for e in errs: print(' -',e)
    raise SystemExit(1)

print('LAYOUT CONTRACT PASS',
      len(h.ids),'unique ids',
      len(h.pages),'pages',
      len(h.nav_targets),'nav targets')
