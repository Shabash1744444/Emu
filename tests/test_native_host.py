"""Transport tests. CI uses a declared small fixture, local full-organism run
sets C4_TEST_ORGANISM. Neither test replaces a user's imported life.
"""
import concurrent.futures, hashlib, json, os, shutil, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app/src/main/python'))
import c4_mobile_bridge as b
RUNTIME=ROOT/'payload/research_runtime'


def seed(folder):
    full=os.environ.get('C4_TEST_ORGANISM')
    path=folder/'seed.c4m'
    if full:shutil.copyfile(full,path);return path
    sys.path.insert(0,str(RUNTIME))
    from c4child.c4life.kernel import Life
    from c4child.checkpoint import REQUIRED,SCHEMA
    home=folder/'fixture-life';life=Life(str(home));life.tick(0,[]);life.snapshot()
    raw={REQUIRED[0]:(home/'snapshot.json').read_bytes(),REQUIRED[1]:(home/'journal.jsonl').read_bytes()}
    raw.update({k:(ROOT/'tests/lab_fixture'/Path(k).name).read_bytes() for k in REQUIRED[2:]})
    snap=json.loads(raw[REQUIRED[0]])
    manifest={'schema':SCHEMA,'organismId':'TEST_FIXTURE_ONLY','journal_len':snap['journal_len'],
              'journal_head':snap['journal_head'],'files':{k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}}
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest))
        for k,v in raw.items():z.writestr(k,v)
    life.j._fh.close();return path


class NativeHostTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name)
        self.organism=seed(self.home);self.original=self.organism.read_bytes()
        self.zip=self.home/'runtime.zip'
        with zipfile.ZipFile(self.zip,'w') as z:
            for p in RUNTIME.rglob('*.py'):z.write(p,p.relative_to(RUNTIME))
        b.install_runtime(str(self.zip),str(self.home))
        self.assertTrue(json.loads(b.open_organism(str(self.organism)))['running'])
    def tearDown(self):
        if b._research:
            b._research.runtime.life.j._fh.close()
        b._research=None;b._runtime=None
        self.tmp.cleanup()
    def call(self,k,p):return json.loads(b.command(k,json.dumps(p,ensure_ascii=False)))
    def test_identity_native_events_diagnostics_and_unknown(self):
        state=json.loads(b.state());self.assertEqual(state['organismSha256'],hashlib.sha256(self.original).hexdigest())
        r=self.call('USER_MESSAGE',{'text':'Привет'});self.assertTrue(r['accepted'])
        self.assertEqual(r['result']['intent']['status'],'UNKNOWN')
        for e in r['events']:
            if e.get('origin','').startswith('ADAPTER_'):self.assertEqual(e['type'],'DIAGNOSTIC');self.assertFalse(e['trainingEligible'])
        self.assertEqual(self.organism.read_bytes(),self.original)
    def test_ambiguous_raw_text_and_no_fake_learning(self):
        r=self.call('USER_MESSAGE',{'text':'Он дал ей ключ, а она сказала: не тот.'})
        self.assertTrue(r['accepted']);self.assertFalse(r['state']['language_learning_from_raw_chat'])
        self.call('USER_MESSAGE',{'text':'Под ключом я подразумеваю музыкальную тональность'})
        self.assertEqual(json.loads(b.state())['language_lessons'],r['state']['language_lessons'])
    def test_checkpoint_restart_exact_history(self):
        self.call('USER_MESSAGE',{'text':'Запомни именно факт этой моей реплики'})
        old=json.loads(b.state());json.loads(b.close())
        boot=json.loads(b.open_organism(str(self.organism)));self.assertTrue(boot['running'],boot)
        new=json.loads(b.state());self.assertEqual(old['journal_head'],new['journal_head'])
        self.assertEqual(old['provisional_dialogue_explanations'],new['provisional_dialogue_explanations'])
        self.assertEqual(old['world_t'],new['world_t'])
    def test_concurrent_user_input_and_ticks(self):
        before=json.loads(b.state())['world_t']
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            fs=[pool.submit(self.call,'USER_MESSAGE',{'text':'сообщение '+str(i)}) for i in range(12)]
            fs+=[pool.submit(self.call,'TICK',{'n':1}) for _ in range(12)]
            self.assertTrue(all(f.result()['accepted'] for f in fs))
        self.assertEqual(json.loads(b.state())['world_t'],before+24)
        self.assertEqual(self.organism.read_bytes(),self.original)
    def test_unsupported_no_mutation(self):
        before=json.loads(b.state())
        for kind in ('SENSORY_FRAME','WORLD_EVENT','ACTION_RECEIPT','TEACH_DIALOGUE'):
            r=self.call(kind,{'text':'anything','verified_by':'HOST'})
            self.assertFalse(r['accepted']);self.assertEqual(r['error'],'UNSUPPORTED')
        self.assertEqual(before,json.loads(b.state()))
    def test_incompatible_runtime_keeps_current(self):
        b.close();previous=Path(b._runtime_root,'c4child/runtime.py').read_bytes()
        with zipfile.ZipFile(self.home/'bad.zip','w') as z:z.writestr('c4child/runtime.py','pass')
        with self.assertRaises(RuntimeError):b.install_runtime(str(self.home/'bad.zip'),str(self.home))
        self.assertEqual(previous,Path(b._runtime_root,'c4child/runtime.py').read_bytes())
    def test_corrupt_checkpoint_preserved_and_rejected(self):
        b.close();folder=self.organism.parent/('life-'+hashlib.sha256(self.original).hexdigest())
        current=json.loads((folder/'CURRENT.json').read_bytes())
        target=folder/current['generation']/'metadata.json';target.write_text('corrupt')
        boot=json.loads(b.open_organism(str(self.organism)));self.assertFalse(boot['running'])
        self.assertIn('CHECKPOINT_DIGEST_MISMATCH',boot['errorDetail']);self.assertIn('Traceback',boot['traceback'])
        self.assertEqual(target.read_text(),'corrupt')
    def test_uncheckpointed_process_death_native_replay(self):
        b.close()
        script='''import sys,json,os
sys.path.insert(0,sys.argv[1]);import c4_mobile_bridge as b
b.configure(sys.argv[2]);r=json.loads(b.open_organism(sys.argv[3]));assert r['running'],r
r=json.loads(b.command('USER_MESSAGE',json.dumps({'text':'Жизнь продолжается после сбоя'})));assert r['accepted'],r
open(sys.argv[4],'w').write(b.state());os._exit(0)
'''
        expected=self.home/'expected.json'
        subprocess.run([sys.executable,'-c',script,str(ROOT/'app/src/main/python'),str(self.home),str(self.organism),str(expected)],check=True)
        boot=json.loads(b.open_organism(str(self.organism)));self.assertTrue(boot['running'],boot)
        old=json.loads(expected.read_text());new=json.loads(b.state())
        for k in ('journal_head','journal_len','world_t','provisional_dialogue_explanations','appliedOperations'):self.assertEqual(old[k],new[k],k)
    def test_corrupt_import_and_incompatible_schema(self):
        b.close()
        for mode in ('digest','schema'):
            dst=self.home/(mode+'.c4m')
            with zipfile.ZipFile(self.organism) as source,zipfile.ZipFile(dst,'w') as target:
                for n in source.namelist():
                    data=source.read(n)
                    if mode=='digest' and n=='lab/g30d_pragmatics.json':data=b'{}'
                    if mode=='schema' and n=='manifest.json':
                        m=json.loads(data);m['schema']='OTHER_ABI';data=json.dumps(m).encode()
                    target.writestr(n,data)
            before=dst.read_bytes();r=json.loads(b.open_organism(str(dst)))
            self.assertFalse(r['running']);self.assertIn('Traceback',r['traceback'])
            self.assertEqual(dst.read_bytes(),before)

    def test_native_tail_corruption_not_silently_truncated(self):
        b.close();home=self.organism.parent/('life-'+hashlib.sha256(self.original).hexdigest())
        journal=home/'journal.jsonl'
        with journal.open('ab') as f:f.write(b'{broken')
        before=journal.read_bytes();r=json.loads(b.open_organism(str(self.organism)))
        self.assertFalse(r['running']);self.assertIn('TORN_NATIVE_JOURNAL_PRESERVED',r['errorDetail'])
        self.assertEqual(journal.read_bytes(),before)

if __name__=='__main__':unittest.main(verbosity=2)
