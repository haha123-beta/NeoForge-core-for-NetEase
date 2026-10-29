import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_java_arrays as helper
pkg = helper.pkg
from java_codegen import NeedsLowering

PREFIX = '''import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Level;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.nbt.CompoundTag;
'''
BODY = '''class A extends Entity {
    public int observed;
    public int value=7;
    public int ticks;
    public A(EntityType type, Level level){super(type,level);}
    protected void defineSynchedData(SynchedEntityData.Builder builder){observed=value;}
    protected void addAdditionalSaveData(CompoundTag tag){tag.putInt("Value",value);}
    protected void readAdditionalSaveData(CompoundTag tag){value=tag.getInt("Value");}
    public void tick(){super.tick();ticks++;}
    public void capture(CompoundTag tag){saveWithoutId(tag);}
    public void restore(CompoundTag tag){load(tag);}
}'''
CASES = [BODY,
    BODY.replace('public int ticks;', 'public int ticks; protected void defineSynchedData(int n){value=90;} protected void addAdditionalSaveData(int n){value=80;} protected void readAdditionalSaveData(int n){value=70;}'),
    BODY.replace('public A(EntityType type, Level level){super(type,level);}',
        'public A(EntityType type,Level level){this(type,level,5);}public A(EntityType type,Level level,int n){super(type,level);value+=n;}'),
    BODY + 'class B extends A {public B(EntityType type,Level level){super(type,level);}public void tick(){super.tick();ticks+=2;}}']


class EntitySuperclassTests(unittest.TestCase):
    def generate(self, source=BODY): return helper.ArrayTests().python(PREFIX + source)
    def world(self):
        access = pkg.load('minecraft.level_access').InMemoryLevelAccess()
        level = pkg.load('minecraft.level').ServerLevel(access)
        kind = pkg.load('minecraft.entity').EntityType.of('r48:probe')
        return kind, level
    def test_constructor_virtual_hook_tick_save_and_load(self):
        scope, generated = self.generate()
        kind, level = self.world()
        entity = scope['A'](kind, level)
        self.assertEqual((entity.observed, entity.value, entity.ticks), (0, 7, 0))
        self.assertIs(entity.getType(), kind)
        self.assertIs(entity.level(), level)
        entity.tick(); self.assertEqual((entity.ticks, entity.tickCount), (1, 1))
        tag = pkg.load('minecraft.nbt').CompoundTag()
        entity.capture(tag); self.assertEqual(tag.getInt('Value'), 7)
        entity.value = 20; entity.restore(tag); self.assertEqual(entity.value, 7)
        self.assertIn('neocore.runtime.RuntimeClasses@3', generated['required_runtime_helpers'])
    def test_abstract_contract_and_final_methods_are_checked(self):
        for source in ('class A extends Entity {}', BODY.replace('public void tick()', 'public void discard()'),
                       BODY.replace('protected void readAdditionalSaveData', 'private void readAdditionalSaveData')):
            with self.subTest(source=source), self.assertRaises(NeedsLowering): self.generate(source)
    def test_overloaded_hooks_keep_compile_time_signatures(self):
        source = BODY.replace('public int ticks;', 'public int ticks; protected void defineSynchedData(int n){value=90;} protected void addAdditionalSaveData(int n){value=80;} protected void readAdditionalSaveData(int n){value=70;}')
        scope, _ = self.generate(source)
        kind, level = self.world()
        entity = scope['A'](kind, level)
        tag = pkg.load('minecraft.nbt').CompoundTag()
        entity.capture(tag); entity.value = 0; entity.restore(tag)
        self.assertEqual((entity.observed, entity.value), (0, 7))
    def test_jdk_constructor_delegation_virtual_overloads_and_source_inheritance(self):
        from entity_jdk_oracle import compare
        for index, body in enumerate(CASES):
            with self.subTest(index=index):
                scope, _ = self.generate(body)
                kind, level = self.world()
                name = 'B' if index == 3 else 'A'
                obj = scope[name](kind, level)
                obj.tick(); tag = pkg.load('minecraft.nbt').CompoundTag()
                obj.capture(tag); obj.value = 20; obj.restore(tag)
                actual = ':'.join(str(value) for value in (obj.observed, obj.value, obj.ticks, obj.tickCount, tag.getInt('Value')))
                self.assertEqual(actual, compare(PREFIX + body, name))
    def test_runtime_typed_call_reference_and_invalid_constructor(self):
        scope, _ = self.generate(BODY + '''class Logic {
            static void advance(Entity target){target.tick();}
            static boolean removed(Entity target){return target.isRemoved();}
            static java.lang.Runnable task(Entity target){return target::tick;}
        }''')
        kind, level = self.world(); obj = scope['A'](kind, level)
        scope['Logic'].advance(obj); scope['Logic'].task(obj).run()
        self.assertEqual(obj.ticks, 2); self.assertFalse(scope['Logic'].removed(obj))
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException): scope['A'](None, level)
        with self.assertRaises(TypeError): scope['A'](object(), level)
        with self.assertRaises(pkg.load('java_stdlib.lang').NullPointerException): scope['Logic'].task(None)
    def test_private_storage_abstract_super_and_unreviewed_parent_stay_blocked(self):
        for source in (BODY.replace('public int ticks;', 'public int ticks; int _level_wrapper;'),
            BODY.replace('observed=value;', 'super.defineSynchedData(builder);'),
            'class A extends net.minecraft.world.entity.LivingEntity {}',
            'class Logic {Entity create(EntityType type,Level level){return new Entity(type,level);}}'):
            with self.subTest(source=source), self.assertRaises(NeedsLowering): self.generate(source)


if __name__ == '__main__': unittest.main()
