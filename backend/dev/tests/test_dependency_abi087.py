import os,sys,tempfile,json,unittest,zipfile,copy,subprocess
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
from dependency_abi import export,Index
from build_source_bundle import core_bundle,collect_sources
from workspace_paths import SCRIPTS_ROOT
from run_translation_job import run_job

class DependencyAbi087(unittest.TestCase):
    def fixture(self,root):
        source=root/'source';(source/'third/library').mkdir(parents=True)
        java=source/'third/library/Base.java';java.write_text('package third.library;public class Base {public int n;public Base(int value){n=value;}public int get(){return n;}}')
        report=translate(source,root/'out');self.assertEqual(report['generated_for_review'],1,report)
        jar=root/'library.jar'
        with zipfile.ZipFile(jar,'w') as archive:archive.writestr('third/library/Base.java',java.read_bytes())
        return export(source,report,jar,'1.0','third_library',7,root/'out/source')

    def test_formal_provenance_abi_and_physical_implementation(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=self.fixture(Path(tmp));row=manifest['types']['third.library.Base']
            self.assertEqual(row['package'],'third.library');self.assertEqual(len(row['constructors']),1);self.assertTrue(row['python_sha256']);self.assertTrue(row['implementation_available'])
            self.assertFalse(manifest['engine_verified']);self.assertEqual(len(manifest['source_jar_sha256']),64)
            index=Index([manifest],core_symbols=['net.minecraft.world.item.Item'])
            self.assertEqual(index.resolve('third.library.Base','inheritance')['category'],'TRANSLATED_DEPENDENCY_SYMBOL')
            self.assertEqual(index.resolve('net.minecraft.world.item.Item')['category'],'CORE_SYMBOL')
            self.assertIn('third.library.Base',index.project_records())

    def test_symbol_only_optional_and_hard_abi_are_distinct(self):
        index=Index(optional_packages=['optional.lib'])
        self.assertEqual(index.resolve('optional.lib.Thing')['category'],'OPTIONAL_DEPENDENCY')
        self.assertEqual(index.resolve('other.lib.Thing')['category'],'UNRESOLVED_EXTERNAL')
        self.assertTrue(index.resolve('other.lib.Thing')['deferred'])
        self.assertEqual(index.resolve('other.lib.Thing','constructor')['category'],'EXTERNAL_ABI_REQUIRED')
        self.assertFalse(index.resolve('other.lib.Thing','inheritance')['deferred'])

    def test_conflicts_incomplete_and_unsafe_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=self.fixture(Path(tmp))
            with self.assertRaises(ValueError):Index([manifest,manifest])
            with self.assertRaises(ValueError):Index([manifest],available_neocore_abi=6)
            damaged=copy.deepcopy(manifest);damaged['types']['third.library.Base']['source_record']['file']='../escape.java'
            with self.assertRaises(ValueError):Index([damaged])
            damaged=copy.deepcopy(manifest);damaged['types']['third.library.Base']['implementation_available']=False
            self.assertEqual(Index([damaged]).resolve('third.library.Base','inheritance')['category'],'EXTERNAL_ABI_REQUIRED')

    def test_independent_content_dependency_inheritance_executes_actual_python2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=self.fixture(root)
            consumer=root/'consumer';consumer.mkdir()
            (consumer/'Run.java').write_text('import third.library.Base;public class Run extends Base {public Run(){super(6);}@Override public int get(){return super.get()+1;}public int run(){return get();}}')
            report=translate(consumer,root/'consumer_out',dependency_abis=[manifest])
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report)
            row=report['results'][0];self.assertEqual(row['translated_dependencies'],['third_library']);self.assertEqual(row['project_dependencies'],[]);self.assertEqual(row['missing_generated_dependencies'],[])
            sources=core_bundle()['sources'];sources.update(collect_sources(root/'out/source'));sources.update(collect_sources(root/'consumer_out/consumer'))
            payload={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'module':'Run','class_name':'Run','expected':'7'}
            path=root/'probe.json';path.write_text(json.dumps(payload),encoding='utf-8')
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(path)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)

    def test_deferred_static_reference_is_lazy_but_constructor_and_inheritance_require_abi(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'consumer';source.mkdir();path=source/'Run.java'
            path.write_text('import other.lib.Thing;public class Run {public void later(){Thing.fire();}public int run(){return 4;}}')
            report=translate(source,root/'out',defer_external_symbols=True)
            self.assertEqual(report['generated_for_review'],1,report)
            row=report['results'][0];self.assertTrue(row['external_symbols'][0]['deferred']);self.assertNotIn('other.lib.Thing',row['required_api_types'])
            for body in ['public class Run extends other.lib.Thing {}','import other.lib.Thing;public class Run {public Object run(){return new Thing();}}']:
                path.write_text(body);report=translate(source,dry_run=True,defer_external_symbols=True)
                self.assertEqual(report['manual_review'],1,report);self.assertEqual(report['results'][0]['details']['category'],'EXTERNAL_ABI_REQUIRED')

    def test_soft_third_party_symbols_defer_by_default_but_core_symbols_do_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';source.mkdir();path=source/'Run.java'
            path.write_text('import third.party.Api; public class Run {Api value; Api read(){return value;}}')
            report=translate(source,dry_run=True)
            self.assertEqual(report['generated_for_review'],1,report)
            self.assertTrue(report['results'][0]['external_symbols'][0]['deferred'])
            path.write_text('import net.minecraft.unknown.Core; public class Run {Core value;}')
            report=translate(source,dry_run=True)
            self.assertEqual(report['manual_review'],1,report)
            self.assertEqual(report['results'][0]['details']['category'],'EXTERNAL_ABI_REQUIRED')

    def test_background_json_producer_consumer_and_deferred_packaging_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            config=root/'job.json';config.write_text(json.dumps({'input':'source','output_root':'jobs','export_dependency_abi':{'source_jar':'library.jar','version':'1.0','dependency_id':'third_library','neocore_abi':7}}))
            producer=run_job(config);self.assertEqual(producer['status'],'GENERATED_REVIEW_REQUIRED',producer)
            consumer=root/'consumer';consumer.mkdir();(consumer/'Run.java').write_text('import third.library.Base;public class Run extends Base {public Run(){super(2);}public int run(){return get();}}')
            config.write_text(json.dumps({'input':'consumer','output_root':'jobs','dependency_abis':[producer['dependency_abi']['manifest']]}))
            report=run_job(config);self.assertEqual(report['translation']['generated_for_review'],1,report);self.assertEqual(report['translated_dependencies'],['third_library']);self.assertFalse(report['engine_verified'])
            (consumer/'Run.java').write_text('import other.lib.Thing;public class Run {public void later(){Thing.fire();}}')
            config.write_text(json.dumps({'input':'consumer','output_root':'jobs','defer_external_symbols':True,'distribution':{'pack_id':'consumer','entrypoints':{'consumer':'Run:Run'}}}))
            report=run_job(config);self.assertEqual(report['status'],'GENERATED_REVIEW_REQUIRED',report);self.assertIn('external symbols remain deferred',report['packaging']);self.assertNotIn('distribution',report)

    def test_transitive_local_implementation_gap_cannot_satisfy_dependency_abi(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir()
            bodies={'A.java':'public class A extends B {}','B.java':'public class B {public int get(){return C.n();}}','C.java':'public class C {public static synchronized int n(){return 3;}}'}
            for name,body in bodies.items():(source/name).write_text(body)
            report=translate(source,root/'out');self.assertEqual(report['generated_for_review'],2,report)
            jar=root/'lib.jar'
            with zipfile.ZipFile(jar,'w') as archive:
                for name,body in bodies.items():archive.writestr(name,body)
            manifest=export(source,report,jar,'1','chain',7,root/'out/source')
            self.assertFalse(manifest['types']['A']['implementation_available']);self.assertFalse(manifest['types']['B']['implementation_available'])
            self.assertEqual(Index([manifest]).resolve('A','inheritance')['category'],'EXTERNAL_ABI_REQUIRED')

    def test_required_transform_blocker_cannot_export_available_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            report=json.loads((root/'out/translation_report.json').read_bytes())
            report['capability_blockers']=[{'kind':'asm','status':'UNSUPPORTED'}]
            manifest=export(root/'source',report,root/'library.jar','1','blocked_library',7,root/'out/source')
            self.assertFalse(manifest['types']['third.library.Base']['implementation_available'])
            self.assertEqual(Index([manifest]).resolve('third.library.Base','inheritance')['category'],'EXTERNAL_ABI_REQUIRED')

if __name__=='__main__':unittest.main()
