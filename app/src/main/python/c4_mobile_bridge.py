import json, os, sys, zipfile, shutil, importlib
_runtime=None
_runtime_root=None

def install_runtime(zip_path, home):
    global _runtime, _runtime_root
    dest=os.path.join(home,"c4_runtime")
    tmp=dest+".tmp"
    shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp,exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        names=z.namelist()
        hits=[n for n in names if n.endswith("c4child/runtime.py")]
        if not hits: raise RuntimeError("C4CHILD_RUNTIME_NOT_FOUND")
        prefix=hits[0][:-len("c4child/runtime.py")]
        for n in names:
            if n.startswith(prefix+"c4child/") and not n.endswith("/"):
                rel=n[len(prefix):]; out=os.path.join(tmp,rel)
                os.makedirs(os.path.dirname(out),exist_ok=True)
                with z.open(n) as src, open(out,"wb") as dst: shutil.copyfileobj(src,dst)
    shutil.rmtree(dest,ignore_errors=True); os.replace(tmp,dest)
    _runtime_root=dest
    if dest not in sys.path: sys.path.insert(0,dest)
    return json.dumps({"installed":True,"root":dest})

def open_organism(path):
    global _runtime
    if not _runtime_root: raise RuntimeError("RUNTIME_PACKAGE_NOT_INSTALLED")
    importlib.invalidate_caches()
    pkg=importlib.import_module("c4child")
    loader=getattr(pkg,"load_c4m",None)
    if loader is None:
        rtmod=importlib.import_module("c4child.runtime")
        loader=getattr(rtmod,"load_c4m",None)
    if loader is None: raise RuntimeError("LOAD_C4M_NOT_FOUND")
    obj=loader(path)
    cls=getattr(pkg,"C4LivingRuntime",None)
    if cls is None: cls=getattr(importlib.import_module("c4child.runtime"),"C4LivingRuntime")
    try: _runtime=cls(obj)
    except TypeError: _runtime=cls(organism=obj)
    return json.dumps({"running":True,"state":_runtime.runtime_state()})

def command(type_, payload_json):
    if _runtime is None: return json.dumps({"accepted":False,"error":"RUNTIME_NOT_RUNNING"})
    p=json.loads(payload_json or "{}")
    if type_=="USER_MESSAGE":
        out=_runtime.user_message(p.get("text",""))
    elif type_=="TICK":
        out=_runtime.tick(int(p.get("n",1)))
    elif type_=="POLL":
        out=_runtime.poll(int(p.get("limit",100)))
    else:
        return json.dumps({"accepted":False,"error":"PY_COMMAND_UNSUPPORTED"})
    events=_runtime.poll(100) if type_!="POLL" else out
    return json.dumps({"accepted":True,"result":out,"events":events,"state":_runtime.runtime_state()},ensure_ascii=False,default=str)

def state():
    return json.dumps(_runtime.runtime_state() if _runtime else {"state":"STOPPED"},ensure_ascii=False,default=str)

def close():
    global _runtime
    _runtime=None
    return json.dumps({"closed":True})
