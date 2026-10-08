import json, os, sys, zipfile, shutil, importlib, base64
_runtime=None
_runtime_root=None
_checkpoint_path=None
_h3=None
_manifest_meta={}
_last_saved_step=0

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
    global _runtime,_checkpoint_path,_h3,_manifest_meta,_last_saved_step
    if not _runtime_root: raise RuntimeError("RUNTIME_PACKAGE_NOT_INSTALLED")
    importlib.invalidate_caches()
    pkg=importlib.import_module("c4child")
    schema,g,h,manifest,rs=_load_checkpoint(path)
    dialogue=pkg.C4ChildDialogue(g)
    _runtime=pkg.C4LivingRuntime(dialogue)
    if rs:
        _runtime.load_runtime_state(rs)
    _checkpoint_path=path
    _h3=h
    _manifest_meta=dict(manifest or {})
    state=_runtime.runtime_state()
    _last_saved_step=int(state.get("step",0)) if isinstance(state,dict) else 0
    return json.dumps({"running":True,"schema":schema,"manifestSchema":manifest.get("schema"),"state":state},ensure_ascii=False,default=str)

def checkpoint():
    global _last_saved_step
    if _runtime is None or not _checkpoint_path:
        return json.dumps({"saved":False,"error":"RUNTIME_NOT_RUNNING"})
    import c4child.checkpoint as cp
    tmp=_checkpoint_path+".save.tmp"
    state=_runtime.runtime_state()
    save_compact=getattr(cp,"save_c4m_compact",None)
    if save_compact is None: raise RuntimeError("COMPACT_SAVER_NOT_AVAILABLE")
    save_compact(tmp,_runtime.dialogue.g,h3=_h3,meta=_manifest_meta,runtime_state=state,include_cold=True)
    os.replace(tmp,_checkpoint_path)
    _last_saved_step=int(state.get("step",0))
    return json.dumps({"saved":True,"path":_checkpoint_path,"step":_last_saved_step})

def _typed_runtime_call(type_,p):
    generic=("handle_runtime_command","runtime_command")
    targets=[_runtime,getattr(_runtime,"dialogue",None)]
    last_type_error=None
    for target in targets:
        if target is None: continue
        for name in generic:
            fn=getattr(target,name,None)
            if callable(fn):
                try:
                    out=fn(type_,p)
                    return {"accepted":True,"result":out,"adapterMethod":name}
                except TypeError as e:
                    last_type_error=str(e)
    names={
        "BEGIN_SOURCE":("begin_source","source_begin"),
        "APPEND_SOURCE":("append_source","source_append"),
        "END_SOURCE":("end_source","source_end"),
        "SENSORY_SESSION_START":("sensory_session_start","start_sensory_session"),
        "SENSORY_FRAME":("sensory_frame","ingest_sensory_frame"),
        "SENSORY_SESSION_STOP":("sensory_session_stop","stop_sensory_session"),
        "ACTION_RECEIPT":("action_receipt","receive_action_receipt"),
        "WORLD_EVENT":("world_event","observe_world_event","ingest_world_event"),
        "WORLD_TASK":("world_task","accept_world_task","receive_world_task"),
        "BODY_MANIFEST":("body_manifest","set_body_manifest","capability_manifest","receive_body_manifest"),
        "TRACE_CONFIG":("trace_config","configure_trace","set_trace_config"),
        "TRACE_SNAPSHOT":("trace_snapshot","get_trace_snapshot","diagnostic_snapshot"),
    }.get(type_,())
    call_p=dict(p)
    if type_=="APPEND_SOURCE" and call_p.get("encoding")=="base64" and isinstance(call_p.get("bytes"),str):
        call_p["bytes"]=base64.b64decode(call_p["bytes"],validate=True)
        call_p.pop("encoding",None)
    for target in targets:
        if target is None: continue
        for name in names:
            fn=getattr(target,name,None)
            if not callable(fn): continue
            try:
                out=fn(call_p)
                return {"accepted":True,"result":out,"adapterMethod":name}
            except TypeError as e:
                last_type_error=str(e)
                try:
                    out=fn(**call_p)
                    return {"accepted":True,"result":out,"adapterMethod":name}
                except TypeError as e2:
                    last_type_error=str(e2)
    return {"accepted":False,"error":"RUNTIME_CAPABILITY_UNAVAILABLE","command":type_,"detail":last_type_error}

def command(type_, payload_json):
    if _runtime is None: return json.dumps({"accepted":False,"error":"RUNTIME_NOT_RUNNING"})
    p=json.loads(payload_json or "{}")
    if type_=="USER_MESSAGE":
        out=_runtime.user_message(str(p.get("text","")))
        events=_runtime.poll(100)
        return json.dumps({"accepted":True,"result":out,"events":events,"state":_runtime.runtime_state()},ensure_ascii=False,default=str)
    if type_=="TICK":
        out=_runtime.tick(int(p.get("n",1)))
        events=_runtime.poll(100)
        return json.dumps({"accepted":True,"result":out,"events":events,"state":_runtime.runtime_state()},ensure_ascii=False,default=str)
    if type_=="POLL":
        out=_runtime.poll(int(p.get("limit",100)))
        return json.dumps({"accepted":True,"result":out,"events":out,"state":_runtime.runtime_state()},ensure_ascii=False,default=str)
    if type_ in ("BEGIN_SOURCE","APPEND_SOURCE","END_SOURCE","SENSORY_SESSION_START","SENSORY_FRAME","SENSORY_SESSION_STOP","ACTION_RECEIPT","WORLD_EVENT","WORLD_TASK","BODY_MANIFEST","TRACE_CONFIG","TRACE_SNAPSHOT"):
        r=_typed_runtime_call(type_,p)
        r["events"]=_runtime.poll(100) if r.get("accepted") else []
        r["state"]=_runtime.runtime_state()
        return json.dumps(r,ensure_ascii=False,default=str)
    return json.dumps({"accepted":False,"error":"PY_COMMAND_UNSUPPORTED","command":type_})

def state():
    return json.dumps(_runtime.runtime_state() if _runtime else {"state":"STOPPED"},ensure_ascii=False,default=str)

def bind_native_room_session(session_id):
    """Native Java-only call on OPEN_SESSION; not exposed by command()."""
    if _runtime is None:
        return json.dumps({"accepted":False,"error":"RUNTIME_NOT_RUNNING"})
    return json.dumps(_runtime.bind_native_room_session(str(session_id)),ensure_ascii=False)

def native_room_receipt(receipt_json,session_id):
    """Native Java room result only; never a WebView runtime command.

    This caller is trusted to supply the receipt returned by the room executor.
    A JSON message sent through USER_MESSAGE / ACTION_RECEIPT cannot reach here.
    """
    if _runtime is None:
        return json.dumps({"accepted":False,"error":"RUNTIME_NOT_RUNNING"})
    if not isinstance(receipt_json,str) or len(receipt_json)>20000:
        return json.dumps({"accepted":False,"error":"INVALID_NATIVE_RECEIPT_SIZE"})
    try:
        receipt=json.loads(receipt_json)
        result=_runtime.native_room_receipt(receipt,str(session_id))
    except (ValueError,TypeError,KeyError) as exc:
        result={"accepted":False,"error":"NATIVE_RECEIPT_REJECTED","reason":str(exc)}
    return json.dumps(result,ensure_ascii=False,default=str)

def close():
    global _runtime
    _runtime=None
    return json.dumps({"closed":True})
