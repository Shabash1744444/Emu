import json, os, sys, zipfile, shutil, importlib
_runtime=None
_runtime_root=None

def _purge_c4child():
    for name in list(sys.modules):
        if name=="c4child" or name.startswith("c4child."):
            sys.modules.pop(name,None)

def configure(home):
    global _runtime_root
    dest=os.path.join(home,"c4_runtime")
    if os.path.isfile(os.path.join(dest,"c4child","runtime.py")):
        _runtime_root=dest
        if dest not in sys.path: sys.path.insert(0,dest)
        return json.dumps({"ready":True,"root":dest})
    _runtime_root=None
    return json.dumps({"ready":False})

def install_runtime(zip_path, home):
    global _runtime, _runtime_root
    _runtime=None
    dest=os.path.join(home,"c4_runtime")
    tmp=dest+".tmp"
    shutil.rmtree(tmp,ignore_errors=True); os.makedirs(tmp,exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        names=z.namelist()
        hits=[n for n in names if n.endswith("c4child/runtime.py")]
        if not hits: raise RuntimeError("C4CHILD_RUNTIME_NOT_FOUND")
        prefix=hits[0][:-len("c4child/runtime.py")]
        for n in names:
            if n.startswith(prefix+"c4child/") and not n.endswith("/") and n.endswith(".py"):
                rel=n[len(prefix):]; out=os.path.join(tmp,rel)
                os.makedirs(os.path.dirname(out),exist_ok=True)
                with z.open(n) as src, open(out,"wb") as dst: shutil.copyfileobj(src,dst)
    if not os.path.isfile(os.path.join(tmp,"c4child","__init__.py")):
        raise RuntimeError("C4CHILD_PACKAGE_INCOMPLETE")
    shutil.rmtree(dest,ignore_errors=True); os.replace(tmp,dest)
    _purge_c4child()
    _runtime_root=dest
    if dest not in sys.path: sys.path.insert(0,dest)
    importlib.invalidate_caches()
    pkg=importlib.import_module("c4child")
    required=("C4LivingRuntime","C4ChildDialogue")
    missing=[x for x in required if not hasattr(pkg,x)]
    if missing: raise RuntimeError("RUNTIME_API_MISSING:"+",".join(missing))
    return json.dumps({"installed":True,"root":dest,"api":"C4_LIVING_RUNTIME","override":True})

def _load_checkpoint(path):
    import c4child.checkpoint as cp
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read("manifest.json"))
    schema=str(manifest.get("schema",""))
    if schema=="C4M_CHILD_V0.4_COMPACT":
        loader=getattr(cp,"load_c4m_compact",None)
        if loader is None: raise RuntimeError("COMPACT_LOADER_NOT_AVAILABLE")
        g,h,m,rs=loader(path,with_runtime=True)
    else:
        loader=getattr(cp,"load_c4m",None)
        if loader is None: raise RuntimeError("LOAD_C4M_NOT_FOUND")
        g,h,m,rs=loader(path,with_runtime=True)
    return schema,g,h,m,rs

def open_organism(path):
    global _runtime
    if not _runtime_root: raise RuntimeError("RUNTIME_PACKAGE_NOT_INSTALLED")
    importlib.invalidate_caches()
    pkg=importlib.import_module("c4child")
    schema,g,h,manifest,rs=_load_checkpoint(path)
    dialogue=pkg.C4ChildDialogue(g)
    _runtime=pkg.C4LivingRuntime(dialogue)
    if rs:
        _runtime.load_runtime_state(rs)
    state=_runtime.runtime_state()
    return json.dumps({"running":True,"schema":schema,"manifestSchema":manifest.get("schema"),"state":state},ensure_ascii=False,default=str)

def command(type_, payload_json):
    if _runtime is None: return json.dumps({"accepted":False,"error":"RUNTIME_NOT_RUNNING"})
    p=json.loads(payload_json or "{}")
    if type_=="USER_MESSAGE":
        out=_runtime.user_message(str(p.get("text","")))
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
