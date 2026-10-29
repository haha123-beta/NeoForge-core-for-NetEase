"""Evidence categories and strict reuse of the existing Objects runtime."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.neocore_gui_092.diagnostic_contract import file_diagnostic, summarize
from java_frontend import parse_source, api_index
from java_codegen import generate, NeedsLowering
import test_interfaces082 as oracle

class Takeover096(unittest.TestCase):
    def test_reason_text_never_guesses_category(self):
        row=dict(file='X.java',status='MANUAL_REVIEW',line=7,reason='Unresolved external import: fake.Block',details={})
        diagnostic=file_diagnostic(row)
        self.assertEqual(diagnostic['first_blocker']['category'],'unknown')
        row['details']={'category':'EXTERNAL_ABI_REQUIRED','symbol':'net.minecraft.X'}
        classified=file_diagnostic(row)
        self.assertEqual(classified['first_blocker']['category'],'official_api')
        self.assertIsNone(classified['first_blocker']['java']['descriptor'])

    def test_static_and_observed_evidence_stay_distinct_and_groups_use_symbol(self):
        rows=[dict(file=n,status='MANUAL_REVIEW',reason='first',details={'category':'EXTERNAL_ABI_REQUIRED','symbol':s},
            additional_requirements=[{'symbol':'other.Type','evidence':'STATIC_IMPORT_ONLY'}])
            for n,s in [('A.java','net.minecraft.X'),('B.java','net.minecraft.X'),('C.java','net.minecraft.Y')]]
        summary=summarize([{'results':rows}])
        self.assertEqual(len(summary['shared_blockers']),2)
        self.assertEqual(summary['category_counts'],{'official_api':3})
        self.assertEqual(summary['files'][0]['additional_requirements'][0]['evidence'],'STATIC_IMPORT_ONLY')
        self.assertIsNone(file_diagnostic(dict(file='Good.java',status='GENERATED_REVIEW_REQUIRED'))['first_blocker'])

    def test_require_nonnull_preserves_reference_type_across_three_runtimes(self):
        oracle.Interfaces082().compare({'use/Run.java':'''package use;
import java.util.Objects;
public class Run { public String run(){String x="value";String y=Objects.requireNonNull(x,"reason");
return Objects.requireNonNull(y);}}'''},'value')

    def test_null_throws_in_three_runtimes(self):
        oracle.Interfaces082().compare({'use/Run.java':'''package use;
import java.util.Objects;
public class Run {public int run(){String x=null;try {Objects.requireNonNull(x,"");return 0;}
catch(NullPointerException e){return 7;}}}'''},'7')

    def test_unreviewed_supplier_message_and_primitive_inference_remain_blocked(self):
        known,_=api_index()
        for expression in ('Objects.requireNonNull(7)', 'Objects.requireNonNull(x,()->"message")'):
            source='import java.util.Objects; public class Run {public Object run(String x){return '+expression+';}}'
            with self.subTest(expression=expression),self.assertRaises(NeedsLowering):
                generate(parse_source(source,known_types=known))

if __name__=='__main__':unittest.main()
