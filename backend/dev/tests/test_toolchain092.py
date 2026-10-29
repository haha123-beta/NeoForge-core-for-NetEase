"""Evidence-driven ABI parser reuse and recipe/Mixin classification regressions."""
import json,os,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dependency_abi
from translate_java import translate
from mod_content_pipeline import classify
from mod_compat_audit import audit
from harness import Package
from workspace_paths import SCRIPTS_ROOT

class Toolchain092(unittest.TestCase):
    def test_live_snapshot_permission_race_retries_without_losing_event(self):
        import translation_observer as observer
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ,{'NEOCORE_OBSERVABILITY_DIR':tmp}):
            original=Path.replace;attempts=[]
            def busy(path,target):
                if Path(target).name=='live.json' and len(attempts)<2:
                    attempts.append(1);raise PermissionError('Reader holds destination')
                return original(path,target)
            with mock.patch.object(Path,'replace',busy),mock.patch.object(observer.time,'sleep'):
                observer.event('probe','FINISHED',file='Run.java')
            self.assertEqual(len(attempts),2)
            journal=[json.loads(s) for s in (Path(tmp)/'events.jsonl').read_text().splitlines()]
            self.assertEqual(len(journal),1);self.assertEqual(json.loads((Path(tmp)/'live.json').read_text()),journal[0])

    def test_persistent_live_lock_preserves_full_conversion_and_marks_stale_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir();(source/'Run.java').write_text('public class Run {public int run(){return 7;}}')
            baseline=translate(source,root/'baseline');original=Path.replace
            def busy(path,target):
                if Path(target).name=='live.json':raise PermissionError('Persistent preview reader')
                return original(path,target)
            evidence=root/'observations'
            with mock.patch.dict(os.environ,{'NEOCORE_OBSERVABILITY_DIR':str(evidence)}),mock.patch.object(Path,'replace',busy):
                result=translate(source,root/'observed')
            self.assertEqual(result,baseline)
            self.assertEqual((root/'baseline/source/Run.py').read_bytes(),(root/'observed/source/Run.py').read_bytes())
            rows=[json.loads(s) for s in (evidence/'events.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertTrue(any(r.get('state')=='STALE_SNAPSHOT' and r.get('journal_event_preserved') for r in rows))
            self.assertTrue(any(r['phase']=='file_result' for r in rows))

    def fixture(self,root):
        source=root/'source';(source/'third').mkdir(parents=True)
        (source/'third/Base.java').write_text('package third;public class Base<T> {public T value;public Base(T x){value=x;}public T get(){return value;}}')
        (source/'third/Child.java').write_text('package third;public class Child extends Base<String>{public Child(){super("ok");}}')
        (source/'third/Blocked.java').write_text('package third;public class Blocked extends java.util.ArrayList<String>{}')
        report=translate(source,root/'out');self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(2,1,0),report)
        jar=root/'fixture.jar'
        with zipfile.ZipFile(jar,'w') as z:
            for p in source.rglob('*.java'):z.write(p,p.relative_to(source).as_posix())
        return source,report,jar,'1','third_fixture',7,root/'out/source'

    def test_abi_worker_and_isolated_paths_are_identical_and_keep_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp))
            isolated=dependency_abi.export(*args,use_parser_worker=False)
            worker=dependency_abi.export(*args,use_parser_worker=True)
            self.assertEqual(isolated,worker)
            self.assertFalse(worker['types']['third.Blocked']['implementation_available'])
            self.assertEqual(worker['types']['third.Blocked']['implementation_status'],'MANUAL_REVIEW')
            self.assertTrue(worker['types']['third.Child']['implementation_available'])

    def test_source_change_during_export_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp));original=dependency_abi._export
            def change(*a,**kw):
                result=original(*a,**kw)
                p=args[0]/'third/Base.java';p.write_text(p.read_text()+'\n// changed concurrently')
                return result
            with mock.patch.object(dependency_abi,'_export',change):
                with self.assertRaisesRegex(ValueError,'source changed during export'):
                    dependency_abi.export(*args)

    def test_mixing_is_recipe_but_explicit_declarations_still_block_python2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);recipe='data/demo/recipe/integration/create/mixing/cabbage_slice_from_mixing.json'
            path=root/recipe;path.parent.mkdir(parents=True);path.write_text('{"type":"create:mixing"}')
            self.assertEqual(classify(recipe),('data_json','recipe'))
            self.assertEqual(audit(root)['findings'],[])
            alpha=Package().load('core.alpha_neoforge')
            self.assertEqual(alpha.inspect_bytecode_requirements(str(root),{}),[])
            # Nonstandard declared names must never disappear under the filename fallback.
            explicit=alpha.inspect_bytecode_requirements(str(root),{'mixins':[{'config':recipe},{'config':'missing_custom.json'}]})
            self.assertEqual({r['source'] for r in explicit},{recipe,'missing_custom.json'})
            (root/'demo.mixins.json').write_text('{"required":true,"plugin":"demo.Plugin"}')
            (root/'META-INF').mkdir();(root/'META-INF/MANIFEST.MF').write_text('MixinConfigs: missing_custom.json\n')
            self.assertEqual(classify('demo.mixins.json')[0],'mixin_at')
            self.assertEqual(audit(root)['finding_counts']['mixin_config'],1)
            payload={'module':str(SCRIPTS_ROOT/'core/alpha_neoforge.py'),'root':str(root),'recipe':recipe}
            code='import imp,json,sys;p=json.loads(sys.argv[1]);a=imp.load_source("probe_alpha",p["module"]);print(json.dumps(a.inspect_bytecode_requirements(p["root"],{"mixins":[{"config":p["recipe"]}]})))'
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B','-c',code,json.dumps(payload)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual({r['source'] for r in json.loads(run.stdout)}, {recipe,'demo.mixins.json','missing_custom.json'})

if __name__=='__main__':unittest.main()
