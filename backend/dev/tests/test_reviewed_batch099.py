import sys,unittest,tempfile,json,shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.compat_mining098 import reviewed099 as reviewed

class ReviewedBatch099(unittest.TestCase):
    def setUp(self):
        # Exercise a pinned, self-contained catalogue rule, rather than assume
        # all current compiler files still equal the historical 0.9.9 outputs.
        rules=reviewed.catalog()
        self.rules=dict(rules,files=[r for r in rules['files'] if r['file']=='java_unicode_prelex.py'])
        self.catalog_patch=patch.object(reviewed,'catalog',return_value=self.rules)
        self.catalog_patch.start();self.addCleanup(self.catalog_patch.stop)

    def fixture(self,root,missing=False):
        dev=root/'dev';dev.mkdir();rules=reviewed.catalog()
        for row in rules['files']:
            if missing and row['file']=='java_unicode_prelex.py':continue
            target=dev/row['file'];target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(reviewed.materialize(row,None))
        run=root/'run';run.mkdir();(run/'ranking.json').write_text(json.dumps({'profile':'historical','groups':[{'key':'java.unicode_prelexing','observed_blocked_mods':2}]}))
        return dev,run

    def test_installed_batch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dev,run=self.fixture(root)
            with patch.object(reviewed,'DEV',dev),patch.object(reviewed,'profile',return_value={'sha256':'fixture'}):
                p=reviewed.propose(run,root/'proposal');self.assertEqual(p['status'],'ALREADY_INSTALLED');self.assertEqual(p['files'],[])

    def test_generated_candidate_is_rederived_and_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dev,run=self.fixture(root,True)
            with patch.object(reviewed,'DEV',dev),patch.object(reviewed,'profile',return_value={'sha256':'fixture'}):
                folder=root/'proposal';p=reviewed.propose(run,folder)
                self.assertEqual([x['file'] for x in p['files']],['java_unicode_prelex.py'])
                reviewed.checked(folder)
                (folder/'after/java_unicode_prelex.py').write_text('unsafe = True')
                with self.assertRaisesRegex(ValueError,'Untrusted candidate'):reviewed.checked(folder)

    def test_target_escape_and_changed_profile_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dev,run=self.fixture(root,True)
            with patch.object(reviewed,'DEV',dev),patch.object(reviewed,'profile',return_value={'sha256':'fixture'}):
                folder=root/'proposal';p=reviewed.propose(run,folder)
                with patch.object(reviewed,'profile',return_value={'sha256':'changed'}),self.assertRaisesRegex(ValueError,'Compiler changed'):reviewed.checked(folder)
                p['files'][0]['file']='../outside.py';(folder/'proposal.json').write_text(json.dumps(p))
                with self.assertRaisesRegex(ValueError,'Unexpected reviewed patch targets'):reviewed.checked(folder)
                self.assertFalse((root/'outside.py').exists())

    def test_static_frequency_never_authorizes_the_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dev,run=self.fixture(root)
            (run/'ranking.json').write_text(json.dumps({'groups':[{'key':'java.unicode_prelexing','affected_mods':100,'observed_blocked_mods':0}]}))
            with self.assertRaisesRegex(ValueError,'observed Unicode blockers'):reviewed.reviewed_evidence(run)

if __name__=='__main__':unittest.main()
