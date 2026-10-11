"""Strict research-only G29 + separate G30C read-only test checkpoint.
Do not claim this is the approved CODE_UPGRADE into canonical knowledge.
"""
import json, os, hashlib, zipfile, tempfile
from pathlib import Path
SCHEMA='C4M_G29_G30C_G30D_DIALOGUE_LAB_V1'
REQUIRED=('organism/snapshot.json','organism/journal.jsonl','lab/g29_semantic_index.json',
          'lab/g30c_extended_state.json','lab/g30c_extended_host_evidence.json','lab/g30d_pragmatics.json')

def digest(b):return hashlib.sha256(b).hexdigest()

def verified_read(z):
    m=json.loads(z.read('manifest.json'))
    if m.get('schema')!=SCHEMA:raise ValueError('SCHEMA_NOT_G29_G30C_LIVE_LAB')
    raw={}
    for key in REQUIRED:
        b=z.read(key)
        if digest(b)!=m.get('files',{}).get(key):raise ValueError('DIGEST_MISMATCH:'+key)
        raw[key]=b
    snap=json.loads(raw['organism/snapshot.json'])
    if snap.get('journal_len')!=m.get('journal_len') or snap.get('journal_head')!=m.get('journal_head'):
        raise ValueError('SNAPSHOT_HEAD_INCONSISTENT')
    from .c4life.journal import rec_hash,GENESIS
    prev=GENESIS
    for i,line in enumerate(raw['organism/journal.jsonl'].splitlines()):
        r=json.loads(line)
        if r.get('seq')!=i or r.get('prev')!=prev or rec_hash(prev,r)!=r.get('hash'):
            raise ValueError('JOURNAL_CHAIN_FAIL_AT:'+str(i))
        prev=r['hash']
    if i+1 != snap['journal_len'] or prev!=snap['journal_head']:
        raise ValueError('JOURNAL_MISMATCH')
    return m,raw

class G29Graph:
    def __init__(self,home,metadata,lab_payload,pragmatics_state):
        self.home=home;self.metadata=metadata;self.lab_payload=lab_payload
        self.pragmatics_state=pragmatics_state;self.life=None;self.lab=None;self.pragmatics=None

def load_c4m_compact(path,with_runtime=False,**kw):
    with zipfile.ZipFile(path) as z:m,raw=verified_read(z)
    home=tempfile.mkdtemp(prefix='c4g30c_lab_',dir=os.path.dirname(os.path.abspath(path)))
    for internal,dest in [('organism/snapshot.json','snapshot.json'),('organism/journal.jsonl','journal.jsonl')]:
        Path(home,dest).write_bytes(raw[internal])
    payload=tuple(json.loads(raw[key]) for key in (REQUIRED[2],REQUIRED[4],REQUIRED[3]))
    g=G29Graph(home,m,payload,json.loads(raw['lab/g30d_pragmatics.json']))
    state={'schema':SCHEMA,'step':m.get('world_t',0),'journal_len':m.get('journal_len')}
    if with_runtime:return g,None,m,state
    return g,None,m

def load_c4m(path,with_runtime=False,**kw):return load_c4m_compact(path,with_runtime=with_runtime,**kw)

def save_c4m_compact(path,g,h3=None,meta=None,runtime_state=None,include_cold=True,**kw):
    if not isinstance(g,G29Graph) or g.life is None or g.lab is None or g.pragmatics is None:raise ValueError('RUNTIME_NOT_BOUND')
    g.life.snapshot()
    index,observations,state=g.lab.memory_state()
    raw={
      'organism/snapshot.json':Path(g.home,'snapshot.json').read_bytes(),
      'organism/journal.jsonl':Path(g.home,'journal.jsonl').read_bytes(),
      'lab/g29_semantic_index.json':json.dumps(index,ensure_ascii=False,sort_keys=True).encode('utf8'),
      'lab/g30c_extended_state.json':json.dumps(state,ensure_ascii=False,sort_keys=True).encode('utf8'),
      'lab/g30c_extended_host_evidence.json':json.dumps(observations,ensure_ascii=False,sort_keys=True).encode('utf8'),
      'lab/g30d_pragmatics.json':json.dumps(g.pragmatics.state(),ensure_ascii=False,sort_keys=True).encode('utf8')}
    snap=json.loads(raw['organism/snapshot.json'])
    m={'schema':SCHEMA,'organismId':'c4-g29-and-g30c-separated-live-research',
       'researchOnly':True,'g30cMergedIntoG29':False,'g30dProvenanceOnlyDialogue':True,
       'world_t':int(g.life.world_t),'journal_len':snap['journal_len'],
       'journal_head':snap['journal_head'], 'files':{key:digest(blob) for key,blob in raw.items()},
       'originalG29Life':'G2.9 2026-10-11', 'originalG30CLanguage':'G3.0C 2026-10-11'}
    tmp=path+'.writing'
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('manifest.json',json.dumps(m,ensure_ascii=False,sort_keys=True))
        for key,val in raw.items():z.writestr(key,val)
    with zipfile.ZipFile(tmp) as z:verified_read(z)
    os.replace(tmp,path)
    return m
