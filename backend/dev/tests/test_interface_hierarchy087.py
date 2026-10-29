import json,os,sys,tempfile,unittest,subprocess
from pathlib import Path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_interfaces082 as oracle
from translate_java import translate

class InterfaceHierarchy087(unittest.TestCase):
    def test_diamond_most_specific_default_and_redundant_bases(self):
        oracle.Interfaces082().compare({
            'api/A.java':'package api;public interface A {default int value(){return 1;}}',
            'api/B.java':'package api;public interface B extends A {default int value(){return 7;}}',
            'api/C.java':'package api;public interface C extends A {}',
            'use/Run.java':'package use;import api.A;import api.B;import api.C;public class Run implements A,C,B {public int run(){B b=this;return value()+b.value();}}'
        },'14')
    def test_interface_constants_static_methods_and_abstract_parent_calls(self):
        oracle.Interfaces082().compare({
            'api/A.java':'package api;public interface A {int N=3;static int plus(int v){return v+N;}int value();}',
            'api/B.java':'package api;public interface B extends A {default int twice(){return value()+value();}}',
            'use/Run.java':'package use;import api.A;import api.B;public class Run implements B {public int value(){return 4;}public int run(){B b=this;return b.twice()+A.plus(A.N);}}'
        },'14')
    def test_concrete_class_wins_default_and_redundant_implemented_parent(self):
        oracle.Interfaces082().compare({
            'api/A.java':'package api;public interface A {default int value(){return 1;}}',
            'base/Parent.java':'package base;import api.A;public class Parent implements A {public int value(){return 7;}}',
            'use/Run.java':'package use;import api.A;import base.Parent;public class Run extends Parent implements A {public int run(){return value();}}'
        },'7')
    def test_reabstract_cycle_and_noninherited_static_are_rejected(self):
        cases=[{'A':'interface A {default int value(){return 1;}}','B':'interface B extends A {int value();}','Run':'class Run implements B {}'},
               {'A':'interface A extends B {}','B':'interface B extends A {}','Run':'class Run implements A {}'},
               {'A':'interface A {static int value(){return 1;}}','Run':'class Run implements A {int run(){return value();}}'}]
        for files in cases:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                for name,source in files.items():(root/(name+'.java')).write_text(source)
                result=translate(root,dry_run=True)
                self.assertEqual(result['failed'],0,result)
                self.assertEqual(next(r for r in result['results'] if r['file']=='Run.java')['status'],'MANUAL_REVIEW',result)

    def test_defaults_from_independent_overload_interfaces_dispatch_by_signature(self):
        oracle.Interfaces082().compare({
            'api/A.java':'package api;public interface A {default int value(){return 3;}}',
            'api/B.java':'package api;public interface B {default int value(int n){return n+4;}}',
            'use/Run.java':'package use;import api.A;import api.B;public class Run implements A,B {public int run(){A a=this;B b=this;return value()+value(2)+a.value()+b.value(1);}}'
        },'17')

    def test_private_interface_helpers_are_owner_bound_and_static_not_inherited(self):
        oracle.Interfaces082().compare({
            'api/A.java':'package api;public interface A {private int inc(int n){return n+1;}default int value(){return inc(6);}private static int base(){return 3;}static int plus(){return base()+2;}}',
            'use/Run.java':'package use;import api.A;public class Run implements A {public int inc(int n){return 99;}public int run(){return value()+A.plus();}}'
        },'12')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'A.java').write_text('interface A {private static int value(){return 1;}}')
            (root/'Run.java').write_text('class Run {int run(){return A.value();}}')
            report=translate(root,dry_run=True)
            self.assertEqual(next(r for r in report['results'] if r['file']=='Run.java')['status'],'MANUAL_REVIEW',report)

    def test_covariant_return_satisfies_all_unrelated_abstract_contracts(self):
        oracle.Interfaces082().compare({
            'api/A.java':'package api;public interface A {Object value();}',
            'api/B.java':'package api;public interface B {String value();}',
            'use/Run.java':'package use;import api.A;import api.B;public class Run implements A,B {public String value(){return "yes";}public int run(){B b=this;return b.value().length();}}'
        },'3')

    def test_covariant_array_return_preserves_runtime_array(self):
        oracle.Interfaces082().compare({
            'api/A.java':'package api;public interface A {Object[] values();}',
            'use/Run.java':'package use;import api.A;public class Run implements A {public String[] values(){return new String[]{"yes"};}public int run(){A a=this;return a.values().length;}}'
        },'1')

    def test_qualified_source_default_super_bypasses_override_and_keeps_virtual_calls(self):
        oracle.Interfaces082().compare({
            'api/A.java':'package api;public interface A {default int value(){return helper();}default int helper(){return 1;}}',
            'api/B.java':'package api;public interface B {default int value(){return 4;}}',
            'use/Run.java':'package use;import api.A;import api.B;public class Run implements A,B {public int helper(){return 7;}public int value(){return A.super.value()+B.super.value();}public int run(){return value();}}'
        },'11')

    def test_qualified_source_default_super_inherited_and_varargs(self):
        oracle.Interfaces082().compare({
            'api/X.java':'package api;public interface X {default int value(int... values){return values.length;}}',
            'api/A.java':'package api;public interface A extends X {}',
            'use/Run.java':'package use;import api.A;public class Run implements A {public int value(int... values){return 99;}public int run(){return A.super.value(1,2,3);}}'
        },'3')

if __name__=='__main__':unittest.main()
