"""Host ABI registry. Imported profiles authorize source identity, never cognition.
A matching digest is integrity/identity, not proof of semantic correctness.
"""
import json
from pathlib import Path
from c4_research_host import atomic
ADAPTER='g29-research-host-v1'

def validate(p):
    if p.get('adapter',ADAPTER)!=ADAPTER:raise ValueError('UNSUPPORTED_HOST_ADAPTER')
    if p.get('profileVersion',1)!=1:raise ValueError('UNSUPPORTED_PROFILE_VERSION')
    if not all(isinstance(p.get(k),str) and p[k] for k in ('abi','schema')):raise ValueError('PROFILE_ABI_SCHEMA_REQUIRED')
    files=p.get('files')
    if not isinstance(files,dict) or not 1<=len(files)<=500:raise ValueError('INVALID_PROFILE_FILES')
    for name,digest in files.items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or not name.startswith('c4child/') or not name.endswith('.py'):raise ValueError('UNSAFE_PROFILE_PATH')
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('INVALID_PROFILE_DIGEST')
    for required in ('c4child/__init__.py','c4child/runtime.py','c4child/checkpoint.py'):
        if required not in files:raise ValueError('PROFILE_MISSING_ENTRYPOINT:'+required)
    return {**p,'adapter':ADAPTER,'profileVersion':1}

def all_profiles(home):
    base=Path(__file__).parent
    profiles=[{**validate(json.loads(p.read_text())), 'profileOrigin':'BUNDLED_REVIEWED'} for p in sorted((base/'profiles').glob('*.json'))]
    user=Path(home)/'c4_abi_profiles.json'
    if user.exists():profiles.extend({**validate(p),'profileOrigin':'USER_IMPORTED'} for p in json.loads(user.read_text()))
    return profiles

def resolve(files,home):
    matches=[p for p in all_profiles(home) if p['files']==files]
    if not matches:raise ValueError('UNSUPPORTED_RUNTIME_BUILD: import a developer ABI profile for this exact source, or use a bundled runtime')
    if any((p['schema'],p['abi'])!=(matches[0]['schema'],matches[0]['abi']) for p in matches):raise ValueError('CONFLICTING_ABI_PROFILES')
    return matches[0]

def register(path,home):
    raw=Path(path).read_bytes()
    if len(raw)>1048576:raise ValueError('PROFILE_TOO_LARGE')
    p=validate(json.loads(raw));store=Path(home)/'c4_abi_profiles.json'
    prior=json.loads(store.read_text()) if store.exists() else []
    for old in all_profiles(home):
        if old['files']==p['files']:
            if (old['abi'],old['schema'])!=(p['abi'],p['schema']):raise ValueError('CONFLICTING_ABI_PROFILES')
            return p
    if len(prior)>=64:raise ValueError('PROFILE_REGISTRY_LIMIT')
    atomic(store,json.dumps(prior+[p],sort_keys=True).encode())
    return p
