import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_official_probe import native,run_original
from translate_java import translate
from build_source_bundle import core_bundle,collect_sources
from workspace_paths import SCRIPTS_ROOT
from harness import Package
GROUPS=('io.netty:netty-buffer','io.netty:netty-common','io.netty:netty-codec','com.mojang:datafixerupper','com.mojang:authlib','com.mojang:logging','com.mojang:brigadier','org.joml:joml','org.apache.commons:commons-lang3','commons-io:commons-io','com.google.guava:guava','com.google.code.gson:gson','it.unimi.dsi:fastutil','org.slf4j:slf4j-api')
SOURCE='package demo;\nimport io.netty.buffer.ByteBuf;\nimport java.util.UUID;\nimport net.minecraft.core.BlockPos;\nimport net.minecraft.core.UUIDUtil;\nimport net.minecraft.network.codec.StreamCodec;\nimport net.minecraft.network.protocol.common.custom.CustomPacketPayload;\nimport net.minecraft.resources.ResourceLocation;\npublic record Packet(int number,byte flag,UUID id,BlockPos pos) implements CustomPacketPayload {\n public static final CustomPacketPayload.Type<Packet> TYPE=new CustomPacketPayload.Type(ResourceLocation.fromNamespaceAndPath("demo","wire"));\n public static final StreamCodec<ByteBuf,Packet> CODEC=new StreamCodec<ByteBuf,Packet>() {\n  public Packet decode(ByteBuf b){int n=b.readInt();byte f=b.readByte();UUID id=(UUID)UUIDUtil.STREAM_CODEC.decode((Object)b);BlockPos p=(BlockPos)BlockPos.STREAM_CODEC.decode((Object)b);return new Packet(n,f,id,p);}\n  public void encode(ByteBuf b,Packet p){b.writeInt(p.number);b.writeByte((int)p.flag);UUIDUtil.STREAM_CODEC.encode((Object)b,(Object)p.id);BlockPos.STREAM_CODEC.encode((Object)b,(Object)p.pos);}\n };\n public CustomPacketPayload.Type<Packet> type(){return TYPE;}\n}'

# CFR also erases codec arguments selected from an imported reference array.
SOURCE=SOURCE.replace('UUIDUtil.STREAM_CODEC.encode((Object)b,(Object)p.id);',
    'UUID[] values=new UUID[]{p.id};UUIDUtil.STREAM_CODEC.encode((Object)b,(Object)values[0]);')

class Network086(unittest.TestCase):
    def test_payload_record_anonymous_codec_wire_jdk_and_real_python2(self):
        names={n:native(n) for n in ('net.minecraft.core.BlockPos','net.minecraft.core.UUIDUtil','net.minecraft.network.codec.StreamCodec','net.minecraft.network.protocol.common.custom.CustomPacketPayload','net.minecraft.resources.ResourceLocation')}
        source=SOURCE.replace('package demo;','').replace('public record Packet','record Packet')
        for fq,obf in names.items():
            source=source.replace('import '+fq+';','').replace(fq.rsplit('.',1)[-1],obf.replace('$','.'))
        payload=names['net.minecraft.network.protocol.common.custom.CustomPacketPayload'];pos=names['net.minecraft.core.BlockPos'];uid=names['net.minecraft.core.UUIDUtil'];rl=names['net.minecraft.resources.ResourceLocation']
        source=source.replace(payload+'.Type',payload+'.b').replace('fromNamespaceAndPath','a').replace(uid+'.STREAM_CODEC',uid+'.g').replace(pos+'.STREAM_CODEC',pos+'.b').replace(' type(){',' a(){')
        probe='public class Probe {public static void main(String[] a){Packet p=new Packet(-2147483648,(byte)-7,java.util.UUID.fromString("12345678-1234-5678-9abc-def012345678"),new '+pos+'(-33554432,-2048,33554431));io.netty.buffer.ByteBuf b=io.netty.buffer.Unpooled.buffer(0);Packet.CODEC.encode(b,p);for(int i=0;i<b.writerIndex();i++)System.out.print((i==0?"":",")+b.getUnsignedByte(i));System.out.println();Packet q=Packet.CODEC.decode(b);System.out.println(q.equals(p)+","+q.number()+","+q.flag()+","+q.id()+","+q.pos().a()+","+q.hashCode()+","+q.a().a()+","+q.a().toString()+","+q.a().hashCode());}}'
        # BlockPos.asLong is mapped i(), not its static overload; select from pinned mappings.
        from java_official_probe import mapping
        method=next(line.split(' -> ')[1].strip() for line in mapping('net.minecraft.core.BlockPos').splitlines() if 'long asLong()' in line)
        probe=probe.replace('q.pos().a()', 'q.pos().'+method+'()')
        source=source.replace('(Object)','')
        probe=probe.replace('io.netty.buffer.ByteBuf','ByteBuf').replace('io.netty.buffer.Unpooled','Unpooled')
        expected=run_original('import io.netty.buffer.Unpooled;\n'+source+'\n'+probe,GROUPS).replace(',b[id=',',Type[id=').splitlines()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();(root/'demo').mkdir()
            files={'Packet.java':SOURCE,'Sink.java':'package demo;public class Sink {public static int count;public static void accept(Packet p){count=(int)p.flag();}}','Handlers.java':'package demo;import net.neoforged.neoforge.network.handling.IPayloadContext;public class Handlers {public static void handle(Packet p,IPayloadContext c){c.enqueueWork(()->{if(!c.flow().isClientbound())return;Sink.accept(p);});}}'}
            for name,value in files.items():(root/'demo'/name).write_text(value)
            report=translate(root,Path(tmp)/'out');self.assertEqual((report['generated_for_review'],report['manual_review'],report['failed']),(3,0,0),report['results'])
            sources=core_bundle()['sources'];sources.update(collect_sources(Path(tmp)/'out/source'))
            path=Path(tmp)/'input.json';path.write_text(json.dumps({'loader_source':(SCRIPTS_ROOT/'core/source_modules.py').read_text(encoding='utf-8'),'sources':sources,'expected':expected}),encoding='utf-8')
            run=subprocess.run([r'D:\NeoCore工具\python27_validation\runtime\python.exe','-B',str(Path(__file__).with_name('probe_network086_python27.py')),str(path)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr);self.assertEqual(json.loads(run.stdout.strip().splitlines()[-1])['wire_bytes'],29)

    def test_byte_buffer_primitive_boundaries_match_original_netty(self):
        values=[-2147483648,-257,-1,0,1,127,128,255,256,2147483647]
        source='public class Probe {public static void main(String[] a){for(int n:new int[]{'+','.join(map(str,values))+'}){io.netty.buffer.ByteBuf b=io.netty.buffer.Unpooled.buffer(0,64);b.writeByte(n).writeShort(n).writeInt(n).writeBoolean(n!=0);System.out.print(b.capacity()+","+b.writerIndex());for(int i=0;i<b.writerIndex();i++)System.out.print(","+b.getUnsignedByte(i));System.out.println(","+b.readByte()+","+b.readUnsignedShort()+","+b.readInt()+","+b.readBoolean()+","+b.readableBytes());}}}'
        source='import io.netty.buffer.ByteBuf;import io.netty.buffer.Unpooled;'+source.replace('io.netty.buffer.ByteBuf','ByteBuf').replace('io.netty.buffer.Unpooled','Unpooled')
        expected=run_original(source,('io.netty:netty-buffer','io.netty:netty-common')).splitlines()
        pkg=Package();v=pkg.load('java_stdlib.byte_buffer');actual=[]
        for n in values:
            b=v.Unpooled.buffer(0,64);b.writeByte(n).writeShort(n).writeInt(n).writeBoolean(n!=0)
            row=[b.capacity(),b.writerIndex()]+b._neocore_bytes()+[b.readByte(),b.readUnsignedShort(),b.readInt(),str(b.readBoolean()).lower(),b.readableBytes()]
            actual.append(','.join(map(str,row)))
        self.assertEqual(actual,expected)
        e=pkg.load('java_stdlib.lang');b=v.Unpooled.buffer(0,2)
        with self.assertRaises(e.IndexOutOfBoundsException):b.readInt()
        with self.assertRaises(e.IndexOutOfBoundsException):b.writeInt(1)
        self.assertEqual((b.readerIndex(),b.writerIndex()),(0,0))

    def test_codec_operation_map_unit_and_cast_match_original(self):
        source='public class Probe {public static void main(String[] a){yx<java.util.List<Integer>,Integer> base=yx.a((yz<java.util.List<Integer>,Integer>)(b,v)->{b.add(v);},(yy<java.util.List<Integer>,Integer>)(b)->b.remove(0));yx<java.util.List<Integer>,Integer> mapped=base.a((Integer v)->v+2,(Integer v)->v-2);java.util.List<Integer> b=new java.util.ArrayList<>();mapped.encode(b,10);System.out.println(b.get(0)+","+mapped.decode(b));yx<java.util.List<Integer>,Integer> applied=base.a((yx.a<java.util.List<Integer>,Integer,Integer>)(c)->c.a((Integer v)->v*2,(Integer v)->v/2));applied.encode(b,12);System.out.println(b.get(0)+","+applied.decode(b));yx<Object,String> unit=yx.a("fixed");unit.encode(null,"fixed");System.out.println(unit.decode(null)+","+(unit.a()==unit));try{unit.encode(null,"wrong");}catch(Exception e){System.out.println(e.getClass().getSimpleName());}try{unit.encode(null,null);}catch(Exception e){System.out.println(e.getClass().getSimpleName());}}}'
        expected=run_original(source,GROUPS).splitlines()
        pkg=Package();n=pkg.load('neoforge.network');base=n.StreamCodec.of(lambda b,v:b.append(v),lambda b:b.pop(0));b=[];mapped=base.map(lambda v:v+2,lambda v:v-2);mapped.encode(b,10);actual=[str(b[0])+','+str(mapped.decode(b))]
        applied=base.apply(lambda c:c.map(lambda v:v*2,lambda v:v//2));applied.encode(b,12);actual.append(str(b[0])+','+str(applied.decode(b)))
        unit=n.StreamCodec.unit('fixed');unit.encode(None,'fixed');actual.append(unit.decode(None)+','+str(unit.cast() is unit).lower())
        for value in ('wrong',None):
            try:unit.encode(None,value);self.fail('Expected original exception')
            except Exception as e:actual.append(type(e).__name__)
        self.assertEqual(actual,expected)

    def test_uuid_java_normalization_hash_and_invalid_values(self):
        cases=['12345678-1234-5678-9abc-def012345678','FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF','1-2-3-4-5','abcd-1234','', '100000000-1-1-1-1']
        literals=','.join(json.dumps(v) for v in cases)
        java='public class Probe {public static void main(String[] a){for(String s:new String[]{'+literals+'}){try{java.util.UUID u=java.util.UUID.fromString(s);System.out.println(u.toString()+","+u.getMostSignificantBits()+","+u.getLeastSignificantBits()+","+u.hashCode());}catch(Exception e){System.out.println(e.getClass().getSimpleName());}}}}'
        expected=run_original(java).splitlines();pkg=Package();UUID=pkg.load('java_stdlib.util').UUID;actual=[]
        for value in cases:
            try:
                u=UUID.fromString(value);actual.append(u.toString()+','+','.join(map(str,[u.getMostSignificantBits(),u.getLeastSignificantBits(),u.hashCode()])))
            except Exception as e:actual.append(type(e).__name__)
        self.assertEqual(actual,expected)

    def test_future_observation_unreviewed_fields_and_anonymous_captures_reject(self):
        files=['import net.neoforged.neoforge.network.handling.IPayloadContext;class Run {Object run(IPayloadContext c){return c.enqueueWork(()->{});}}','import net.minecraft.network.codec.ByteBufCodecs;class Run {Object value=ByteBufCodecs.TAG;}','import io.netty.buffer.ByteBuf;import net.minecraft.network.codec.StreamCodec;class Run {Object run(){return new StreamCodec<ByteBuf,Run>(){public Run decode(ByteBuf b){return new Run();}public void encode(ByteBuf b,Run r){}};}}']
        for source in files:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text(source);r=translate(root,dry_run=True);self.assertEqual((r['manual_review'],r['failed']),(1,0),r)
        for source in ['import net.minecraft.network.FriendlyByteBuf;class Run {int bad(FriendlyByteBuf b){return b.capacity();}}',
                       'import net.minecraft.core.UUIDUtil;class Run {Object bad(Object b){return UUIDUtil.STREAM_CODEC.decode(b);}}',
                       'import net.minecraft.core.UUIDUtil;class Run {Object bad(String b){return UUIDUtil.STREAM_CODEC.decode((Object)b);}}']:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text(source);r=translate(root,dry_run=True)
                self.assertEqual((r['manual_review'],r['failed']),(1,0),r)

if __name__=='__main__':unittest.main()
