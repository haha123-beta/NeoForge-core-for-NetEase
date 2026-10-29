import os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_source_generics087 as execution
from java_frontend import api_index,parse_source
from java_codegen import generate,NeedsLowering

class DefiniteAssignment087(unittest.TestCase):
    def execute(self,body,expected):execution.SourceGenerics087().execute({'Run.java':body},expected)

    def test_straight_store_nested_scope_and_if_else_merge(self):
        self.execute('public class Run {int choose(boolean b){int x;if(b){x=3;}else{x=4;}return x;}public int run(){int y;{y=5;}return choose(true)+choose(false)+y;}}','12')

    def test_short_circuit_true_path_and_return_join(self):
        self.execute('public class Run {int choose(boolean b){int x;if(b&&(x=4)>0)return x;return 1;}public int run(){return choose(true)+choose(false);}}','5')

    def test_short_circuit_or_false_path_and_negation(self):
        self.execute('public class Run {int choose(boolean b){int x;if(b||(x=0)>0)return 8;return x;}int other(boolean b){int x;if(!(b&&(x=3)>0))return 2;return x;}public int run(){return choose(false)+choose(true)+other(false)+other(true);}}','13')

    def test_ternary_stores_both_paths_left_to_right_and_single_evaluation(self):
        self.execute('public class Run {int calls=0;int next(){calls++;return calls;}int choose(boolean b){int x;int y=b?(x=next()):(x=next());return x+y;}public int run(){return choose(true)*10+choose(false)+calls;}}','26')

    def test_delayed_local_inside_lambda_does_not_escape_assignment_facts(self):
        self.execute('import java.lang.Runnable;public class Run {int value=0;public int run(){Runnable r=()->{int x;x=6;value=x;};r.run();return value;}}','6')

    def test_do_body_precedes_condition_and_for_update_follows_body(self):
        self.execute('public class Run {public int run(){int x;do{x=5;}while(x<0);int total=0;int y;for(int i=0;i<3;total=total+y){y=i;i++;}return total+x;}}','8')

    def test_unassigned_paths_reads_self_initialization_and_exception_paths_reject(self):
        known,_=api_index()
        cases=['int x;return x;','int x;x=x+1;return x;','int x;if(b)x=3;return x;','int x;boolean c=b&&(x=3)>0;return x;','int x;while(b){x=3;}return x;','int x;try {if(b)throw new RuntimeException();x=3;}catch(RuntimeException e){return x;}return 1;','int x;int y=b?(x=3):1;return x;','int x;do{return x;}while((x=2)>0);','int x;for(int i=0;i<2;x=3){return x;}return 0;','int x;do {if(b)break;x=3;}while(false);return x;']
        for body in cases:
            with self.subTest(body=body),self.assertRaises(NeedsLowering):generate(parse_source('public class Run {int test(boolean b){'+body+'}}',known_types=known))

if __name__=='__main__':unittest.main()
