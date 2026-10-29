import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harness import Package

class DiagnosticCleanupTests(unittest.TestCase):
    def test_cleanup_continues_past_broken_error_formatting_and_clears_callbacks(self):
        module=Package().load('core.translated_loader');context=module.ModContext({'mod_id':'diagnostic'})
        calls=[]
        class Broken(Exception):
            def __str__(self):raise ValueError('broken str')
            def __repr__(self):raise ValueError('broken repr')
        def last():calls.append('last')
        def first():calls.append('first')
        def fail():calls.append('fail');raise Broken()
        context.on_close(last);context.on_close(fail);context.on_close(first)
        errors=context.close()
        self.assertEqual(calls,['first','fail','last']);self.assertEqual(len(errors),1)
        self.assertEqual(context._cleanup,[]);self.assertEqual(context.game_bus.listenerCount(),0)
        self.assertEqual(context.close(),errors)

if __name__=='__main__':unittest.main()
