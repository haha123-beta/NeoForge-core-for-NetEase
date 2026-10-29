import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modrinth_benchmark import save,sha,encoded
from modrinth_dependencies import audit_development
from modrinth_results import Ledger
from test_modrinth_benchmark_r56 import version,CUTOFF

class AuditProgressTests(unittest.TestCase):
    def test_reaudit_preserves_source_review_and_uses_append_only_status(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);v=version('one');rows=[{'sample_id':'S001','project_id':'one','title':'fixture','version':v,'group':'development'}]
            save(root/'samples.json',{'samples':rows,'sample_sha256':sha(encoded(rows)),'commitment':{'cutoff':CUTOFF}})
            class Client:
                def __init__(self):self.root=root
                def get(self,path):return {'source_url':'https://example.invalid/test-fixture','license':{'id':'MIT'}}
            client=Client();audit_development(client,root/'samples.json')
            path=root/'development_records/S001.json';prior=json.loads(path.read_bytes())
            prior.update(status='BLOCKED_SOURCE',source_review={'association_verified':False,'notes':'manually examined source'},source_version_link_verified=False)
            save(path,prior)
            record=audit_development(client,root/'samples.json')[0]
            self.assertEqual(record['status'],'BLOCKED_SOURCE');self.assertEqual(record['source_review'],prior['source_review'])
            self.assertEqual(record['metadata_status'],'NOT_RUN')
            ledger=Ledger(root);event=ledger.result('S001',{'status':'BLOCKED_TRANSLATION','reason':'reviewed later source blocker'})
            record=audit_development(client,root/'samples.json')[0]
            self.assertEqual(record['status'],'BLOCKED_TRANSLATION');self.assertEqual(record['assessment_event_sha256'],event['sha256'])
            self.assertEqual(record['source_review'],prior['source_review'])
    def test_cannot_merge_progress_from_other_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);v=version('one');rows=[{'sample_id':'S001','project_id':'one','title':'fixture','version':v,'group':'development'}]
            save(root/'samples.json',{'samples':rows,'sample_sha256':sha(encoded(rows)),'commitment':{'cutoff':CUTOFF}})
            save(root/'development_records/S001.json',{'project_id':'one','version_id':'other'})
            class Client:
                def __init__(self):self.root=root
                def get(self,path):return {}
            with self.assertRaises(ValueError):audit_development(Client(),root/'samples.json')

if __name__=='__main__':unittest.main()
