# -*- coding: utf-8 -*-
"""
θ 层自测：minecraft/registries.py + minecraft/sound.py

真实依据（逐字来自反编译源码）：
    // HolderLookup.Provider 当读写存档的注册表上下文（12 个文件引用）
    protected void loadAdditional(CompoundTag tag, HolderLookup.Provider registries)
    protected void saveAdditional(CompoundTag tag, HolderLookup.Provider registries)

    // Holder<T>
    public static final DeferredHolder<CreativeModeTab, CreativeModeTab> MANAITA_PLUS_TAB;

    // TagKey
    public static final TagKey<Block> MINEABLE = BlockTags.create(ResourceLocation...)
    public TagKey<Block> getIncorrectBlocksForDrops()

    // SoundSource（20 次）
    new SimpleSoundInstance(soundtype.getHitSound(), SoundSource.BLOCKS, ...)

    // GameEvent（21 次）—— 注意第一个参数是 Holder
    level.gameEvent(GameEvent.BLOCK_PLACE, pos, GameEvent.Context.of(player, state))
    this.gameEvent(GameEvent.LIGHTNING_STRIKE);

验证点：
  1. Holder 的绑定语义（未绑定取 value 必须抛，不能静默返回 None）
  2. Holder 的属性转发
  3. HolderLookup 的查找、空查找器、getOrThrow 报错
  4. TagKey 的身份与比较
  5. SoundSource 常量的稳定性
  6. SoundEvent 的位置语义
  7. GameEvent 常量是 Holder（与 Java 类型一致）
  8. GameEvent.Context 的两种构造形态
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
registries = pkg.load("minecraft.registries")
sound = pkg.load("minecraft.sound")
level_mod = pkg.load("minecraft.level")
access_mod = pkg.load("minecraft.level_access")
core = pkg.load("minecraft.core")


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("Holder：绑定语义")
    # ------------------------------------------------------------
    Holder = registries.Holder

    bound = Holder(u"某个值", u"test:thing")
    check(u"已绑定", bound.isBound() is True)
    check(u"value() 取到值", bound.value() == u"某个值")
    check(u"get() 也取到", bound.get() == u"某个值")
    check(u"key() 保留键", bound.key() == u"test:thing")

    # 关键：未绑定时 value() 必须抛，不能返回 None。
    # Java 会抛 IllegalStateException，这样空引用当场暴露而不静默传播。
    unbound = Holder(None, u"test:pending")
    check(u"未绑定", unbound.isBound() is False)
    check(u"未绑定时 value() 抛异常", raises(unbound.value))
    check(u"但 get() 返回 None（探测用）", unbound.get() is None)

    unbound.bindValue(u"后来绑上的")
    check(u"bindValue 后已绑定", unbound.isBound() is True)
    check(u"bindValue 后可取值", unbound.value() == u"后来绑上的")

    check(u"direct 工厂", Holder.direct(u"x").value() == u"x")
    check(u"of 工厂", Holder.of(u"y").value() == u"y")

    # 属性转发
    class Thing(object):
        def __init__(self):
            self.label = u"标签"

        def describe(self):
            return u"描述"

    forwarded = Holder(Thing())
    check(u"属性转发到持有的值", forwarded.label == u"标签")
    check(u"方法转发", forwarded.describe() == u"描述")
    check(u"未绑定时转发报 AttributeError",
          raises(getattr, unbound if False else Holder(None), u"label"))

    # 身份
    check(u"同键相等",
          Holder(u"a", u"k") == Holder(u"b", u"k"))
    check(u"不同键不等",
          Holder(u"a", u"k1") != Holder(u"a", u"k2"))
    # 无键时按被持有值的身份比较：同一个对象才算相等
    shared = Thing()
    check(u"无键时同一对象相等", Holder(shared) == Holder(shared))
    check(u"无键时不同对象不等", Holder(Thing()) != Holder(Thing()))
    check(u"可作字典键",
          {Holder(u"a", u"k"): 1}[Holder(u"b", u"k")] == 1)
    check(u"toString 可读", u"某个值" in u"{}".format(bound))

    # dunder 不能被转发 —— 否则 hasattr 探测会变成真的调用能力。
    # 实测：hasattr(holder, "__iter__") 曾把被持有值的 iter() 拉起来，
    # 抛 TypeError: argument of type 'Holder' is not iterable。
    check(u"dunder 不被转发（hasattr 探测安全）",
          hasattr(bound, u"__iter__") is False)
    check(u"普通缺失属性也不被转发（抛 AttributeError 而不是乱来）",
          hasattr(bound, u"no_such_attr") is False)

    # ------------------------------------------------------------
    section("HolderLookup：注册表查找")
    # ------------------------------------------------------------
    lookup = registries.HolderLookup()
    check(u"初始为空", lookup.isEmpty() is True)

    stone_holder = lookup.register(u"block", u"stone", u"STONE")
    dirt_holder = lookup.register(u"block", u"dirt", u"DIRT")
    item_holder = lookup.register(u"item", u"diamond", u"DIAMOND")

    check(u"register 返回 Holder", isinstance(stone_holder, Holder))
    check(u"不再是空的", lookup.isEmpty() is False)
    check(u"按名字取到", lookup.get(u"stone") is stone_holder)
    check(u"取不存在的返回 None", lookup.get(u"nope") is None)

    check(u"listRegistryKeys", lookup.listRegistryKeys() == [u"block", u"item"],
          lookup.listRegistryKeys())
    check(u"listNames 全部",
          u"stone" in lookup.listNames() and u"diamond" in lookup.listNames())
    check(u"listNames 按注册表",
          lookup.listNames(u"block") == [u"dirt", u"stone"],
          lookup.listNames(u"block"))

    # getOrThrow：反序列化时找不到注册项是硬错误
    check(u"getOrThrow 命中", lookup.getOrThrow(u"stone") is stone_holder)
    check(u"getOrThrow 未命中抛异常", raises(lookup.getOrThrow, u"nope"))
    try:
        lookup.getOrThrow(u"missing_thing")
    except Exception as error:
        check(u"报错点名了缺少的项",
              u"missing_thing" in u"{}".format(error), u"{}".format(error)[:70])

    # lookup(注册表名) 得到一个限定到该注册表的子查找器
    block_lookup = lookup.lookup(u"block")
    check(u"lookup 得到子查找器", block_lookup.get(u"stone") is stone_holder)
    check(u"子查找器记录了 scope",
          block_lookup.getScope() == u"block", block_lookup.getScope())
    # 关键：子查找器**不能**看到别的注册表 —— 方块和物品都可能有
    # 同名项，混起来会取错东西。
    check(u"子查找器看不到别的注册表", block_lookup.get(u"diamond") is None)
    check(u"子查找器 listNames 被限定",
          block_lookup.listNames() == [u"dirt", u"stone"],
          block_lookup.listNames())
    check(u"子查找器仍非空", block_lookup.isEmpty() is False)

    # 未限定的查找器看全部
    check(u"未限定查找器能看到两个注册表",
          lookup.listRegistryKeys() == [u"block", u"item"])
    check(u"未限定查找器 default scope 是 None", lookup.getScope() is None)
    check(u"hasRegistry 判断", lookup.hasRegistry(u"block") is True
          and lookup.hasRegistry(u"nope") is False)

    # 关键：查不到的注册表要返回**空查找器**而不是 None。
    # 真实代码会直接在结果上 .getOrThrow(...)，返回 None 会 NPE；
    # 空查找器则给出「找不到 XXX」这种能看懂的错。
    missing_lookup = lookup.lookup(u"no_such_registry")
    check(u"未知注册表返回空查找器而不是 None", missing_lookup is not None)
    check(u"空查找器 isEmpty 为真", missing_lookup.isEmpty() is True)
    check(u"空查找器 getOrThrow 抛可读的错",
          raises(missing_lookup.getOrThrow, u"x"))

    # Provider 内部类写法
    check(u"HolderLookup.Provider 可用",
          registries.HolderLookup.Provider is registries.HolderLookup)
    check(u"Provider 可以当上下文传给方法",
          isinstance(registries.HolderLookup.Provider(), registries.HolderLookup))

    # ResourceKey 风格的名字也能吃
    check(u"lookup 接受带 registry() 的对象（ResourceKey 风格）",
          lookup.lookup(registries.TagKey(u"block", u"x")).get(u"stone")
          is stone_holder)

    # ------------------------------------------------------------
    section("RegistryAccess")
    # ------------------------------------------------------------
    access = registries.RegistryAccess(lookup)
    check(u"registryOrThrow 取到子查找器",
          access.registryOrThrow(u"block").get(u"stone") is stone_holder)
    check(u"lookupOrThrow 同上",
          access.lookupOrThrow(u"item").get(u"diamond") is item_holder)
    check(u"getLookup 取回底层", access.getLookup() is lookup)
    check(u"registries 列出名字",
          access.registries() == [u"block", u"item"], access.registries())
    check(u"默认构造可用", registries.RegistryAccess().registries() == [])

    # ------------------------------------------------------------
    section("TagKey")
    # ------------------------------------------------------------
    TagKey = registries.TagKey
    mineable = TagKey(u"block", u"minecraft:mineable/pickaxe")
    other = TagKey(u"block", u"minecraft:mineable/axe")

    check(u"location()", mineable.location() == u"minecraft:mineable/pickaxe",
          mineable.location())
    check(u"registry()", mineable.registry() == u"block")
    check(u"isFor 判断所属注册表", mineable.isFor(u"block") is True
          and mineable.isFor(u"item") is False)
    check(u"同标签相等",
          mineable == TagKey(u"block", u"minecraft:mineable/pickaxe"))
    check(u"不同标签不等", mineable != other)
    check(u"可作字典键",
          {mineable: 1}[TagKey(u"block", u"minecraft:mineable/pickaxe")] == 1)
    check(u"create 工厂",
          TagKey.create(u"item", u"t:x").registry() == u"item")
    check(u"toString 可读", u"mineable" in mineable.toString(),
          mineable.toString())

    # location 也接受带 toString 的对象（ResourceLocation）
    class FakeLocation(object):
        def toString(self):
            return u"mod:thing"

    check(u"location 接受 ResourceLocation 风格对象",
          TagKey(u"block", FakeLocation()).location() == u"mod:thing")

    # Tag 容器
    tag = registries.Tag()
    check(u"Tag 初始为空", tag.size() == 0)
    tag.add(stone_holder)
    tag.add(dirt_holder)
    check(u"Tag 有 2 项", tag.size() == 2, tag.size())
    check(u"contains 命中", tag.contains(stone_holder) is True)
    check(u"contains 未命中", tag.contains(item_holder) is False)
    check(u"可迭代", len(list(tag)) == 2)

    # ------------------------------------------------------------
    section("SoundSource")
    # ------------------------------------------------------------
    SoundSource = sound.SoundSource
    check(u"BLOCKS 存在（真实代码最常用）",
          SoundSource.BLOCKS.name() == u"BLOCKS")
    check(u"常量是稳定对象", SoundSource.BLOCKS is SoundSource.BLOCKS)
    check(u"不同常量不等", SoundSource.BLOCKS != SoundSource.MUSIC)
    check(u"按身份比较",
          (SoundSource.BLOCKS == SoundSource.BLOCKS) is True)
    check(u"可作字典键", {SoundSource.BLOCKS: 1}[SoundSource.BLOCKS] == 1)
    check(u"values 有 10 个", len(SoundSource.values()) == 10,
          len(SoundSource.values()))
    check(u"byName 命中", SoundSource.byName(u"blocks") is SoundSource.BLOCKS)
    check(u"byName 未命中抛异常", raises(SoundSource.byName, u"NOPE"))
    check(u"toString 是名字", SoundSource.BLOCKS.toString() == u"BLOCKS")
    check(u"MASTER/PLAYERS 等都在",
          all(getattr(SoundSource, n) is not None
              for n in (u"MASTER", u"MUSIC", u"RECORDS", u"WEATHER",
                        u"HOSTILE", u"NEUTRAL", u"PLAYERS", u"AMBIENT",
                        u"VOICE")))

    # ------------------------------------------------------------
    section("SoundEvent / SoundEvents")
    # ------------------------------------------------------------
    SoundEvent = sound.SoundEvent
    custom = SoundEvent.of(u"manaita_plus_legacy:cosmic")
    check(u"of 建出自定义音效", custom.location()
          == u"manaita_plus_legacy:cosmic", custom.location())
    check(u"同位置相等", custom == SoundEvent.of(u"manaita_plus_legacy:cosmic"))
    check(u"不同位置不等", custom != SoundEvent.of(u"other:sound"))
    check(u"可作字典键",
          {custom: 1}[SoundEvent.of(u"manaita_plus_legacy:cosmic")] == 1)
    check(u"默认传播范围是 16", custom.getRange() == 16.0, custom.getRange())

    fixed = SoundEvent.createFixedRangeEvent(u"t:far", 64.0)
    check(u"固定范围事件记录范围", fixed.getRange() == 64.0, fixed.getRange())

    sound.SoundEvents.clear()
    anvil = sound.SoundEvents.ANVIL_LAND
    check(u"SoundEvents 懒加载得到 SoundEvent",
          isinstance(anvil, SoundEvent))
    check(u"同名同对象", sound.SoundEvents.ANVIL_LAND is anvil)
    check(u"名字按约定生成",
          anvil.location() == u"minecraft:anvil_land", anvil.location())
    check(u"不同名不同对象",
          sound.SoundEvents.ANVIL_LAND is not sound.SoundEvents.ANVIL_USE)

    # ------------------------------------------------------------
    section("GameEvent：常量是 Holder")
    # ------------------------------------------------------------
    GameEvent = sound.GameEvent

    # 关键：Java 里 GameEvent.BLOCK_PLACE 的类型就是 Holder<GameEvent>，
    # level.gameEvent(...) 的第一个形参也是 Holder —— 所以这里必须是 Holder。
    check(u"BLOCK_PLACE 是 Holder",
          isinstance(GameEvent.BLOCK_PLACE, Holder),
          type(GameEvent.BLOCK_PLACE).__name__)
    check(u"Holder 里包的是 GameEvent",
          isinstance(GameEvent.BLOCK_PLACE.value(), GameEvent))
    check(u"BLOCK_PLACE 已绑定", GameEvent.BLOCK_PLACE.isBound() is True)

    check(u"常量稳定", GameEvent.BLOCK_PLACE is GameEvent.BLOCK_PLACE)
    check(u"不同事件不同对象",
          GameEvent.BLOCK_PLACE is not GameEvent.BLOCK_DESTROY)
    check(u"名字正确",
          GameEvent.BLOCK_PLACE.value().name() == u"minecraft:block_place",
          GameEvent.BLOCK_PLACE.value().name())

    check(u"LIGHTNING_STRIKE 存在（真实代码用了）",
          GameEvent.LIGHTNING_STRIKE is not None)
    check(u"BLOCK_CHANGE 存在", GameEvent.BLOCK_CHANGE is not None)

    check(u"通知半径按事件区分（雷击比放方块远）",
          GameEvent.LIGHTNING_STRIKE.value().getRadius()
          > GameEvent.BLOCK_PLACE.value().getRadius(),
          (GameEvent.LIGHTNING_STRIKE.value().getRadius(),
           GameEvent.BLOCK_PLACE.value().getRadius()))

    check(u"byName 命中", GameEvent.byName(u"block_place")
          is GameEvent.BLOCK_PLACE)
    check(u"byName 未命中抛异常", raises(GameEvent.byName, u"NOPE"))
    check(u"values 覆盖全部常量",
          len(GameEvent.values()) == len(GameEvent._CONSTANT_NAMES),
          (len(GameEvent.values()), len(GameEvent._CONSTANT_NAMES)))

    # Context：真实代码两种形态
    player = u"某玩家"
    context_both = GameEvent.Context.of(player, u"某方块状态")
    check(u"Context.of(实体, 状态)",
          context_both.sourceEntity() == player
          and context_both.affectedState() == u"某方块状态")
    context_entity = GameEvent.Context.of(player)
    check(u"Context.of(实体)（第二参可省）",
          context_entity.sourceEntity() == player
          and context_entity.affectedState() is None)
    check(u"Context.EMPTY 存在", GameEvent.Context.EMPTY is not None)
    check(u"EMPTY 没有实体", GameEvent.Context.EMPTY.sourceEntity() is None)
    check(u"Context 内部类写法",
          sound.GameEvent.Context is sound.GameEvent_Context)

    # ------------------------------------------------------------
    section("与 Level.gameEvent 联动")
    # ------------------------------------------------------------
    access = access_mod.InMemoryLevelAccess()
    world = level_mod.Level.wrap(access)
    pos = core.BlockPos(1, 2, 3)

    world.gameEvent(GameEvent.BLOCK_PLACE, pos,
                    GameEvent.Context.of(player, u"state"))
    check(u"gameEvent 被世界记录", len(access.game_events) == 1,
          access.game_events)
    recorded_holder = access.game_events[0][0]
    check(u"记录的第一个参数就是 Holder 本身",
          recorded_holder is GameEvent.BLOCK_PLACE, recorded_holder)
    check(u"位置被归一化", access.game_events[0][1] == (1, 2, 3),
          access.game_events[0][1])
    check(u"上下文也传下去了",
          access.game_events[0][2].sourceEntity() == player)

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in (
        "net.minecraft.core.Holder",
        "net.minecraft.core.HolderLookup",
        "net.minecraft.core.HolderLookup$Provider",
        "net.minecraft.core.RegistryAccess",
        "net.minecraft.tags.TagKey",
        "net.minecraft.tags.Tag",
    ):
        check(u"registries 映射 {}".format(java_name),
              java_name in registries.JAVA_MAP)

    for java_name in (
        "net.minecraft.sounds.SoundSource",
        "net.minecraft.sounds.SoundEvent",
        "net.minecraft.sounds.SoundEvents",
        "net.minecraft.world.level.gameevent.GameEvent",
        "net.minecraft.world.level.gameevent.GameEvent$Context",
    ):
        check(u"sound 映射 {}".format(java_name), java_name in sound.JAVA_MAP)

finally:
    sound.SoundEvents.clear()

sys.exit(summary())
