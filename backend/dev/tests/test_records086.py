import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_interfaces082 as helper
from translate_java import translate
from harness import Package

class Records086(unittest.TestCase):
    def test_components_accessor_object_methods_against_jdk_and_python2(self):
        helper.Interfaces082().compare({
            'demo/R.java':'package demo;public record R(int x,boolean enabled,String name){public int x(){return x+1;}public int sum(){return x+x();}}',
            'use/Run.java':'package use;import demo.R;public class Run {public String run(){R a=new R(-7,true,"hello");R b=new R(-7,true,"hello");R c=new R(-6,true,"hello");return a.toString()+"|"+a.hashCode()+"|"+a.equals(b)+"|"+a.equals(c)+"|"+a.equals(null)+"|"+a.sum();}}'
        },'R[x=-7, enabled=true, name=hello]|99193756|true|false|false|-13')

    def test_record_accessors_implement_source_interface_and_empty_record(self):
        helper.Interfaces082().compare({
            'demo/Named.java':'package demo;public interface Named {String name();}',
            'demo/NamedValue.java':'package demo;public record NamedValue(String name) implements Named {}',
            'demo/Empty.java':'package demo;public record Empty() {}',
            'use/Run.java':'package use;import demo.NamedValue;import demo.Empty;public class Run {public String run(){NamedValue a=new NamedValue(null);return a.toString()+"|"+new Empty().hashCode()+"|"+new Empty().equals(new Empty());}}'
        },'NamedValue[name=null]|0|true')

    def test_signed_components_and_explicit_integer_casts(self):
        helper.Interfaces082().compare({
            'demo/Bits.java':'package demo;public record Bits(byte b,short s,long l) {}',
            'use/Run.java':'package use;import demo.Bits;public class Run {public String run(){Bits b=new Bits((byte)255,(short)65535,-1L);return b.toString()+"|"+b.hashCode();}}'
        },'Bits[b=-1, s=-1, l=-1]|-992')

    def test_readonly_fields_constructor_types_and_unsupported_shapes_reject(self):
        sources=['record Run(int x){public Run {}}','record Run<T>(T x){}','class Run {record Nested(int x){}}','record Run(float x){}','record Run(@Deprecated int x){}','record Run(int x){void bad(){x=2;}}','record Run(int x){void bad(){this.x++;}}','record Run(int x){}class Other extends Run {Other(){super(1);}}','record Run(int x){}class Other {int get(){return new Run(2).x;}}','record Run(int x){}class Other {Run bad(){return new Run(true);}}']
        for source in sources:
            with self.subTest(source=source),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'Run.java').write_text(source);r=translate(root,dry_run=True)
                self.assertEqual((r['generated_for_review'],r['manual_review'],r['failed']),(0,1,0),r)
        p=Package();v=p.load('java_stdlib.records')
        class Fake(v.RecordBase):
            _nc_JavaName='Fake';_nc_RecordComponents=(('x','int','_nc_record_0'),)
            def __init__(self):object.__setattr__(self,'_nc_record_0',1);object.__setattr__(self,'_nc_record_sealed',True)
        a=Fake()
        with self.assertRaises(AttributeError):a._nc_record_0=2
        with self.assertRaises(AttributeError):del a._nc_record_0

if __name__=='__main__':unittest.main()
