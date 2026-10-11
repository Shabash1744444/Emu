"""Prepare a developer host profile without editing/repacking the runtime ZIP.
Use only for this documented host ABI; passing hashes is not semantic validation.
"""
import argparse,ast,hashlib,json,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--abi',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
with zipfile.ZipFile(a.runtime) as z:
 names=[n for n in z.namelist() if n.endswith('c4child/runtime.py')]
 if len(names)!=1:raise SystemExit('AMBIGUOUS_RUNTIME')
 prefix=names[0][:-len('c4child/runtime.py')];files={}
 for n in z.namelist():
  if n.startswith(prefix+'c4child/') and n.endswith('.py'):
   name=n[len(prefix):]
   if '..' in Path(name).parts or name in files:raise SystemExit('UNSAFE_OR_DUPLICATE_SOURCE')
   files[name]=hashlib.sha256(z.read(n)).hexdigest()
 tree=ast.parse(z.read(prefix+'c4child/checkpoint.py').decode())
 schemas=[ast.literal_eval(x.value) for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCHEMA' for t in x.targets)]
 if len(schemas)!=1 or not isinstance(schemas[0],str):raise SystemExit('SCHEMA_CONTRACT_NOT_STATIC')
profile={'profileVersion':1,'adapter':'g29-research-host-v1','abi':a.abi,'schema':schemas[0],'files':files,'runtimeZipSha256':hashlib.sha256(a.runtime.read_bytes()).hexdigest()}
a.output.write_text(json.dumps(profile,ensure_ascii=False,sort_keys=True,indent=2)+'\n');print('PROFILE PREPARED:',len(files),'sources; runtime ZIP unchanged. Compatibility still requires boot handshake and persistence tests.')
