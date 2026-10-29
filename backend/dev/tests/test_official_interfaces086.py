import json,os,re,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from translate_java import translate
from build_source_bundle import core_bundle,collect_sources
from workspace_paths import SCRIPTS_ROOT
from java_official_probe import REF,JDK,mapping,native,run_original
from harness import Package

class OfficialInterfaces086(unittest.TestCase):
    def execute(self,source,expected):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();(root/'Run.java').write_text(source)
            report=translate(root,Path(tmp)/'out')
            self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(1,0,0),report['results'])
            sources=core_bundle()['sources'];sources.update(collect_sources(Path(tmp)/'out/source'))
            data={'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'module':'Run','class_name':'Run','expected':expected}
            path=Path(tmp)/'probe.json';path.write_text(json.dumps(data),encoding='utf-8')
            p=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_interfaces082_python27.py')),str(path)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+'\n'+p.stderr)

    def test_entire_batch_matches_original_jar_instance_contracts(self):
        module=Package().load('minecraft.official_interfaces')
        contracts=dict(module.INTERFACE_CONTRACTS,**module.GENERIC_INTERFACES)
        mappings=(REF/'client_mappings.txt').read_text(encoding='utf-8')
        forward={a.replace('$','.'):b for a,b in re.findall(r'^(\S+) -> (\S+):$',mappings,re.M)}
        def descriptor(kind,bounds):
            kind=re.sub(r'<.*>','',kind)
            if kind.endswith('[]'):return '['+descriptor(kind[:-2],bounds)
            primitive={'void':'V','int':'I','long':'J','double':'D','float':'F','boolean':'Z','byte':'B','short':'S','char':'C'}
            if kind in primitive:return primitive[kind]
            kind=bounds.get(kind,'java.lang.Object' if kind in ('T','B','V','I','O') else kind)
            return 'L'+forward.get(kind,kind).replace('.','/')+';'
        evidence=[]
        for identity,contract in sorted(contracts.items()):
            with self.subTest(interface=identity):
                identities=[identity]+contract.get('superinterfaces',[]);available={}
                for owner in identities:
                    original=next(a for a,b in re.findall(r'^(\S+) -> (\S+):$',mappings,re.M) if a.replace('$','.')==owner)
                    text=mapping(original)
                    javap=subprocess.run([str(JDK/'javap.exe'),'-p','-s','-classpath',str(REF/'client.jar'),native(original)],capture_output=True,text=True)
                    self.assertEqual(javap.returncode,0,javap.stderr)
                    self.assertRegex(javap.stdout,r'public interface ')
                    for line in text.splitlines():
                        match=re.search(r'([\w.$\[\]]+) (\w+)\(([^)]*)\) -> (\w+)$',line)
                        if not match:continue
                        result,name,args,obf=match.groups()
                        expected='('+''.join(descriptor(a.replace('$','.'),{}) for a in args.split(',') if a)+')'+descriptor(result.replace('$','.'),{})
                        hit=re.search(r'^  public (?!static)([^\n]+) '+re.escape(obf)+r'\([^\n]*\);\r?\n\s+descriptor: '+re.escape(expected)+r'\s*$',javap.stdout,re.M)
                        if hit:available[(name,expected)]='abstract' in hit[1].split()
                    evidence.append({'java_name':owner,'mapping':text,'javap':javap.stdout})
                for row in contract['methods']:
                    bounds=contract.get('type_bounds',{})
                    desc='('+''.join(descriptor(a,bounds) for a in row['parameters'])+')'+descriptor(row['return_type'],bounds)
                    key=(row['name'],desc)
                    self.assertIn(key,available)
                    self.assertEqual(row['abstract'],available[key])
        self.assertEqual(len(contracts),22)
        target=Path(__file__).parents[1]/'builds/interfaces086_official_evidence.json'
        target.write_text(json.dumps(evidence,indent=2),encoding='utf-8')

    def test_container_data_dispatch_matches_original_and_python2(self):
        body='public class Run implements ContainerData {int n=0;public int get(int i){return n+i;}public void set(int i,int v){n=v-i;}public int getCount(){return 3;}public int run(){ContainerData d=this;d.set(2,9);return d.get(4)+d.getCount();}}'
        original=body.replace('ContainerData',native('net.minecraft.world.inventory.ContainerData'))
        for name in ('getCount','get','set'):original=re.sub(r'\b'+name+r'\(', 'a(',original)
        expected=run_original(original.replace('public class Run','class Run')+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}')
        self.assertEqual(expected,'14')
        self.execute('import net.minecraft.world.inventory.ContainerData;'+body,expected)

    def test_defaults_and_source_generic_encoder_on_actual_python2(self):
        self.execute('import net.minecraft.client.gui.components.TabOrderedElement;public class Run implements TabOrderedElement {public int run(){TabOrderedElement x=this;return x.getTabOrderGroup()+7;}}','7')
        self.execute('import net.minecraft.world.inventory.ContainerData;import net.minecraft.world.inventory.SimpleContainerData;public class Run {public int read(ContainerData d){d.set(0,7);return d.get(0)+d.getCount();}public int run(){return read(new SimpleContainerData(3));}}','10')
        self.execute('import net.minecraft.world.Nameable;import net.minecraft.network.chat.Component;public class Run implements Nameable {public Component getName(){return null;}public int run(){if(hasCustomName())return 99;if(getCustomName()!=null)return 98;if(getDisplayName()!=null)return 97;return 7;}}','7')
        self.execute('import net.minecraft.world.item.crafting.RecipeInput;import net.minecraft.world.item.ItemStack;public class Run implements RecipeInput {public int size(){return 0;}public ItemStack getItem(int n){return null;}public int run(){return isEmpty()?7:99;}}','7')
        self.execute('import net.minecraft.network.codec.StreamEncoder;import io.netty.buffer.ByteBuf;import io.netty.buffer.Unpooled;public class Run implements StreamEncoder<ByteBuf,String> {public void encode(ByteBuf b,String v){b.writeInt(7);}public int run(){ByteBuf b=Unpooled.buffer();StreamEncoder<ByteBuf,String> e=this;e.encode(b,"x");return b.readInt();}}','7')

    def test_every_abstract_contract_enforced_and_generic_bounds_rejected(self):
        module=Package().load('minecraft.official_interfaces')
        for identity,contract in module.INTERFACE_CONTRACTS.items():
            if not any(m['abstract'] for m in contract['methods']):continue
            with self.subTest(interface=identity),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text('public class Run implements '+identity+' {}')
                result=translate(root,dry_run=True)
                self.assertEqual((result['manual_review'],result['failed']),(1,0),result['results'])
        for source in ['public class Run {Object value=new net.minecraft.world.Clearable();}', 'public class Run implements net.minecraft.world.level.block.entity.BlockEntityTicker<String> {}']:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text(source);report=translate(root,dry_run=True)
                self.assertEqual((report['manual_review'],report['failed']),(1,0),report['results'])

if __name__=='__main__':unittest.main()
