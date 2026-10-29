import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modrinth_dependencies import resolve
from test_modrinth_benchmark_r56 import version,CUTOFF

def dep(pid=None,vid=None,kind='required'):
    return {'project_id':pid,'version_id':vid,'dependency_type':kind,'file_name':None}

class Fake:
    def __init__(self,versions):self.versions={v['id']:v for v in versions}
    def get(self,path,params=None):
        if path.startswith('/version/'):return self.versions[path.split('/')[-1]]
        return [v for v in self.versions.values() if v['project_id']==path.split('/')[2]]

class DependencyTests(unittest.TestCase):
    def test_required_closure_cycles_and_optional_embedded_not_installed(self):
        a=version('a');b=version('b');c=version('c')
        a['dependencies']=[dep('b','bv1'),dep('c',kind='optional'),dep('embedded',kind='embedded')]
        b['dependencies']=[dep('a','av1')]
        graph=resolve(Fake([a,b,c]),a,CUTOFF)
        self.assertEqual(set(graph['nodes']),{'a','b'})
        self.assertFalse(graph['problems']);self.assertTrue(any(e.get('cycle') for e in graph['edges']))
    def test_exact_wrong_loader_identity_conflicts_and_incompatibility_block(self):
        for kind in ('wrong_loader','conflict','incompatible','identity','missing'):
            with self.subTest(kind=kind):
                a=version('a');b=version('b');b2=version('b','v2',date='2026-10-17T00:00:00Z')
                a['dependencies']=[dep('b','bv1')]
                if kind=='wrong_loader':b['loaders']=['fabric']
                if kind=='conflict':a['dependencies'].append(dep('b','bv2'))
                if kind=='incompatible':a['dependencies'].append(dep('b',kind='incompatible'))
                if kind=='identity':a['dependencies']=[dep('other','bv1')]
                if kind=='missing':a['dependencies']=[dep()]
                graph=resolve(Fake([a,b,b2]),a,CUTOFF)
                self.assertEqual(graph['status'],'BLOCKED_DEPENDENCY');self.assertTrue(graph['problems'])
    def test_future_pin_not_silently_replaced(self):
        a=version('a');b=version('b',date='2026-10-20T00:00:00Z')
        a['dependencies']=[dep('b','bv1')]
        graph=resolve(Fake([a,b]),a,CUTOFF)
        self.assertEqual(graph['problems'][0]['kind'],'after_cutoff')

if __name__=='__main__':unittest.main()
