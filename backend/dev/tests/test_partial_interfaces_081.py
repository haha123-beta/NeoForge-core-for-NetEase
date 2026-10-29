import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
from run_translation_job import run_job
from build_source_bundle import collect_sources
from harness import Package


class PartialInterfaces081(unittest.TestCase):
    def write(self,root,files):
        root.mkdir()
        for name,source in files.items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source,encoding='utf-8')

    def test_optional_plugin_is_explicitly_skipped_without_placeholder_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source'
            self.write(root,{'x/Good.java':'package x;public class Good {public int value(){return 7;}}',
                'optional.mixins.json':json.dumps({'required':False,'plugin':'x.Plugin','package':'x'})})
            strict=translate(root,dry_run=True)
            self.assertEqual(strict['generated_for_review'],0)
            result=translate(root,Path(tmp)/'converted',partial_transformers=True)
            self.assertEqual((result['generated_for_review'],result['manual_review'],result['failed']),(1,0,0))
            self.assertEqual(result['skipped_optional'][0]['status'],'SKIPPED_OPTIONAL')
            self.assertFalse(result['engine_verified'])
            config=Path(tmp)/'job.json';config.write_text(json.dumps({'input':str(root),'output_root':str(Path(tmp)/'jobs'),'partial_transformers':True,'distribution':{'pack_id':'sample'}}))
            job=run_job(config)
            self.assertEqual(job['status'],'GENERATED_REVIEW_REQUIRED')
            self.assertFalse((Path(job['output'])/'distribution').exists())

    def test_required_malformed_and_asm_keep_capability_blockers_but_do_not_erase_sources(self):
        for config in ({'required':True,'plugin':'x.Plugin'},{'required':'false','plugin':'x.Plugin'},None):
            with self.subTest(config=config),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'source';files={'x/Good.java':'package x;public class Good {}'}
                if config is not None:files['x.mixins.json']=json.dumps(config)
                else:files['META-INF/services/cpw.mods.modlauncher.serviceapi.ILaunchPluginService']='x.Plugin'
                self.write(root,files)
                result=translate(root,dry_run=True,partial_transformers=True)
                self.assertEqual(result['generated_for_review'],1)
                self.assertEqual(len(result['capability_blockers']),1)
                self.assertFalse(result['skipped_optional'])

    def test_default_virtual_dispatch_override_and_abstract_contract_match_jdk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source'
            files={'x/Values.java':'package x; public interface Values {int value(); default int doubled(){return value()*2;} default int bonus(){return 3;}}',
                'x/First.java':'package x; public class First implements Values {public int value(){return 7;} public int total(){return doubled()+bonus();}}',
                'x/Second.java':'package x; public class Second implements Values {public int value(){return 11;} public int bonus(){return 5;} public int total(){return doubled()+bonus();}}'}
            self.write(root,files)
            result=translate(root,Path(tmp)/'out')
            self.assertEqual((result['generated_for_review'],result['manual_review'],result['failed']),(3,0,0),result['results'])
            pkg=Package();api=pkg.load('core.java_api');runtime=pkg.load('core.source_modules').SourceModuleLoader(collect_sources(Path(tmp)/'out/source'))
            scope=api.JavaApiImports(runtime).install(api.collect_java_api())
            try:
                first=runtime.load('x.First').First();second=runtime.load('x.Second').Second()
                actual=str(first.total())+','+str(second.total())
                self.assertEqual(actual,'17,27')
                with self.assertRaises(TypeError):runtime.load('x.Values').Values()
                self.assertIsInstance(first,runtime.load('x.Values').Values)
            finally:scope.close();runtime.close()
            probe=root/'Probe.java';probe.write_text('public class Probe {public static void main(String[] a){System.out.print(new x.First().total()+","+new x.Second().total());}}')
            classes=Path(tmp)/'classes';classes.mkdir();jdk=Path(r'E:\Java\jdk-21.0.10\bin')
            built=subprocess.run([str(jdk/'javac.exe'),'-d',str(classes)]+[str(root/p) for p in files]+[str(probe)],capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            run=subprocess.run([str(jdk/'java.exe'),'-cp',str(classes),'Probe'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout,actual)
            from workspace_paths import SCRIPTS_ROOT
            sources=collect_sources(SCRIPTS_ROOT);sources.update(collect_sources(Path(tmp)/'out/source'))
            probe_input=Path(tmp)/'probe.json';probe_input.write_text(json.dumps({'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'expected':actual}),encoding='utf-8')
            py2=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces081_python27.py')),str(probe_input)],capture_output=True,text=True)
            self.assertEqual(py2.returncode,0,py2.stderr+'\n'+py2.stdout)
            self.assertTrue(json.loads(py2.stdout.strip().splitlines()[-1])['python2_executed'])

    def test_missing_abstract_implementation_and_unsupported_diamonds_are_not_generated(self):
        for declaration in ('public class Bad implements Values {}','public class Bad implements Values {public int unrelated(){return 2;}}','public class Bad implements Values, Other {}','public class Bad extends Base implements Values {}'):
            with self.subTest(declaration=declaration),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'source';self.write(root,{'x/Values.java':'package x;public interface Values {int value();}', 'x/Bad.java':'package x;'+declaration})
                result=translate(root,dry_run=True)
                self.assertEqual(next(r for r in result['results'] if r['file']=='x/Bad.java')['status'],'MANUAL_REVIEW')

    def test_benchmark_denominator_and_at_audit_do_not_claim_semantic_success(self):
        from conversion_benchmark import summarize
        from audit_access_transformers import audit
        with tempfile.TemporaryDirectory() as tmp:
            jar=Path(tmp)/'input.jar';jar.write_bytes(b'input identity')
            report={'files':2,'manual_review':1,'failed':0,'results':[{'file':'a.java','status':'GENERATED_REVIEW_REQUIRED','missing_generated_dependencies':['b.java']},{'file':'b.java','status':'MANUAL_REVIEW','reason':'Unresolved external import: net.minecraft.client.Minecraft'}]}
            summary=summarize(report,jar,2)
            self.assertEqual(summary['conversion_rate'],.5);self.assertEqual(summary['generated_with_missing_dependencies'],1)
            self.assertFalse(summary['playable'])
            with self.assertRaises(ValueError):summarize(report,jar,130)
            config=Path(tmp)/'at.cfg';config.write_text('# comment\npublic x.Missing missing\npublic x.Present field # trailing\npublic x.Present method()V\n')
            class Present:
                field=1
                def method(self):pass
            result=audit(config,{'x.Present':Present})
            self.assertEqual(result['active_rows'],3)
            self.assertEqual([r['line'] for r in result['rows']],[2,3,4])
            self.assertFalse(result['automatically_satisfied'])


if __name__=='__main__':unittest.main()
