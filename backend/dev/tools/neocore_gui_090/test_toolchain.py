import json,sys,tempfile,time,unittest,zipfile,subprocess,threading,os
from pathlib import Path
from http.server import ThreadingHTTPServer
from app import Workspace,make_handler
from conversion import convert
from cli import call,describe

HERE=Path(__file__).resolve().parent;DEV=HERE.parents[1]
CONFIG={'dev_root':str(DEV)}
def source_jar(path,identity,files):
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('META-INF/neoforge.mods.toml','modLoader="javafml"\nloaderVersion="[1,)"\nlicense="MIT"\n[[mods]]\nmodId="'+identity+'"\nversion="1.0"\n')
        for name,body in files.items():z.writestr(name,body)
    return path

def wait(workspace,identity):
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        job=next(j for j in workspace.state()['jobs'] if j['id']==identity)
        if job['status'] not in ('QUEUED','RUNNING'):return job
        time.sleep(.1)
    raise AssertionError('Worker did not finish')

class Toolchain087(unittest.TestCase):
    def test_compiled_library_cli_to_consumer_report_archive_and_actual_python2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);classes=root/'classes';classes.mkdir();base=root/'Base.java'
            base.write_text('package third.library;public class Base {private int n;public Base(int value){n=value;}public int get(){return n;}}')
            javac=Path(r'E:\Java\jdk-21.0.10\bin\javac.exe')
            result=subprocess.run([str(javac),'-d',str(classes),str(base)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
            library=source_jar(root/'library.jar','library_sample',{'third/library/Base.class':(classes/'third/library/Base.class').read_bytes()})
            consumer=source_jar(root/'consumer.jar','consumer_sample',{'demo/Main.java':'package demo;import third.library.Base;import net.neoforged.fml.common.Mod;@Mod("consumer_sample") public class Main extends Base {public Main(){super(8);}@Override public int get(){return super.get()+1;}public int run(){return get();}}'})
            workspace=Workspace(root/'state',CONFIG);server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(workspace,'test-token'));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            (workspace.root/'当前窗口.json').write_text(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port)+'/','token':'test-token'}))
            def command(*args):
                run=subprocess.run([sys.executable,'-B',str(HERE/'cli.py'),'--data-dir',str(workspace.root),'--json',*args],capture_output=True,text=True,encoding='utf-8',env=dict(os.environ,PYTHONIOENCODING='utf-8'))
                self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr);return json.loads(run.stdout)
            try:
                lib=wait(workspace,command('convert',str(library),'--library')['job']['id'])
                self.assertEqual(lib['status'],'GENERATED_REVIEW_REQUIRED',lib);self.assertEqual(lib['source_mode'],'cfr');self.assertEqual(lib['dependency_abi']['available_types'],1)
                missing=wait(workspace,command('convert',str(consumer))['job']['id'])
                self.assertEqual(missing['status'],'TRANSLATION_INCOMPLETE',missing);self.assertEqual(missing['translation']['manual_review'],1)
                job=wait(workspace,command('convert',str(consumer),'--dependency',lib['id'])['job']['id'])
                self.assertEqual(job['status'],'GENERATED_REVIEW_REQUIRED',job);self.assertEqual(job['translation']['generated_for_review'],1)
                self.assertEqual(job['translated_dependencies'],['library_sample']);self.assertEqual(job['artifact_kind'],'SOURCE_REVIEW_ZIP');self.assertFalse(job['engine_verified']);self.assertFalse(job['translated'])
                full=call(workspace.root,'api/report/'+job['id']);self.assertEqual(len(full['content_reports']),1);self.assertEqual(len(full['dependency_abis']),1);self.assertEqual(full['source_reports'][0]['results'][0]['missing_generated_dependencies'],[])
                output=root/'review.zip';command('download',job['id'],str(output))
                with zipfile.ZipFile(output) as z:
                    self.assertIn('dependencies/library_sample/translated_sources/third/library/Base.py',z.namelist());self.assertIn('translated_sources/demo/Main.py',z.namelist());self.assertIn('reports/dependency_abi.json',z.namelist())
                    self.assertFalse(json.loads(z.read('review_manifest.json'))['netease_pack']);self.assertFalse(any(n.startswith('behavior_pack') for n in z.namelist()));z.extractall(root/'review')
                self.assertIn('源码审查包',describe({'job':job}))
                restored=Workspace(workspace.root,CONFIG)
                self.assertEqual(restored.dependency_records(job['id'],[lib['id']])[0]['manifest_sha256'],lib['dependency_abi']['manifest_sha256'])
                sys.path.insert(0,str(DEV));from build_source_bundle import core_bundle,collect_sources
                from workspace_paths import SCRIPTS_ROOT
                sources=core_bundle()['sources'];sources.update(collect_sources(root/'review/translated_sources'));sources.update(collect_sources(root/'review/dependencies/library_sample/translated_sources'))
                probe=root/'probe.json';probe.write_text(json.dumps({'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'module':'demo.Main','class_name':'Main','expected':'9'}),encoding='utf-8')
                run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(DEV/'tests/probe_interfaces082_python27.py'),str(probe)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
                module=Path(lib['dependency_abi']['source_root'])/'third/library/Base.py';module.write_text(module.read_text()+'\n# altered\n')
                with self.assertRaisesRegex(ValueError,'已变化'):workspace.export(job['id'],dependency_ids=[lib['id']])
            finally:server.shutdown();server.server_close();thread.join()

    def test_partial_library_retains_other_abi_and_exports_review_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);jar=source_jar(root/'partial.jar','partial_library',{'lib/Good.java':'package lib;public class Good {public int value(){return 3;}}','lib/Bad.java':'package lib;public record Bad<T>(T value) {}'})
            result=convert(jar,root/'work',root/'out.zip',dict(CONFIG,purpose='library'))
            self.assertEqual(result['status'],'TRANSLATION_INCOMPLETE',result);self.assertEqual(result['artifact_kind'],'SOURCE_REVIEW_ZIP');self.assertEqual(result['dependency_abi']['available_types'],1)
            abi=json.loads(Path(result['dependency_abi']['manifest']).read_bytes());self.assertEqual(abi['export_issues'][0]['file'],'lib/Bad.java')
            with zipfile.ZipFile(root/'out.zip') as z:self.assertIn('translated_sources/lib/Good.py',z.namelist());self.assertNotIn('translated_sources/lib/Bad.py',z.namelist())

if __name__=='__main__':unittest.main()
