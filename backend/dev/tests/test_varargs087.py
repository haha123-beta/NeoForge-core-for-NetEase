import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from java_frontend import parse_source
from java_codegen import generate,NeedsLowering
from java_official_probe import run_original
import test_official_interfaces086 as execution

class Varargs087(unittest.TestCase):
    def execute(self,source):
        expected=run_original(source.replace('public class Run','class Run')+'public class Probe {public static void main(String[] a){System.out.print(new Run().run());}}')
        execution.OfficialInterfaces086().execute(source,expected)
        return expected
    def test_interface_defaults_expanded_fixed_array_and_no_values(self):
        source='interface Values {int sum(int... values);default int twice(int n){return sum(n,n);}default int empty(){return sum();}}public class Run implements Values {public int sum(int... values){int n=0;for(int v:values)n=n+v;return n;}public int run(){Values v=this;return v.twice(7)+v.empty()+sum(new int[]{1,2,3})+sum(4);}}'
        self.assertEqual(self.execute(source),'24')
    def test_strict_fixed_phase_before_variable_phase_and_array_null(self):
        source='public class Run {int f(Object value){return 3;}int f(int... values){return values==null?7:values.length;}public int run(){return f(5)*100+f(1,2)*10+f((int[])null);}}'
        self.assertEqual(self.execute(source),'327')
    def test_most_specific_reference_varargs_and_empty(self):
        source='public class Run {int f(Object... values){return 1;}int f(String... values){return values.length+2;}public int run(){return f()*100+f("a","b")*10+f(new String[]{"a"});}}'
        self.assertEqual(self.execute(source),'243')
    def test_fixed_prefix_order_and_single_array_identity(self):
        source='public class Run {int n=0;int tick(){n=n+1;return n;}int f(int head,int... rest){return head*100+rest[0]*10+rest[1];}int[] identity(int... a){return a;}public int run(){int[] a=new int[]{1,2};int result=f(tick(),tick(),tick());return result+(identity(a)==a?1:0);}}'
        self.assertEqual(self.execute(source),'124')
    def test_interface_static_private_overloads(self):
        source='interface Values {private static int f(int n){return n;}private static int f(String s){return s.length();}default int number(){return f(3)+f("abcd");}}public class Run implements Values {public int run(){return number();}}'
        self.assertEqual(self.execute(source),'7')
    def test_unsupported_ambiguity_and_method_reference_fail_explicitly(self):
        for source in ['class Run {int f(String... a){return 1;}int f(Integer... a){return 2;}int run(){return f();}}','import java.util.function.Function;class Run {int f(int... a){return 1;}Function<Integer,Integer> x=Run::f;}']:
            with self.subTest(source=source),self.assertRaises(NeedsLowering):generate(parse_source(source))

if __name__=='__main__':unittest.main()
