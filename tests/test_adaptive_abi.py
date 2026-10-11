"""Host profile negotiation and real G30G binding persistence (small CI life)."""
import hashlib,json,subprocess,sys,unittest,zipfile
from test_native_host import NativeHostTest,ROOT,b
import c4_abi_profiles as profiles

class AdaptiveTest(NativeHostTest):
    # Run only the new tests here; the original suite runs separately.
    def test_g30g_native_question_binding_cold_restart(self):
        r=self.call('USER_MESSAGE',{'text':'Привет'})
        self.assertTrue(any(e['type']=='ASK' for e in r['events']))
        self.assertTrue(b._research.runtime.binding.questions)
        self.call('USER_MESSAGE',{'text':'Меня зовут Руслан'})
        pending=b._research.runtime.binding.state()
        self.assertFalse(pending['claims']);self.assertTrue(pending['hypotheses'])
        b.close();self.assertTrue(json.loads(b.open_organism(str(self.organism)))['running'])
        self.assertEqual(pending,b._research.runtime.binding.state())
        self.call('USER_MESSAGE',{'text':'Руслан моё имя'})
        binding=b._research.runtime.binding.state();claim=binding['claims'][-1]
        self.assertEqual(claim['value'],'Руслан')
        self.assertEqual(claim['status'],'PROVISIONAL_SELF_REPORT_NOT_PERSON_VERIFICATION')
        self.assertEqual(len(claim['corroborating_turn_roots']),2)
        self.assertTrue(claim['question_root']);self.assertTrue(claim['method_roots'])
        state=json.loads(b.state());b.close()
        script="""import sys,json
sys.path.insert(0,sys.argv[1]);import c4_mobile_bridge as b
b.configure(sys.argv[2]);r=json.loads(b.open_organism(sys.argv[3]));assert r['running'],r
print(json.dumps({'binding':b._research.runtime.binding.state(),'state':json.loads(b.state())}));b.close()
"""
        restored=json.loads(subprocess.check_output([sys.executable,'-c',script,str(ROOT/'app/src/main/python'),str(self.home),str(self.organism)],text=True))
        self.assertEqual(binding,restored['binding'])
        self.assertEqual(state['journal_head'],restored['state']['journal_head'])
        self.assertEqual(self.original,self.organism.read_bytes())
    def test_negative_not_certified(self):
        self.call('USER_MESSAGE',{'text':'Привет'})
        for text in ('Я не Руслан','Я пишу','Да'):
            self.call('USER_MESSAGE',{'text':text})
        self.assertFalse(b._research.runtime.binding.state()['claims'])
    def test_future_source_profile_and_persistent_registry(self):
        b.close();future=self.home/'future.zip'
        with zipfile.ZipFile(self.zip) as source,zipfile.ZipFile(future,'w') as target:
            for n in source.namelist():
                data=source.read(n)
                if n=='c4child/runtime.py':data+=b'\n# CI source identity variant; cognition unchanged.\n'
                target.writestr(n,data)
        with self.assertRaisesRegex(RuntimeError,'UNSUPPORTED_RUNTIME_BUILD'):b.install_runtime(str(future),str(self.home))
        path=self.home/'developer.json'
        subprocess.run([sys.executable,str(ROOT/'tools/create_runtime_profile.py'),'--runtime',str(future),'--abi','CI_SAME_CONTRACT_VARIANT','--output',str(path)],check=True)
        self.assertTrue(json.loads(b.register_runtime_profile(str(path),str(self.home)))['registered'])
        b.install_runtime(str(future),str(self.home))
        self.assertTrue(json.loads(b.configure(str(self.home)))['ready'])
        # A different source build cannot silently overwrite an existing working life.
        boot=json.loads(b.open_organism(str(self.organism)))
        self.assertFalse(boot['running']);self.assertIn('CHECKPOINT_ORGANISM_OR_RUNTIME_MISMATCH',boot['errorDetail'])
        fresh=self.home/'new-test-fixture.c4m'
        with zipfile.ZipFile(self.organism) as source,zipfile.ZipFile(fresh,'w') as target:
            for n in source.namelist():
                data=source.read(n)
                if n=='manifest.json':
                    manifest=json.loads(data);manifest['organismId']='SECOND_CI_FIXTURE';data=json.dumps(manifest).encode()
                target.writestr(n,data)
        boot=json.loads(b.open_organism(str(fresh)));self.assertTrue(boot['running'],boot)
        self.assertEqual(boot['compatibility']['profileOrigin'],'USER_IMPORTED');b.close()
        p=json.loads(path.read_text());p['abi']='CONFLICT'
        path.write_text(json.dumps(p))
        with self.assertRaisesRegex(ValueError,'CONFLICTING_ABI_PROFILES'):b.register_runtime_profile(str(path),str(self.home))
        self.assertEqual(self.original,self.organism.read_bytes())
    def test_contract_rejects_missing_method(self):
        import c4child.runtime as runtime
        saved=runtime.C4LivingRuntime.poll
        try:
            runtime.C4LivingRuntime.poll=None
            with self.assertRaisesRegex(RuntimeError,'UNSUPPORTED_RUNTIME_API:poll'):b._verify_contract(runtime)
        finally:runtime.C4LivingRuntime.poll=saved

if __name__=='__main__':
    suite=unittest.TestSuite(AdaptiveTest(n) for n in ('test_g30g_native_question_binding_cold_restart','test_negative_not_certified','test_future_source_profile_and_persistent_registry','test_contract_rejects_missing_method'))
    result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())
