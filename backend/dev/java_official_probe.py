"""Development-only JDK probes against pinned original Minecraft classes and libraries."""
import hashlib,json,os,re,subprocess,tempfile,shutil
from pathlib import Path
from workspace_paths import DEV_ROOT
REF=DEV_ROOT/'references/minecraft-1.21.1'
JDK=Path(os.environ['NEOCORE_JAVA_HOME'])/'bin' if os.environ.get('NEOCORE_JAVA_HOME') else (Path(os.environ['JAVA_HOME'])/'bin' if os.environ.get('JAVA_HOME') else Path(shutil.which('javac') or 'javac').parent)

def mapping(name):
    text=(REF/'client_mappings.txt').read_text(encoding='utf-8')
    start=text.index(name+' -> ');end=text.find('\n',start)+1
    while end<len(text) and (text[end].isspace() or text[end]=='#'):end=text.find('\n',end)+1
    return text[start:end]

def native(name):return mapping(name).split(' -> ',1)[1].split(':',1)[0]

def jars(groups):
    manifest=json.loads((REF/'reference_manifest.json').read_bytes())
    jar=REF/'client.jar'
    assert hashlib.sha256(jar.read_bytes()).hexdigest()==manifest['files']['client.jar']['sha256']
    assert hashlib.sha256((REF/'client_mappings.txt').read_bytes()).hexdigest()==manifest['files']['client_mappings.txt']['sha256']
    result=[jar];version=json.loads((REF/'version.json').read_bytes())
    for group in groups:
        lib=next(row for row in version['libraries'] if row['name'].startswith(group+':'))
        artifact=lib['downloads']['artifact'];path=Path(r'F:\PCL\.minecraft\libraries')/artifact['path']
        assert path.is_file(),'Missing pinned test dependency: '+str(path)
        assert hashlib.sha1(path.read_bytes()).hexdigest()==artifact['sha1']
        result.append(path)
    return result

def run_original(source,groups=()):
    return run_with_dependencies(source,jars(groups))

def run_with_dependencies(source,dependencies):
    with tempfile.TemporaryDirectory(prefix='neocore_official_') as tmp:
        root=Path(tmp);launcher=root/'launcher';classes=root/'classes';launcher.mkdir();classes.mkdir()
        java='''import java.net.*;import java.nio.file.*;public class ContractLauncher {public static void main(String[] a)throws Exception{URL[] urls=new URL[a.length-1];for(int i=1;i<a.length;i++)urls[i-1]=Path.of(a[i]).toUri().toURL();try(URLClassLoader original=new URLClassLoader(urls,ClassLoader.getPlatformClassLoader());URLClassLoader probe=new URLClassLoader(new URL[]{Path.of(a[0]).toUri().toURL()},original)){probe.loadClass("Probe").getMethod("main",String[].class).invoke(null,(Object)new String[0]);}}}'''
        (root/'ContractLauncher.java').write_text(java,encoding='utf-8');(root/'Probe.java').write_text(source,encoding='utf-8')
        def execute(args):
            p=subprocess.run(args,capture_output=True,text=True)
            if p.returncode:raise RuntimeError(p.stderr)
            return p.stdout
        execute([str(JDK/'javac.exe'),'-d',str(launcher),str(root/'ContractLauncher.java')])
        execute([str(JDK/'javac.exe'),'-cp',os.pathsep.join(map(str,dependencies)),'-d',str(classes),str(root/'Probe.java')])
        return execute([str(JDK/'java.exe'),'-cp',str(launcher),'ContractLauncher',str(classes)]+list(map(str,dependencies))).strip()
