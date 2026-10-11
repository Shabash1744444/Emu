import json, os, sys, zipfile, shutil, importlib, base64, traceback, hashlib
from pathlib import Path
from c4_research_host import ResearchHost, atomic, sha
import threading, inspect
import c4_abi_profiles as profiles
_lock=threading.RLock()
_runtime=None
_runtime_root=None
_checkpoint_path=None
_h3=None
_manifest_meta={}
_last_saved_step=0
_research=None
_runtime_build=None
_profiles_home=None
_profile=json.loads(Path(__file__).with_name("c4_runtime_profile.json").read_text())

def _purge_c4child():
    for name in list(sys.modules):
        if name=="c4child" or name.startswith("c4child."):
            sys.modules.pop(name,None)

def configure(home):
    global _runtime_root,_runtime_build,_profile,_profiles_home
    _profiles_home=home
    dest=os.path.join(home,"c4_runtime")
    if not os.path.isdir(dest) and os.path.isdir(dest+".previous"):
        os.replace(dest+".previous",dest)
    if os.path.isfile(os.path.join(dest,"c4child","runtime.py")):
        build,files=_code_build(dest)
        try:_profile=profiles.resolve(files,home)
        except ValueError as e:
            _runtime_root=None
            return json.dumps({"ready":False,"error":str(e)})
        _runtime_root=dest;_runtime_build=build
        if dest not in sys.path:sys.path.insert(0,dest)
        return json.dumps({"ready":True,"root":dest,"buildSha256":build,"abi":_profile["abi"]})
    _runtime_root=None
    return json.dumps({"ready":False})

def _code_build(root):
    files={p.relative_to(root).as_posix():sha(p.read_bytes()) for p in Path(root).rglob("*.py")}
    return sha(json.dumps(files,sort_keys=True).encode()),files

def install_runtime(zip_path, home):
    global _runtime_root, _runtime_build, _profile, _profiles_home
    if _runtime is not None or _research is not None:
        raise RuntimeError("STOP_LIFE_BEFORE_RUNTIME_INSTALL")
    dest=os.path.join(home,"c4_runtime");tmp=dest+".tmp"
    shutil.rmtree(tmp,ignore_errors=True);os.makedirs(tmp,exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        hits=[n for n in z.namelist() if n.endswith("c4child/runtime.py")]
        if len(hits)!=1:raise RuntimeError("AMBIGUOUS_OR_MISSING_RUNTIME")
        prefix=hits[0][:-len("c4child/runtime.py")]
        count=0;total=0;seen=set()
        for info in z.infolist():
            n=info.filename
            if not n.startswith(prefix+"c4child/") or not n.endswith(".py"):continue
            rel=Path(n[len(prefix):])
            if rel.is_absolute() or ".." in rel.parts:raise RuntimeError("UNSAFE_ZIP_PATH")
            if rel.as_posix() in seen:raise RuntimeError("DUPLICATE_RUNTIME_SOURCE")
            seen.add(rel.as_posix())
            count+=1;total+=info.file_size
            if total>16777216 or count>500:raise RuntimeError("RUNTIME_ZIP_LIMIT")
            out=Path(tmp)/rel;out.parent.mkdir(parents=True,exist_ok=True)
            atomic(out,z.read(info))
    build,files=_code_build(tmp)
    try:selected=profiles.resolve(files,home)
    except ValueError as e:
        shutil.rmtree(tmp)
        raise RuntimeError(str(e)) from e
    atomic(Path(tmp)/"host_abi.json",json.dumps({"buildSha256":build,"abi":selected["abi"],"schema":selected["schema"]}).encode())
    backup=dest+".previous"
    shutil.rmtree(backup,ignore_errors=True)
    if os.path.isdir(dest):os.replace(dest,backup)
    try:os.replace(tmp,dest)
    except Exception:
        if os.path.isdir(backup):os.replace(backup,dest)
        raise
    _purge_c4child();_runtime_root=dest;_runtime_build=build;_profile=selected;_profiles_home=home
    # Remove the old sys.path entry to avoid importing an older runtime.
    sys.path[:]=[x for x in sys.path if x!=dest and not x.endswith("/c4_runtime.tmp")]
    sys.path.insert(0,dest);importlib.invalidate_caches()
    return json.dumps({"installed":True,"ready":False,"requiresOrganismHandshake":True,
        "root":dest,"buildSha256":build,"abi":_profile["abi"],"schema":_profile["schema"]})


def _verify_contract(pkg):
    cp=importlib.import_module('c4child.checkpoint')
    if cp.SCHEMA!=_profile['schema']:raise RuntimeError('ABI_SCHEMA_SOURCE_MISMATCH')
    for name in ('load_c4m_compact','save_c4m_compact','G29Graph'):
        if not callable(getattr(cp,name,None)):raise RuntimeError('UNSUPPORTED_SERIALIZATION_API:'+name)
    params=list(inspect.signature(cp.G29Graph).parameters)
    if params not in [['home','metadata','lab_payload','pragmatics_state'],['home','metadata','lab_payload','pragmatics_state','binding_state']]:
        raise RuntimeError('UNSUPPORTED_STATE_COMPONENT_CONTRACT:'+repr(params))
    for name in ('user_message','tick','poll','runtime_state','load_runtime_state'):
        if not callable(getattr(pkg.C4LivingRuntime,name,None)):raise RuntimeError('UNSUPPORTED_RUNTIME_API:'+name)

def compatibility():
    return {'adapter':profiles.ADAPTER,'abi':_profile['abi'],'schema':_profile['schema'],
        'profileOrigin':_profile.get('profileOrigin','BUNDLED_REVIEWED'),
        'runtimeBuildSha256':_runtime_build,'supportedCommands':['USER_MESSAGE','TICK','POLL'],
        'worldEvent':'UNSUPPORTED','newAbiRequiresAdapter':True}

def register_runtime_profile(path,home):
    if _runtime is not None or _research is not None:raise RuntimeError('STOP_LIFE_BEFORE_PROFILE_IMPORT')
    p=profiles.register(path,home)
    ready=json.loads(configure(home))
    return json.dumps({'registered':True,'abi':p['abi'],'schema':p['schema'],
        'profileOrigin':'USER_IMPORTED','runtimeReady':ready.get('ready',False)})

def _boot_diagnostic_payload(code, exc=None, path=None):
    detail = str(exc) if exc is not None else ""
    result = {"running": False, "errorCode": code, "errorDetail": detail,
              "traceback": traceback.format_exc() if exc is not None else "",
              "runtimeRoot": _runtime_root, "organismPath": path, "runtimeBuildSha256": _runtime_build,
              "abi": _profile["abi"], "expectedSchema":_profile["schema"]}
    try:
        if _runtime_root and os.path.isfile(os.path.join(_runtime_root,"c4child","runtime.py")):
            with open(os.path.join(_runtime_root,"c4child","runtime.py"),"rb") as source:
                result["runtimeCodeSha256"] = hashlib.sha256(source.read()).hexdigest()
        if path and os.path.isfile(path):
            result["organismSha256"]=sha(Path(path).read_bytes())
            with zipfile.ZipFile(path) as archive:
                m = json.loads(archive.read("manifest.json"))
            result["organismSchema"] = m.get("schema")
            result["organismId"] = m.get("organismId")
        if _runtime_root and os.path.isdir(_runtime_root):
            target = os.path.join(_runtime_root, "last_boot_diagnostic.json")
            temp = target + ".tmp"
            with open(temp, "w", encoding="utf-8") as output:
                json.dump(result, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, target)
    except Exception as diag_exc:
        result["diagnosticCaptureError"] = repr(diag_exc)
    return result

def last_boot_diagnostic():
    if not _runtime_root:
        return json.dumps({"available":False},ensure_ascii=False)
    name = os.path.join(_runtime_root,"last_boot_diagnostic.json")
    if not os.path.isfile(name):
        return json.dumps({"available":False},ensure_ascii=False)
    with open(name,encoding="utf-8") as source:
        return source.read()

def open_organism(path):
    global _runtime,_checkpoint_path,_h3,_manifest_meta,_last_saved_step,_research
    if _runtime is not None or _research is not None:
        return json.dumps({"running":False,"errorCode":"LIFE_ALREADY_RUNNING"})
    _runtime = None
    if not _runtime_root:
        return json.dumps(_boot_diagnostic_payload("RUNTIME_PACKAGE_NOT_INSTALLED",path=path),ensure_ascii=False)
    try:
        importlib.invalidate_caches()
        pkg = importlib.import_module("c4child")
        with zipfile.ZipFile(path) as archive:
            schema=json.loads(archive.read("manifest.json")).get("schema")
        if schema==_profile["schema"]:
            build,files=_code_build(_runtime_root)
            if files!=_profile["files"]:raise RuntimeError("RUNTIME_BUILD_CHANGED")
            _verify_contract(pkg)
            _research=ResearchHost(path,build,pkg)
            _runtime=_research.runtime;_checkpoint_path=path
            result={"running":True,"schema":schema,"state":_research.state(),"compatibility":compatibility()}
            atomic(Path(_runtime_root)/"last_boot_diagnostic.json",json.dumps(result,ensure_ascii=False).encode())
            return json.dumps(result,ensure_ascii=False)
        raise RuntimeError("UNSUPPORTED_ORGANISM_SCHEMA:"+str(schema))
    except Exception as exc:
        _runtime = None
        _research = None
        return json.dumps(_boot_diagnostic_payload("PY_RUNTIME_BOOT_FAILURE",exc,path),ensure_ascii=False,default=str)

def checkpoint():
    if _research is None:return json.dumps({"saved":False,"error":"RUNTIME_NOT_RUNNING"})
    return json.dumps(_research.checkpoint(),ensure_ascii=False)

def command(type_, payload_json):
    if _research is None:return json.dumps({"accepted":False,"error":"RUNTIME_NOT_RUNNING"})
    try:
        return json.dumps(_research.command(type_,json.loads(payload_json or "{}")),ensure_ascii=False)
    except Exception as exc:
        return json.dumps(dict(_boot_diagnostic_payload("PY_RUNTIME_OPERATION_FAILURE",exc,_checkpoint_path),accepted=False),ensure_ascii=False)

def state():
    return json.dumps(_research.state() if _research else (_runtime.runtime_state() if _runtime else {"state":"STOPPED"}),ensure_ascii=False,default=str)

def export_organism(destination):
    if _research is None:return json.dumps({'exported':False,'error':'RUNTIME_NOT_RUNNING'})
    return json.dumps(_research.export(destination),ensure_ascii=False)

def close():
    global _runtime,_research
    if _research is not None:_research.close()
    _runtime=None;_research=None
    return json.dumps({"closed":True})


def _serialized(fn):
    def call(*args,**kwargs):
        with _lock:return fn(*args,**kwargs)
    return call
for _name in ("configure","install_runtime","open_organism","checkpoint","command","state","close","export_organism","last_boot_diagnostic","register_runtime_profile"):
    globals()[_name]=_serialized(globals()[_name])
