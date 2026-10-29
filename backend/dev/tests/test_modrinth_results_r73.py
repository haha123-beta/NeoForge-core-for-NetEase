import copy,json,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modrinth_benchmark import encoded,sha,save
from modrinth_results import Ledger,CHECKS

def fixture(root):
    samples=[{'sample_id':'S001','project_id':'one','group':'development','version':{'id':'one_v1'}},
             {'sample_id':'S002','project_id':'two','group':'evaluation','version':{'id':'two_v1'}}]
    save(root/'samples.json',{'samples':samples,'sample_sha256':sha(encoded(samples))})
    (root/'evidence').mkdir();(root/'evidence/synthetic.log').write_text('SYNTHETIC UNIT TEST; NOT ACTUAL GAME EVIDENCE',encoding='utf-8')
    return Ledger(root)

ACCEPT={'principal_cases':[{'id':'primary','steps':'synthetic interaction','expected':'synthetic expected result'}]}

def result(accept):
    return {'status':'PASS_ENGINE','reason':'synthetic unit-test record only','acceptance_sha256':accept['payload']['acceptance_sha256'],
            'engine_run':{'environment':'netease_pc','operator':'SYNTHETIC_TEST','observed_at':'2026-10-20T00:00:00+08:00','core_version':'fixture','tool_version':'fixture'},
            'principal_results':{'primary':'pass'},'checks':{k:{'status':'pass'} for k in CHECKS},
            'evidence':[{'path':'evidence/synthetic.log','kind':'engine_log'}]}

def distribution_fixture(root):
    source='synthetic = True\n';bootstrap=b'# SYNTHETIC BOOTSTRAP\n'
    bundle={'schema_version':1,'kind':'neocore_core_sources','sources':{'fixture':{'source':source,'origin':'fixture.py','sha256':sha(source.encode())}}}
    snapshot='import json\nBUNDLE = json.loads('+repr(json.dumps(bundle))+')\n'
    fingerprint={'NeoForgeCoreScripts/fixture.py':sha(source.encode())}
    with zipfile.ZipFile(root/'distribution.zip','w') as archive:
        archive.writestr('behavior_pack_neocore/NeoCoreSourceScripts/source_snapshot.py',snapshot)
        for name,key in [('source_modules.py','NeoForgeCoreScripts/core/source_modules.py'),('runtime_host.py','NeoForgeCoreScripts/core/runtime_host.py'),('modMain.py','dev/templates/source_core_modMain.py')]:
            archive.writestr('behavior_pack_neocore/NeoCoreSourceScripts/'+name,bootstrap);fingerprint[key]=sha(bootstrap)
    save(root/'validation.json',{'status':'PASSED','changed_during_run':[],'source_sha256':fingerprint})

class ResultsLedgerTests(unittest.TestCase):
    def test_acceptance_and_results_survive_restart_with_exact_denominator(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=fixture(Path(folder));a=ledger.acceptance('S001',ACCEPT)
            ledger.result('S001',{'status':'READY_LOCAL','reason':'local-only result'})
            summary=ledger.summary('development');self.assertEqual((summary['N'],summary['P'],summary['U']),(1,0,1))
            self.assertIsNone(summary['conditional_engine_pass_rate']);self.assertEqual(summary['engine_assessment'],'NOT_EXECUTED')
            ledger.result('S001',result(a));reopened=Ledger(folder)
            self.assertEqual(reopened.summary('development')['P'],1)
            self.assertEqual(reopened.summary('evaluation')['U'],1)
            self.assertEqual(len(reopened.read()),3)
    def test_incomplete_local_or_changed_criteria_cannot_be_passed(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=fixture(Path(folder));a=ledger.acceptance('S001',ACCEPT)
            altered=copy.deepcopy(ACCEPT);altered['principal_cases'][0]['expected']='weakened'
            with self.assertRaises(ValueError):ledger.acceptance('S001',altered)
            for key in ('no_engine','failed_case','missing_check','local_evidence','wrong_criteria'):
                payload=result(a)
                if key=='no_engine':payload.pop('engine_run')
                if key=='failed_case':payload['principal_results']['primary']='fail'
                if key=='missing_check':payload['checks'].pop('unload')
                if key=='local_evidence':payload['evidence'][0]['kind']='local_test'
                if key=='wrong_criteria':payload['acceptance_sha256']='0'*64
                with self.subTest(key=key),self.assertRaises(ValueError):ledger.result('S001',payload)
            self.assertEqual(len(ledger.read()),1)
    def test_holdout_custom_demos_evidence_escape_and_chain_edits_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=fixture(Path(folder))
            with self.assertRaises(ValueError):ledger.result('demo',{'status':'READY_LOCAL','reason':'custom fixture'})
            with self.assertRaises(ValueError):ledger.result('S002',{'status':'BLOCKED_SOURCE','reason':'early holdout audit'})
            with self.assertRaises(ValueError):ledger.result('S001',{'status':'READY_LOCAL','reason':'bad evidence','evidence':[{'path':'../outside.log'}]})
            ledger.result('S001',{'status':'BLOCKED_SOURCE','reason':'missing source'})
            raw=ledger.path.read_bytes().replace(b'missing source',b'changed source');ledger.path.write_bytes(raw)
            with self.assertRaises(ValueError):ledger.read()
    def test_writer_lock_and_fixed_implementation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);ledger=fixture(root)
            with ledger.locked():
                with self.assertRaises(FileExistsError):ledger.result('S001',{'status':'NOT_RUN','reason':'locked'})
            distribution_fixture(root)
            ledger.freeze_evaluation('fixture','fixture',root/'distribution.zip',root/'validation.json')
            ledger.result('S002',{'status':'BLOCKED_SOURCE','reason':'frozen holdout audit'})
            self.assertEqual(ledger.summary()['B'],1)
            with self.assertRaises(ValueError):ledger.freeze_evaluation('other','fixture',root/'distribution.zip',root/'validation.json')

if __name__=='__main__':unittest.main()
