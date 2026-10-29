import copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from java_type_queries import request_scope
from java_parse_cache import ParseCache
from translate_java import translate
import test_interfaces082 as oracle

class QueryCache092(unittest.TestCase):
    def test_none_cached_within_request_and_environment_never_retained(self):
        memo=request_scope();calls=[];env={'type':None};node={}
        @memo
        def child(n):calls.append(1);return env['type']
        @memo
        def parent(n):return (child(n),child(n))
        self.assertEqual(parent(node),(None,None));self.assertEqual(len(calls),1)
        env['type']='String';self.assertEqual(parent(node),('String','String'));self.assertEqual(len(calls),2)
    def test_exception_cleans_request_state(self):
        memo=request_scope();state=[True];node={}
        @memo
        def value(n):
            if state[0]:raise ValueError('blocked')
            return 7
        with self.assertRaises(ValueError):value(node)
        state[0]=False;self.assertEqual(value(node),7)
    def test_cache_on_off_same_reports_and_generated_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';(root/'use').mkdir(parents=True)
            (root/'use/Run.java').write_text('package use;public class Run {public int run(){String s="abc";return s.length();}}')
            a=translate(root,Path(tmp)/'a',parse_cache_enabled=False)
            b=translate(root,Path(tmp)/'b',parse_cache_enabled=True)
            self.assertEqual(a,b)
            self.assertEqual((Path(tmp)/'a/source/use/Run.py').read_bytes(),(Path(tmp)/'b/source/use/Run.py').read_bytes())
    def test_long_reviewed_chain_and_lexical_types_execute_three_runtimes(self):
        chain='new Fluent()'+'.next()'*14+'.finish()'
        oracle.Interfaces082().compare({
            'use/Fluent.java':'package use;public class Fluent {String value="";public Fluent next(){value=value+"x";return this;}public String finish(){return value;}}',
            'use/Run.java':'package use;public class Run {public String run(){String first='+chain+';String s="abc";return first+":"+s.length();}}'},'x'*14+':3')
    def test_immutable_parser_result_and_context_boundaries(self):
        import hashlib
        calls=[]
        def parser(source,origin,known):calls.append(1);return dict(origin=origin,source_sha256=hashlib.sha256(source).hexdigest(),tree={'kind':'good'})
        with ParseCache({'abi':'A'}) as cache:
            first=cache.parse(b'class A{}','A.java',[],parser);first['tree']['kind']='bad'
            self.assertEqual(cache.parse(b'class A{}','A.java',[],parser)['tree']['kind'],'good')
            self.assertEqual(len(calls),1)
            cache.parse(b'class B{}','A.java',[],parser);cache.parse(b'class A{}','A.java',['api.New'],parser)
            self.assertEqual(len(calls),3)
            p,h=next(iter(cache.entries.values()));p.write_bytes(b'{}')
            with self.assertRaises(ValueError):cache.parse(b'class A{}','A.java',[],parser)

if __name__=='__main__':unittest.main()
