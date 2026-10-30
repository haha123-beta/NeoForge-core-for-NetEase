import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import Package
from java_frontend import parse_source, api_index
from java_codegen import generate, NeedsLowering
pkg = Package()
api = pkg.load('core.java_api')


class CodegenTests(unittest.TestCase):
    def test_int_bits_java_shift_distances_boolean_eager_and_core_version_guard(self):
        result, module = self.run_module('''class Bits {
 int calls=0;
 int unsigned(){return -1>>>1;}
 int signed(){return -1>>1;}
 int overflow(){return 1<<31;}
 int maskedDistance(){return -1>>>32;}
 int negativeDistance(){return 1<<-1;}
 int complement(){return ~0;}
 int xor(){return 0xff^0xaa;}
 int mask(){return (0xffff0000&0xff00ff00)|0x11;}
 boolean left(){calls++;return false;}
 boolean right(){calls++;return true;}
 boolean eager(){return left()&right();}
 int count(){return calls;}
}''')
        obj = module['Bits']()
        self.assertEqual([obj.unsigned(),obj.signed(),obj.overflow(),obj.maskedDistance(),
            obj.negativeDistance(),obj.complement(),obj.xor(),obj.mask()],
            [2147483647,-1,-2147483648,-1,-2147483648,-1,85,-16777199])
        self.assertFalse(obj.eager())
        self.assertEqual(obj.count(), 2)
        self.assertIn('neocore.runtime.Int32@2', result['required_runtime_helpers'])
        primitive = pkg.load('java_stdlib.primitives').Int32
        previous = primitive.ABI_VERSION
        scope = api.JavaApiImports(sys).install(api.collect_java_api())
        try:
            primitive.ABI_VERSION = 1
            with self.assertRaisesRegex(RuntimeError, 'update the independent core pack'):
                exec(result['python_source'], {})
        finally:
            primitive.ABI_VERSION = previous
            scope.close()
        with self.assertRaises(NeedsLowering):
            generate(parse_source('class X {long value(long x){return x>>>1;}}'))

    def test_mapped_nested_api_constructor_keeps_java_owner_and_member_names(self):
        result, module = self.run_module('''import net.minecraft.world.item.Item;
class Factory { Item create(){return new Item(new Item.Properties().stacksTo(16));} }''')
        self.assertEqual(module['Factory']().create().getMaxStackSize(), 16)
        self.assertIn('net.minecraft.world.item.Item.Properties', result['required_api_types'])
        self.assertIn("'Properties'", result['python_source'])
        known, _ = api_index()
        with self.assertRaises(NeedsLowering):
            generate(parse_source('import net.minecraft.world.item.Item; '
                'class Factory {Object create(){return new Item.Unknown();}}',known_types=known))
        # A known parent alone must not imply arbitrary nested members exist.
        with self.assertRaises(NeedsLowering):
            generate(parse_source('import net.minecraft.world.item.Item; '
                'class Factory {Object create(){return new Item.Properties();}}',
                known_types={'net.minecraft.world.item.Item'}))

    def test_java_integer_radices_signed_patterns_and_constant_unary(self):
        result, module = self.run_module('''class Literals {
 int hex(){return 0xFF_FF_FF_FF;}
 int octal(){return 0377;}
 int binary(){return 0b10000000_00000000_00000000_00000000;}
 int negate(){return -0x80000000;}
 int min(){return -2_147_483_648;}
 long minLong(){return -9_223_372_036_854_775_808L;}
 long longHex(){return 0xFFFF_FFFF_FFFF_FFFFL;}
 long widenedHex(){return 0xFFFF_FFFFL;}
 int signedOctal(){return 037777777777;}
 int arithmetic(){return 0xff+0b1;}
}''')
        obj = module['Literals']()
        self.assertEqual([obj.hex(),obj.octal(),obj.binary(),obj.negate(),obj.min(),obj.minLong(),obj.longHex(),obj.widenedHex(),obj.signedOctal(),obj.arithmetic()],
            [-1,255,-2147483648,-2147483648,-2147483648,-9223372036854775808,-1,4294967295,-1,256])
        for literal in ['2147483648','+2147483648','0x1_0000_0000','0b1_00000000_00000000_00000000_00000000',
                        '9223372036854775808L','0x1_0000_0000_0000_0000L']:
            with self.subTest(literal=literal), self.assertRaises(NeedsLowering):
                generate(parse_source('class X {long value(){return '+literal+';}}'))

    def test_do_while_first_iteration_continue_break_and_nested_scope(self):
        result, module = self.run_module('''class DoLoops {
 int once(){int n=0;do{n++;}while(false);return n;}
 int continuing(){int n=0,total=0;do{n++;if(n<3)continue;total+=n;}while(n<4);return total;}
 int breaking(){int n=0;do{n++;break;}while(n/0>0);return n;}
 int returning(){do{return 7;}while(false);}
 int nested(){int total=0;for(int i=0;i<2;i++){int n=0;do{n++;if(n==1)continue;total++;}while(n<3);}return total;}
 int scope(){do{int n=1;}while(false);int n=9;return n;}
}''')
        obj = module['DoLoops']()
        self.assertEqual(obj.once(), 1)
        self.assertEqual(obj.continuing(), 7)
        self.assertEqual(obj.breaking(), 1)
        self.assertEqual(obj.returning(), 7)
        self.assertEqual(obj.nested(), 4)
        self.assertEqual(obj.scope(), 9)
        with self.assertRaises(NeedsLowering):
            generate(parse_source('class X {void f(){do{int n=0;}while(n<1);}}'))

    def test_basic_for_update_continue_break_scope_and_empty_header(self):
        result, module = self.run_module('''class Loops {
 int sum(){int total=0; for(int i=0,j=1;i<5;i++,j+=2){
   if(i==1)continue; if(i==4)break; total+=j;
 } int i=9; return total+i; }
 int nested(){int n=0; for(int i=0;i<3;i++){
   int j=0; while(j<2){j++;continue;} n++;
 } return n; }
 int infinite(){int n=0; for(;;){n++; if(n==3)break;} return n;}
 int expressionInit(){int i=0; for(i=1;i<3;i++); return i;}
 int returning(){for(int i=0;i<3;i++){return i;} return 99;}
}''')
        obj = module['Loops']()
        self.assertEqual(obj.sum(), 22)
        self.assertEqual(obj.nested(), 3)
        self.assertEqual(obj.infinite(), 3)
        self.assertEqual(obj.expressionInit(), 3)
        self.assertEqual(obj.returning(), 0)
        with self.assertRaises(NeedsLowering):
            generate(parse_source('class X {int f(){for(int i=0;i<1;i++){} return i;}}'))

    def test_type_import_conflicts_and_duplicate_declarations_are_reported(self):
        for source, category in [
            ('import a.Helper; import b.Helper; class Main {}', 'import_conflict'),
            ('import a.Main; class Main {}', 'import_declaration_conflict'),
            ('class Main {} class Main {}', 'duplicate_type')]:
            with self.subTest(source=source), self.assertRaises(NeedsLowering) as caught:
                generate(parse_source(source))
            self.assertEqual(caught.exception.details['category'], category)
        result, module = self.run_module('''package demo;
import demo.Main;
import java.lang.SuppressWarnings;
import java.lang.SuppressWarnings;
@SuppressWarnings("unused") class Main { boolean is(){return true;} }''')
        self.assertTrue(getattr(module['Main'](), 'is')())
        self.assertNotIn('from demo.Main', result['python_source'])
        self.assertEqual(len(result['annotation_metadata']), 1)
        result, module = self.run_module('import java.lang.String; import java.lang.String; '
            'class Text { String value(){return new String("ok");} }')
        self.assertTrue(module['Text']().value().equals('ok'))

    def test_nullability_and_warning_annotations_are_retained_as_review_metadata(self):
        result, module = self.run_module('''import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import java.lang.SuppressWarnings;
@SuppressWarnings("unused") class Contracts {
 @NotNull("name required") String name(){return "ok";}
 @Nullable Object echo(@Nullable Object value){return value;}
}''')
        self.assertTrue(module['Contracts']().name().equals('ok'))
        self.assertIsNone(module['Contracts']().echo(None))
        records = result['annotation_metadata']
        self.assertEqual(len(records), 4)
        self.assertEqual({r['java_name'] for r in records}, {
            'org.jetbrains.annotations.NotNull', 'org.jetbrains.annotations.Nullable', 'java.lang.SuppressWarnings'})
        self.assertTrue(any(r['strategy']=='NULLABILITY_INSTRUMENTATION_REVIEW_REQUIRED' for r in records))
        self.assertIn('name required', next(r['source'] for r in records if r['name']=='NotNull'))
        self.assertNotIn('org.jetbrains', result['python_source'])
        self.assertEqual(result['status'], 'GENERATED_REVIEW_REQUIRED')

    def test_annotation_identity_shadowing_and_runtime_usage_are_not_guessed(self):
        from java_project_types import add_unit
        for source in [
            'import org.jetbrains.annotations.*; class A { @Nullable Object f(){return null;} }',
            'import org.jetbrains.annotations.Nullable; class A { Nullable value; }',
            'class A { org.jetbrains.annotations.Nullable value; }',
            '@EventBusSubscriber class A {}']:
            with self.subTest(source=source), self.assertRaises(NeedsLowering):
                generate(parse_source(source))
        index = {}
        add_unit(index, parse_source('package demo; @interface SuppressWarnings {}', 'demo/SuppressWarnings.java'))
        self.assertIn('demo.SuppressWarnings', index)
        self.assertEqual(index['demo.SuppressWarnings'][0]['kind'], 'annotation_type_declaration')
        with self.assertRaises(NeedsLowering):
            generate(parse_source('package demo; @SuppressWarnings class A {}'), index)

    def run_module(self, source):
        known, _ = api_index()
        result = generate(parse_source(source, known_types=known))
        scope = api.JavaApiImports(sys).install(api.collect_java_api())
        try:
            namespace = {}
            exec(result['python_source'], namespace)
            return result, namespace
        finally:
            scope.close()

    def test_constructor_fields_keyword_method_and_string_literals(self):
        result, module = self.run_module("""package original;
class Box {
  private int count=1;
  Box(int start) { this.count=start; }
  int read(){return count;}
  boolean is(){return true;}
  String hello(){return "中文";}
}
""")
        box = module['Box'](7)
        self.assertEqual(box.read(), 7)
        self.assertTrue(getattr(box, 'is')())
        self.assertTrue(box.hello().equals('中文'))
        self.assertEqual(result['package'], 'original')
        self.assertFalse(result['engine_verified'])
        self.assertEqual(result['status'], 'GENERATED_REVIEW_REQUIRED')

    def test_static_descriptor_and_original_receiver_method_call(self):
        result, module = self.run_module("""class Receiver {Object seen;void is(Object item){seen=item;}}class Bridge {
  static boolean is(){return true;}
  void call(Receiver receiver, Object item){ receiver.is(item); }
}
""")
        self.assertTrue(getattr(module['Bridge'], 'is')())
        self.assertTrue(getattr(module['Bridge'](), 'is')())
        receiver = module['Receiver']()
        marker = object()
        module['Bridge']().call(receiver, marker)
        self.assertIs(receiver.seen, marker)

    def test_boolean_branches_short_circuit_and_type_rejection(self):
        result, module = self.run_module("""class Flags {
  boolean enabled;
  Flags(boolean start){this.enabled=start;}
  boolean is(){return enabled;}
  boolean broken(){this.enabled=false;return true;}
  boolean check(boolean gate){return gate && broken();}
  boolean choose(boolean gate){return gate ? true : false;}
  void set(boolean flag){if(flag){this.enabled=true;}else{this.enabled=false;}}
}
""")
        flags = module['Flags'](True)
        self.assertFalse(flags.check(False))
        self.assertTrue(getattr(flags, 'is')())
        self.assertTrue(flags.check(True))
        self.assertFalse(getattr(flags, 'is')())
        flags.set(True)
        self.assertTrue(getattr(flags, 'is')())
        flags.set(False)
        self.assertFalse(getattr(flags, 'is')())
        self.assertTrue(flags.choose(True))
        self.assertFalse(flags.choose(False))
        with self.assertRaises(NeedsLowering):
            generate(parse_source('class Bad { void f(Object value){if(value){return;}} }'))

    def test_local_field_shadowing_and_block_visibility(self):
        result, module = self.run_module("""class Locals {
  boolean enabled=true;
  boolean check(){boolean enabled=false;return enabled;}
  boolean field(){return enabled;}
  boolean scoped(){if(true){boolean temp=false;}return enabled;}
}
""")
        value = module['Locals']()
        self.assertFalse(value.check())
        self.assertTrue(value.field())
        self.assertTrue(value.scoped())
        for source in (
            'class A { boolean f(){if(true){boolean temp=true;}return temp;} }',
            'class A { boolean flag=true; boolean f(){boolean flag=flag;return flag;} }',
        ):
            with self.assertRaises(NeedsLowering):
                generate(parse_source(source))
        generate(parse_source('class A { boolean f(){boolean value;return true;} }'))

    def test_int32_arithmetic_overflow_division_and_remainder(self):
        result, module = self.run_module("""class Numbers {
 int add(int a,int b){return a+b;}
 int sub(int a,int b){return a-b;}
 int mul(int a,int b){return a*b;}
 int div(int a,int b){return a/b;}
 int rem(int a,int b){return a%b;}
 int neg(int a){return -a;}
 int min(){return -2147483648;}
}
""")
        value = module['Numbers']()
        self.assertEqual(value.add(2147483647, 1), -2147483648)
        self.assertEqual(value.mul(65536, 65536), 0)
        self.assertEqual(value.div(-7, 3), -2)
        self.assertEqual(value.rem(-7, 3), -1)
        self.assertEqual(value.div(-2147483648, -1), -2147483648)
        self.assertEqual(value.rem(-2147483648, -1), 0)
        self.assertEqual(value.neg(-2147483648), -2147483648)
        self.assertEqual(value.min(), -2147483648)
        with self.assertRaises(pkg.load('java_stdlib.lang').ArithmeticException):
            value.div(1, 0)
        self.assertIn('neocore.runtime.Int32@1', result['required_runtime_helpers'])

    def test_while_compare_break_continue_and_field_updates(self):
        result, module = self.run_module("""class Loops {
 int ticks=0;
 int run(int limit){
   int count=0;
   while(count<limit){
     count=count+1;
     if(count==2){continue;}
     if(count==5){break;}
     this.ticks=this.ticks+1;
   }
   return ticks;
 }
}
""")
        self.assertEqual(module['Loops']().run(10), 3)
        self.assertEqual(module['Loops']().run(0), 0)
        _, identity_module = self.run_module('class A { boolean f(Object a,Object b){return a==b;} }')
        same = object()
        self.assertTrue(identity_module['A']().f(same, same))
        self.assertFalse(identity_module['A']().f(object(), object()))

    def test_compound_assignment_reads_old_field_before_rhs_side_effect(self):
        result, module = self.run_module("""class Compound {
 int value=10;
 int rhs(){this.value=100;return 2;}
 int run(){value+=rhs();return value;}
 int local(int a){a*=3;a-=1;return a;}
 int overflow(){this.value=2147483647;this.value+=1;return value;}
}
""")
        value = module['Compound']()
        self.assertEqual(value.run(), 12)
        self.assertEqual(value.local(4), 11)
        self.assertEqual(value.overflow(), -2147483648)
        with self.assertRaises(NeedsLowering):
            generate(parse_source('class A { byte value; void f(){value+=1;} }'))

    def test_update_statements_and_expression_result_is_not_discarded(self):
        result, module = self.run_module("""class Updates {
 int value=0;
 int run(int count){count++;++count;count--;--count;this.value++;return count;}
 int read(){return value;}
 int overflow(){this.value=2147483647;value++;return value;}
}
""")
        value = module['Updates']()
        self.assertEqual(value.run(4), 4)
        self.assertEqual(value.read(), 1)
        self.assertEqual(value.overflow(), -2147483648)
        with self.assertRaises(NeedsLowering):
            generate(parse_source('class A { int n=0; int f(){return n++;} }'))

    def test_unsupported_semantics_never_become_empty_success_methods(self):
        cases = [
            'class A { static void f(int x){} void f(String x){} }',
            'class A extends B {}',
            'class A { int f(){return 1;} static int f; }',
            'class A { void __init__() {} }',
        ]
        for source in cases:
            with self.assertRaises(NeedsLowering):
                generate(parse_source(source))


if __name__ == '__main__':
    unittest.main()
