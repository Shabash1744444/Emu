"""Explicitly opted-in, hash-pinned research overlay for C4 Nursery.

This is not a C4M upgrade. It loads the published G30G+R18E/R18I
linked research ZIP into app-private storage and preserves both lineages.
The imported ZIP contains Python code; only the exact reviewed digest
is allowed. No network, LLM, or fabricated dialogue.
"""
from __future__ import annotations
import hashlib
import importlib
import json
import os
import shutil
import sys
import threading
import zipfile
from pathlib import Path

BUNDLE_SHA256 = "92e01d18b44876577bb21a4b929b1a01106ba4fc0a81caa3417d3537a9cb5e08"
BUNDLE_FOLDER = "C4_G30G_R18I_LINKED_RESEARCH_RUNTIME_2026-10-12"
_lock = threading.RLock()
_engine = None
_home = None

def _status(**kw):
    return json.dumps(kw, ensure_ascii=False, default=str)

def status(home):
    global _engine
    target = Path(home) / "linked_c4" / BUNDLE_FOLDER
    return _status(installed=(target / "bridge.py").is_file(),
                   running=_engine is not None,
                   kind="LINKED_RESEARCH_R18I_NOT_MERGED",
                   zip_sha256=BUNDLE_SHA256)

def install(archive, home):
    global _engine
    with _lock:
        if _engine is not None:
            return _status(installed=False, error="STOP_LINKED_SESSION_BEFORE_INSTALL")
        path = Path(archive)
        if not path.is_file() or path.stat().st_size > 26_000_000:
            return _status(installed=False, error="BUNDLE_MISSING_OR_TOO_LARGE")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != BUNDLE_SHA256:
            return _status(installed=False, error="UNRECOGNIZED_RESEARCH_BUNDLE_SHA256", sha256=digest)
        home = Path(home)
        parent = home / "linked_c4"
        parent.mkdir(parents=True, exist_ok=True)
        tmp = parent / "pending_import"
        if tmp.exists(): shutil.rmtree(tmp)
        tmp.mkdir()
        try:
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                if len(infos) > 150 or sum(i.file_size for i in infos) > 25_000_000:
                    raise ValueError("BUNDLE_LIMIT_EXCEEDED")
                for i in infos:
                    rel = Path(i.filename)
                    if rel.is_absolute() or ".." in rel.parts or rel.parts[0] != BUNDLE_FOLDER:
                        raise ValueError("UNSAFE_MEMBER_NAME")
                    # Reject symlink entries even though the archive is hash-pinned.
                    if ((i.external_attr >> 16) & 0o170000) == 0o120000:
                        raise ValueError("SYMLINK_REJECTED")
                    if i.is_dir():continue
                    target = tmp / rel
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(i) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src,dst,1024*1024)
            root = tmp / BUNDLE_FOLDER
            if not (root / "bridge.py").is_file() or not (root / "integrity_manifest.json").is_file():
                raise ValueError("BUNDLE_ABI_INVALID")
            manifests = json.loads((root / "integrity_manifest.json").read_text("utf-8"))["files"]
            for name, expected in manifests.items():
                f = root / name
                if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=expected:
                    raise ValueError("BUNDLE_INTEGRITY_FAIL:" + name)
            target = parent / BUNDLE_FOLDER
            if target.exists(): shutil.rmtree(target)
            os.replace(root, target)
            return _status(installed=True, origin="SHA256_PINNED_RESEARCH", sha256=digest,
                           warning="R18I is read-only separate research lineage")
        except Exception as e:
            return _status(installed=False, error=type(e).__name__+":"+str(e))
        finally:
            if tmp.exists(): shutil.rmtree(tmp)

def operation(home, request_json):
    global _engine, _home
    with _lock:
        try:
            req=json.loads(request_json)
            op=req.get("op", "")
            root=Path(home) / "linked_c4" / BUNDLE_FOLDER
            if op=="status":
                return status(home)
            if op=="start":
                if _engine is None:
                    if not (root/"bridge.py").is_file():
                        return _status(ok=False,error="IMPORT_LINKED_ZIP_FIRST")
                    # Do not concurrently bind a second c4child incarnation.
                    from c4_mobile_bridge import _research, _runtime
                    if _research is not None or _runtime is not None:
                        return _status(ok=False,error="STOP_LEGACY_SESSION_FIRST")
                    for name in list(sys.modules):
                        if name=="c4child" or name.startswith("c4child.") or name in ("bridge","overlap","r18i","r18d"):
                            sys.modules.pop(name,None)
                    sys.path.insert(0, str(root))
                    module=importlib.import_module("bridge")
                    _engine=module.LinkedRuntime(Path(home) / "linked_c4" / "user_life")
                    _home=str(home)
                stories=_engine.stories(10)
                if stories and _engine.story_root is None:
                    # UI shows the exact historical synthetic scope.
                    _engine.bind_story(stories[0]["world_root"])
                return _status(ok=True,active=True,stories=stories,
                               story_root=_engine.story_root,
                               provenance="HISTORICAL_SYNTHETIC_NOT_LIVE")
            if _engine is None:
                return _status(ok=False,error="START_LINKED_SESSION_FIRST")
            if _home != str(home):
                return _status(ok=False,error="LINKED_HOME_CHANGED")
            if op=="message":
                value=_engine.ask(req.get("text", ""))
            elif op=="stories":
                value=_engine.stories(20)
            elif op=="bind_story":
                value=_engine.bind_story(req["root"])
            elif op=="probes":
                value=_engine.probe_receipts(20)
            elif op=="read_probe":
                value=_engine.research_probe(req["root"])
            elif op=="checkpoint":
                value=_engine.checkpoint()
            elif op=="state":
                value=_engine.state()
            else:
                return _status(ok=False,error="UNKNOWN_LINKED_OPERATION")
            return _status(ok=True,op=op,data=value)
        except Exception as exc:
            return _status(ok=False,error=type(exc).__name__+":"+str(exc))
