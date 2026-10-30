import sys,unittest,tempfile,subprocess,json,hashlib,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from translate_java import translate
from build_source_bundle import core_bundle,collect_sources
from workspace_paths import SCRIPTS_ROOT
from java_official_probe import REF,jars,run_with_dependencies
from harness import Package

class ApiWiring099(unittest.TestCase):
    def original(self,source):
        dependencies=jars(())
        version=json.loads((REF/'version.json').read_bytes())
        for lib in version['libraries']:
            artifact=lib.get('downloads',{}).get('artifact')
            if not artifact:continue
            path=Path('F:/PCL/.minecraft/libraries')/artifact['path']
            if path.is_file():
                self.assertEqual(hashlib.sha1(path.read_bytes()).hexdigest(),artifact['sha1'])
                dependencies.append(path)
        source=source.replace('import net.minecraft.network.chat.Component;','').replace('Component.literal','wz.b').replace('Component.empty','wz.i').replace('Component c','wz c')
        source=source.replace('public class Run','class Run')
        return run_with_dependencies(source+' public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}',dependencies)

    def compare(self,source,expected):
        self.assertEqual(self.original(source),expected)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);input=root/'input';input.mkdir();(input/'Run.java').write_text(source)
            report=translate(input,root/'out');self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report)
            sources=core_bundle()['sources'];sources.update(collect_sources(root/'out/input'))
            pkg=Package();runtime=pkg.load('core.source_modules').SourceModuleLoader(sources)
            api=runtime.load('core.java_api');scope=api.JavaApiImports(runtime).install(api.collect_java_api())
            try:self.assertEqual(str(runtime.load('Run').Run().run()),expected)
            finally:scope.close();runtime.close()
            payload={'sources':sources,'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'module':'Run','class_name':'Run','expected':expected}
            p=root/'probe.json';p.write_text(json.dumps(payload),encoding='utf-8')
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(p)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_literal_empty_get_string_java_original_python2_python3(self):
        self.compare('import net.minecraft.network.chat.Component;public class Run {public int run(){Component c=Component.literal("abc");return c.getString().length()+Component.empty().getString().length();}}','3')

    def test_literal_null_and_receiver_null_match_original(self):
        self.compare('import net.minecraft.network.chat.Component;public class Run {public int run(){int n=0;try{Component.literal(null);}catch(NullPointerException e){n++;}Component c=null;try{c.getString();}catch(NullPointerException e){n+=2;}return n;}}','3')

    def test_unreviewed_overloads_and_translatable_remain_blocked(self):
        for body in ['Component.literal(7);','Component.literal("a","b");','Component.empty(1);','Component.translatable("x");','Component.nullToEmpty("x");','Component c=null;c.literal("x");','Component c=null;c.empty();']:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text('import net.minecraft.network.chat.Component;class Run {void run(){'+body+'}}')
                report=translate(root,dry_run=True);self.assertEqual(report['manual_review'],1,report)

if __name__=='__main__':unittest.main()
