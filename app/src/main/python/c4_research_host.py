"""Infrastructure for the pinned G29/G30C/G30D research ABI. No cognition here.
Native journal is append-only. Write-ahead transport operations recover an
interrupted native tick against the kernel's own hash-verified journal tail.
A checkpoint publishes an immutable native snapshot + lab/transport state,
then atomically switches CURRENT. Imported organisms are never overwritten.
"""
import hashlib, json, os, shutil, time, uuid
from pathlib import Path


def encode(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sync_dir(path):
    fd = os.open(str(path), os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def atomic(path, data):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path); sync_dir(path.parent)


class ResearchHost:
    def __init__(self, organism, build, pkg):
        import c4child.checkpoint as cp
        self.pkg = pkg
        self.source = Path(organism)
        self.source_sha = sha(self.source.read_bytes())
        self.build = build
        self.home = self.source.parent / ('life-' + self.source_sha)
        self.home.mkdir(exist_ok=True)
        self.current = self.home / 'CURRENT.json'
        self.wal = self.home / 'transport.jsonl'
        self.applied = 0; self.wal_head = '0' * 64; self.failed = False; self.last_checkpoint = time.monotonic()
        if self.current.exists():
            self._restore(cp)
        else:
            if self.wal.exists() or (self.home / 'journal.jsonl').exists():
                raise RuntimeError('UNCOMMITTED_LIFE_DIRECTORY_PRESERVED')
            _, g, h, m, rs = self._load(cp)
            self.manifest = m
            old = Path(g.home)
            for name in ('snapshot.json', 'journal.jsonl'):
                shutil.copyfile(old / name, self.home / name)
            g.home = str(self.home)
            self.runtime = pkg.C4LivingRuntime(pkg.C4ChildDialogue(g))
            self.runtime.load_runtime_state(rs)
            shutil.rmtree(old)
            self.checkpoint()
        self.runtime.life.j.fsync = True
        entries = self._read_wal()
        for entry in entries[self.applied:]:
            self._execute(entry['type'], entry['payload'])
            self.applied += 1
        # Remaining native journal tail means no transport record explains it.
        if self.runtime.life.j._tail:
            raise RuntimeError('UNEXPLAINED_NATIVE_JOURNAL_TAIL')

    def _load(self, cp):
        g, h, m, rs = cp.load_c4m_compact(str(self.source), with_runtime=True)
        return cp.SCHEMA, g, h, m, rs

    def _read_wal(self):
        if not self.wal.exists(): return []
        raw = self.wal.read_bytes(); rows = []; prev = '0' * 64
        for line in raw.splitlines(keepends=True):
            if not line.endswith(b'\n'):
                raise RuntimeError('TORN_TRANSPORT_WAL_PRESERVED')
            e = json.loads(line)
            body = {k: v for k, v in e.items() if k != 'hash'}
            if e['seq'] != len(rows) or e['prev'] != prev or sha(encode(body)) != e['hash']:
                raise RuntimeError('TRANSPORT_WAL_CHAIN_FAILED')
            rows.append(e); prev = e['hash']
        self.wal_head = prev
        if self.applied > len(rows): raise RuntimeError('CHECKPOINT_AHEAD_OF_WAL')
        return rows

    def _context(self):
        r = self.runtime
        return {k: getattr(r, k) for k in ('_id', '_last_event_move', '_session', '_channel', '_events')}

    def checkpoint(self):
        if self.failed: raise RuntimeError('RECOVERY_REQUIRED_BEFORE_CHECKPOINT')
        r = self.runtime
        r.life.j._fh.flush(); os.fsync(r.life.j._fh.fileno())
        generation = 'cp-' + uuid.uuid4().hex
        folder = self.home / generation; folder.mkdir()
        r.life.snapshot(str(folder / 'snapshot.json'))
        with (folder / 'snapshot.json').open('rb') as f: os.fsync(f.fileno())
        index, observations, lab = r.lab.memory_state()
        metadata = {'build': self.build, 'sourceSha256': self.source_sha,
                    'manifest': self.manifest, 'applied': self.applied,
                    'payload': [index, observations, lab], 'pragmatics': r.pragmatics.state(),
                    'context': self._context(), 'state': r.runtime_state()}
        atomic(folder / 'metadata.json', encode(metadata))
        digests = {n: sha((folder / n).read_bytes()) for n in ('snapshot.json', 'metadata.json')}
        sync_dir(folder)
        atomic(self.current, encode({'generation': generation, 'files': digests}))
        self.last_checkpoint = time.monotonic()
        older=sorted((p for p in self.home.glob('cp-*') if p.is_dir() and p.name!=generation),key=lambda p:p.stat().st_mtime,reverse=True)
        for old in older[1:]:shutil.rmtree(old)
        return {'saved': True, 'strategy': 'NATIVE_APPEND_JOURNAL_ATOMIC_GENERATION',
                'generation': generation, 'step': r.life.step,
                'journalHead': r.life.j.head(), 'journalLength': len(r.life.j),
                'organismSha256': self.source_sha, 'path': str(self.home)}

    def _restore(self, cp):
        current = json.loads(self.current.read_bytes())
        generation = current['generation']
        if not generation.startswith('cp-') or '/' in generation or '..' in generation:
            raise RuntimeError('INVALID_CHECKPOINT_GENERATION')
        folder = self.home / generation
        for n in ('snapshot.json', 'metadata.json'):
            if sha((folder / n).read_bytes()) != current['files'][n]:
                raise RuntimeError('CHECKPOINT_DIGEST_MISMATCH:' + n)
        meta = json.loads((folder / 'metadata.json').read_bytes())
        if meta['sourceSha256'] != self.source_sha or meta['build'] != self.build:
            raise RuntimeError('CHECKPOINT_ORGANISM_OR_RUNTIME_MISMATCH')
        # Validate before Life.resume: the native loader repairs corrupt tails.
        # The host preserves any unexplained corruption instead of dropping history.
        from c4child.c4life.journal import rec_hash, GENESIS
        prev = GENESIS; records = []
        raw = (self.home / 'journal.jsonl').read_bytes()
        for i, line in enumerate(raw.splitlines(keepends=True)):
            if not line.endswith(b'\n'): raise RuntimeError('TORN_NATIVE_JOURNAL_PRESERVED')
            rec = json.loads(line)
            if rec['seq'] != i or rec['prev'] != prev or rec_hash(prev, rec) != rec['hash']:
                raise RuntimeError('NATIVE_JOURNAL_CHAIN_FAIL_AT:' + str(i))
            records.append(rec); prev = rec['hash']
        snap = json.loads((folder / 'snapshot.json').read_bytes())
        length = snap['journal_len']
        if length > len(records): raise RuntimeError('SNAPSHOT_AHEAD_OF_JOURNAL')
        head = records[length-1]['hash'] if length else GENESIS
        if head != snap['journal_head']:
            raise RuntimeError('NATIVE_SNAPSHOT_JOURNAL_MISMATCH')
        atomic(self.home / 'snapshot.json', (folder / 'snapshot.json').read_bytes())
        g = cp.G29Graph(str(self.home), meta['manifest'], tuple(meta['payload']), meta['pragmatics'])
        self.runtime = self.pkg.C4LivingRuntime(self.pkg.C4ChildDialogue(g))
        for k, v in meta['context'].items(): setattr(self.runtime, k, v)
        self.manifest = meta['manifest']; self.applied = meta['applied']

    def _execute(self, kind, payload):
        if kind == 'USER_MESSAGE': return self.runtime.user_message(payload['text'])
        if kind == 'TICK': return self.runtime.tick(payload.get('n', 1))
        if kind == 'POLL': return self.runtime.poll(payload.get('limit', 100))
        raise ValueError('UNSUPPORTED_OPERATION')

    def command(self, kind, payload):
        if self.failed: raise RuntimeError('RECOVERY_REQUIRED')
        if kind not in ('USER_MESSAGE', 'TICK', 'POLL'):
            return {'accepted': False, 'error': 'UNSUPPORTED', 'command': kind, 'events': [], 'state': self.state()}
        if kind == 'USER_MESSAGE':
            text = payload.get('text')
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                return {'accepted': False, 'error': 'EMPTY_OR_OVERSIZED_UTTERANCE', 'events': []}
        if kind == 'TICK': payload = {'n': max(0, min(int(payload.get('n', 1)), 20))}
        if kind == 'POLL': payload = {'limit': max(0, min(int(payload.get('limit', 100)), 100))}
        e = {'seq': self.applied, 'prev': self.wal_head, 'type': kind, 'payload': payload}
        e['hash'] = sha(encode(e))
        with self.wal.open('ab') as f:
            f.write(encode(e) + b'\n'); f.flush(); os.fsync(f.fileno())
        self.wal_head = e['hash']
        try:
            out = self._execute(kind, payload); self.applied += 1
            # Poll is a separate durable operation: don't lose events on crash.
            events = out if kind == 'POLL' else self._poll_durable()
            result = {'accepted': out.get('accepted', True) if isinstance(out, dict) else True,
                      'result': out, 'events': self.classify(events), 'state': self.state()}
            if time.monotonic() - self.last_checkpoint > 300: self.checkpoint()
            return result
        except Exception:
            self.failed = True
            raise

    def _poll_durable(self):
        e = {'seq': self.applied, 'prev': self.wal_head, 'type': 'POLL', 'payload': {'limit': 100}}
        e['hash'] = sha(encode(e))
        with self.wal.open('ab') as f:
            f.write(encode(e) + b'\n'); f.flush(); os.fsync(f.fileno())
        self.wal_head = e['hash']; events = self.runtime.poll(100); self.applied += 1
        # Durable outbox: remains available to export even if Android is killed
        # after this call and before rendering. No synthetic event is generated.
        if events:
            with (self.home / 'outbound.jsonl').open('ab') as f:
                f.write(encode({'operation': self.applied, 'events': events}) + b'\n')
                f.flush(); os.fsync(f.fileno())
        return events

    @staticmethod
    def classify(events):
        output = []
        for e in events:
            e = dict(e)
            if str(e.get('origin', '')).startswith('ADAPTER_') or e.get('isNativeGeneratedSpeech') is False:
                e['originalType'] = e.get('type'); e['type'] = 'DIAGNOSTIC'
                e['trainingEligible'] = False
            else: e['trainingEligible'] = e.get('type') in ('ASK', 'REPLY', 'PUBLISH')
            output.append(e)
        return output

    def state(self):
        return dict(self.runtime.runtime_state(), organismSha256=self.source_sha,
                    runtimeBuildSha256=self.build, abi='C4_RESEARCH_HOST_V1',
                    persistence='NATIVE_JOURNAL_WAL_GENERATIONS', transportVersion=1,
                    appliedOperations=self.applied, researchOnly=True)

    def export(self, destination):
        if self.failed: raise RuntimeError('RECOVERY_REQUIRED')
        import c4child.checkpoint as cp
        target=Path(destination)
        if target.resolve()==self.source.resolve():raise ValueError('IMPORT_IS_IMMUTABLE')
        self.checkpoint()
        cp.save_c4m_compact(str(target),self.runtime.dialogue.g,runtime_state=self.runtime.runtime_state())
        # Upstream portable ABI does not serialize all ephemeral dialogue context.
        return {'exported':True,'path':str(target),'sha256':sha(target.read_bytes()),
                'journalHead':self.runtime.life.j.head(),
                'limitation':'UPSTREAM_C4M_OMITS_EPHEMERAL_TRANSPORT_CONTEXT'}

    def close(self):
        if not self.failed: self.checkpoint()
        self.runtime.life.j._fh.close()
