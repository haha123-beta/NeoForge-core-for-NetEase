import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modrinth_benchmark import choose_version,ordered,draw,sha,encoded

CUTOFF='2026-10-19T12:30:00+00:00'

def version(pid,vid='v1',kind='release',date='2026-10-18T00:00:00Z',game='1.21.1',loader='neoforge'):
    return {'id':pid+vid,'project_id':pid,'date_published':date,'version_type':kind,
            'game_versions':[game],'loaders':[loader],'dependencies':[],'files':[]}

class SamplingTests(unittest.TestCase):
    def test_exact_version_intersection_cutoff_channels_and_stable_ties(self):
        candidates=[version('a',game='1.20.1'),version('a',loader='fabric'),
                    version('a',date='2026-10-20T00:00:00Z'),version('a','beta',kind='beta'),
                    version('a','old',date='2026-10-01T00:00:00Z'),version('a','new')]
        self.assertEqual(choose_version(candidates,CUTOFF)['id'],'anew')
        self.assertEqual(choose_version(candidates[:4],CUTOFF)['id'],'abeta')
        self.assertIsNone(choose_version(candidates[:3],CUTOFF))
        self.assertEqual(choose_version(list(reversed(candidates)),CUTOFF),choose_version(candidates,CUTOFF))
    def test_permutation_dedup_and_commit_before_qualification(self):
        ids=['a','b','c','d'];seed='NeoCore-r56-round01-20261019'
        self.assertEqual(ordered(ids,seed),ordered(list(reversed(ids)),seed))
        with self.assertRaises(ValueError):ordered(['a','a'],seed)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);order=ordered(ids,seed)
            class Fake:
                def __init__(self):self.root=root
                def get(self,endpoint,params):
                    assert (root/'commitment.json').is_file()
                    pid=endpoint.split('/')[2]
                    return [] if pid==order[0] else [version(pid)]
            frame={'candidate_ids':sorted(ids),'candidate_ids_sha256':sha(encoded(sorted(ids))),
                   'cutoff':CUTOFF,'hits':[{'project_id':pid,'slug':pid,'title':pid,'description':'test','categories':[]} for pid in ids]}
            client=Fake();result=draw(client,frame,seed,1,2)
            self.assertEqual(result['status'],'FROZEN')
            self.assertEqual([r['project_id'] for r in result['samples']],order[1:])
            self.assertEqual([r['group'] for r in result['samples']],['development','evaluation','evaluation'])
            self.assertTrue(all(r['status']=='NOT_RUN' for r in result['samples']))
            self.assertEqual(result,draw(client,frame,seed,1,2))
            with self.assertRaises(ValueError):draw(client,frame,'another',1,2)
            bad=copy.deepcopy(frame);bad['candidate_ids'].append('e')
            with self.assertRaises(ValueError):draw(client,bad,seed,1,2)

if __name__=='__main__':unittest.main()
