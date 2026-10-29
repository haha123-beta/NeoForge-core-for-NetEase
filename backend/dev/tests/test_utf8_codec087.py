import json,os,random,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_official_probe import native,run_original
from test_network086 import GROUPS
import test_official_interfaces086 as execution

class Utf8Codec087(unittest.TestCase):
    def test_original_netty_encoder_surrogates_and_unicode(self):
        cases=[[],[65,0,127,128,2047,2048,65535],[0xd83d,0xde03],[0xd800],[0xdc00],[0xd800,65],[0xd800,0xe9],[0xd800,0xd801],[0xd800,0xdc00,0xd800,65]]
        arrays=','.join('new char[]{'+','.join('(char)'+str(n) for n in row)+'}' for row in cases)
        source='public class Probe {public static void main(String[] a){for(char[] c:new char[][]{'+arrays+'}){io.netty.buffer.ByteBuf b=io.netty.buffer.Unpooled.buffer();'+native('net.minecraft.network.Utf8String')+'.a(b,new String(c),32767);for(int i=0;i<b.writerIndex();i++)System.out.print((i==0?"":",")+b.getUnsignedByte(i));System.out.println();}}}'
        source='import io.netty.buffer.ByteBuf;import io.netty.buffer.Unpooled;'+source.replace('io.netty.buffer.ByteBuf','ByteBuf').replace('io.netty.buffer.Unpooled','Unpooled')
        expected=run_original(source,GROUPS).splitlines();p=Package();u=p.load('minecraft.utf8_codec');b=p.load('java_stdlib.byte_buffer');lang=p.load('java_stdlib.lang');actual=[]
        for row in cases:
            value=lang._utf16_text(''.join(chr(n) for n in row));buffer=b.Unpooled.buffer();u.write(buffer,value,32767);actual.append(','.join(map(str,buffer._neocore_bytes())))
        self.assertEqual(actual,expected)

    def test_original_java_decoder_malformed_sequences(self):
        cases=[[],[0xc0,0x80],[0xed,0xa0,0x80],[0xe0,0x80,0x80],[0xf0,0x80,0x80,0x80],[0xf4,0x90,0x80,0x80],[0xef,0xbf,0xbd],[0xf0,0x9f,0x98,0x83]]
        for head in (0xc2,0xe0,0xe1,0xed,0xf0,0xf1,0xf4):
            for tail in ([0x80],[0xa0],[0x80,65],[0xa0,0x80],[0xa0,0x80,0x80]):cases.append([head]+tail)
        rng=random.Random(87)
        cases.extend([[rng.randrange(256) for _ in range(rng.randrange(1,12))] for i in range(150)])
        arrays=','.join('new int[]{'+','.join(map(str,row))+'}' for row in cases)
        source='public class Probe {public static void main(String[] a){for(int[] data:new int[][]{'+arrays+'}){io.netty.buffer.ByteBuf b=io.netty.buffer.Unpooled.buffer();b.writeByte(data.length);for(int n:data)b.writeByte(n);String s='+native('net.minecraft.network.Utf8String')+'.a(b,32767);for(int i=0;i<s.length();i++)System.out.print((i==0?"":",")+(int)s.charAt(i));System.out.println(";"+b.readerIndex());}}}'
        source='import io.netty.buffer.ByteBuf;import io.netty.buffer.Unpooled;'+source.replace('io.netty.buffer.ByteBuf','ByteBuf').replace('io.netty.buffer.Unpooled','Unpooled')
        expected=run_original(source,GROUPS).splitlines();p=Package();u=p.load('minecraft.utf8_codec');b=p.load('java_stdlib.byte_buffer');lang=p.load('java_stdlib.lang');actual=[]
        for row in cases:
            buffer=b.Unpooled.buffer();buffer.writeByte(len(row))
            for n in row:buffer.writeByte(n)
            value=u.read(buffer,32767);actual.append(','.join(str(ord(c)) for c in lang._utf16_units(value))+';'+str(buffer.readerIndex()))
        self.assertEqual(actual,expected)

    def test_limits_reader_indices_and_failure_before_write(self):
        p=Package();u=p.load('minecraft.utf8_codec');b=p.load('java_stdlib.byte_buffer');c=p.load('minecraft.network_codecs')
        buffer=b.Unpooled.buffer()
        with self.assertRaises(u.EncoderException):u.write(buffer,'abc',2)
        self.assertEqual(buffer.writerIndex(),0)
        for data,maxlen,consumed in [([3,65],5,1),([255,255,255,255,15],5,5),([3,65,66,67],2,4),([7,1,2,3,4,5,6,7],2,1)]:
            buffer=b.Unpooled.buffer()
            for n in data:buffer.writeByte(n)
            with self.assertRaises(u.DecoderException):u.read(buffer,maxlen)
            self.assertEqual(buffer.readerIndex(),consumed)
        buffer=b.Unpooled.buffer();c.ByteBufCodecs.STRING_UTF8.encode(buffer,'\U0001f603');self.assertEqual(c.ByteBufCodecs.STRING_UTF8.decode(buffer),'\U0001f603')

    def test_source_resource_codec_and_utf8_codec_actual_python2(self):
        source='import net.minecraft.resources.ResourceLocation;import net.minecraft.network.codec.ByteBufCodecs;import io.netty.buffer.ByteBuf;import io.netty.buffer.Unpooled;public class Run {public int run(){ByteBuf b=Unpooled.buffer();ResourceLocation r=ResourceLocation.fromNamespaceAndPath("demo","wire");ResourceLocation.STREAM_CODEC.encode(b,r);ResourceLocation q=ResourceLocation.STREAM_CODEC.decode(b);ByteBufCodecs.STRING_UTF8.encode(b,"hello");String s=ByteBufCodecs.STRING_UTF8.decode(b);return (q.equals(r)?100:0)+s.length()+b.readableBytes();}}'
        execution.OfficialInterfaces086().execute(source,'105')

if __name__=='__main__':unittest.main()
