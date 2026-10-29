import gc,sys,unittest,weakref
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harness import Package

class RuntimeHookTests(unittest.TestCase):
    def setUp(self):
        self.pkg=Package();self.hooks=self.pkg.load('neoforge.mixin_hooks');self.menu=self.pkg.load('minecraft.menu')
    def test_menu_tail_after_native_fields_before_derived_body_and_owner_cleanup(self):
        scope=self.hooks.MixinHooks.openScope('one');seen=[]
        replacement=self.menu.MenuType(lambda unused:None)
        def hook(receiver,args,ci):
            seen.append((receiver.containerId,len(receiver.slots),receiver._state_id,ci.getId(),ci.isCancellable(),args[1]))
            receiver.menuType=replacement
        scope.register(self.hooks.MENU_TAIL,hook)
        obj=self.menu.AbstractContainerMenu(None,8)
        self.assertEqual(seen,[(8,0,0,'<init>',False,8)])
        self.assertIs(obj.getType(),replacement)
        scope.close();self.assertEqual(self.hooks.MixinHooks.count(),0)
        self.menu.AbstractContainerMenu(None,9);self.assertEqual(len(seen),1)
        with self.assertRaises(RuntimeError):scope.register(self.hooks.MENU_TAIL,hook)
    def test_priority_stable_order_and_close_during_dispatch(self):
        one=self.hooks.MixinHooks.openScope(object());two=self.hooks.MixinHooks.openScope(object());trace=[]
        one.register(self.hooks.MENU_TAIL,lambda *args:(trace.append(1),two.close()),1500)
        two.register(self.hooks.MENU_TAIL,lambda *args:trace.append(2))
        one.register(self.hooks.MENU_TAIL,lambda *args:trace.append(3),500)
        self.menu.AbstractContainerMenu(None,1);self.assertEqual(trace,[1,3])
        one.close();two.close();self.assertEqual(self.hooks.MixinHooks.count(),0)
    def test_errors_are_not_swallowed_or_constructor_marked_complete(self):
        scope=self.hooks.MixinHooks.openScope('bad')
        def fail(*args):raise ValueError('original handler failure')
        scope.register(self.hooks.MENU_TAIL,fail)
        try:
            with self.assertRaisesRegex(ValueError,'original handler failure'):self.menu.AbstractContainerMenu(None,1)
            with self.assertRaises(ValueError):scope.register('unknown',fail)
        finally:scope.close()
        self.assertEqual(self.hooks.MixinHooks.count(),0)
    def test_shadow_replacement_does_not_retain_a_second_old_menu_type_field(self):
        scope=self.hooks.MixinHooks.openScope('replace')
        scope.register(self.hooks.MENU_TAIL,lambda receiver,args,ci:setattr(receiver,'menuType',None))
        try:
            token=self.menu.MenuType();ref=weakref.ref(token)
            obj=self.menu.AbstractContainerMenu(token,5);del token;gc.collect()
            self.assertIsNone(obj.menuType);self.assertIsNone(ref())
        finally:scope.close()

if __name__=='__main__':unittest.main()
