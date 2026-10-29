# -*- coding: utf-8 -*-
"""
β 层自测：neoforge/registries.py + neoforge/event.py

真实依据（都来自反编译源码，不是凭空设计）：
    @Mod(value = "manaita_plus_legacy")
    public class ManaitaPlusLegacy {
        public static final DeferredRegister<Block> BLOCKS =
            DeferredRegister.createBlocks("manaita_plus_legacy");
        public static final DeferredRegister<Item> ITEMS =
            DeferredRegister.create(BuiltInRegistries.ITEM, "manaita_plus_legacy");

        public ManaitaPlusLegacy(IEventBus modEventBus, ModContainer c) {
            BLOCKS.register(modEventBus);
            ITEMS.register(modEventBus);
        }
    }

    @EventBusSubscriber(modid = "manaita_plus_legacy", value = {Dist.CLIENT})
    public class Handler {
        @SubscribeEvent
        public static void clientTick(ClientTickEvent.Post event) { ... }
    }

验证点：
  1. ResourceLocation / ResourceKey 的解析与比较
  2. DeferredRegister 的三种创建方式 + 登记项 + 惰性求值
  3. DeferredHolder 能当被注册对象本身用（属性转发）
  4. 事件总线的订阅、按类型派发、单个监听器出错不影响其它
  5. @SubscribeEvent 的签名校验（写错当场报错，而不是运行时才炸）
  6. @EventBusSubscriber 的装配与 Dist 过滤
  7. 端到端：一个 mini 模组按真实写法跑一遍完整启动流程
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
registries = pkg.load("neoforge.registries")
Block = pkg.load("minecraft.block").Block
event = pkg.load("neoforge.event")


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("ResourceLocation")
    # ------------------------------------------------------------
    loc = registries.ResourceLocation(u"manaita_plus_legacy", u"crafting_manaita")
    check(u"带命名空间", loc.toString() == u"manaita_plus_legacy:crafting_manaita",
          loc.toString())
    check(u"getNamespace / getPath",
          loc.getNamespace() == u"manaita_plus_legacy"
          and loc.getPath() == u"crafting_manaita")
    check(u"省略命名空间时默认 minecraft",
          registries.ResourceLocation(u"stone").toString() == u"minecraft:stone",
          registries.ResourceLocation(u"stone").toString())
    check(u"字符串解析带冒号",
          registries.ResourceLocation.parse(u"a:b").getNamespace() == u"a")
    check(u"相等比较",
          registries.ResourceLocation(u"a:b") == registries.ResourceLocation(u"a:b"))
    check(u"不等比较",
          registries.ResourceLocation(u"a:b") != registries.ResourceLocation(u"a:c"))
    check(u"可作字典键",
          {registries.ResourceLocation(u"a:b"): 1}[registries.ResourceLocation(u"a:b")] == 1)

    # ------------------------------------------------------------
    section("注册表集合")
    # ------------------------------------------------------------
    check(u"BuiltInRegistries.ITEM 是 Registry",
          isinstance(registries.BUILT_IN_REGISTRIES.ITEM, registries.Registry))
    check(u"同名注册表始终同一对象",
          registries.BUILT_IN_REGISTRIES.ITEM is registries.BUILT_IN_REGISTRIES.ITEM)
    check(u"不同注册表是不同对象",
          registries.BUILT_IN_REGISTRIES.ITEM
          is not registries.BUILT_IN_REGISTRIES.BLOCK)
    check(u"拼错注册表名会报错",
          raises(getattr, registries.BUILT_IN_REGISTRIES, u"NOT_A_REGISTRY"))

    check(u"Registries.CREATIVE_MODE_TAB 是 ResourceKey",
          isinstance(registries.REGISTRIES.CREATIVE_MODE_TAB,
                     registries.ResourceKey))
    check(u"ResourceKey 带注册表名",
          registries.REGISTRIES.CREATIVE_MODE_TAB.registry()
          == u"minecraft:creative_mode_tab",
          registries.REGISTRIES.CREATIVE_MODE_TAB.registry())
    check(u"NeoForgeRegistries.Keys.INGREDIENT 是 ResourceKey",
          isinstance(registries.NEOFORGE_REGISTRIES.Keys.INGREDIENT,
                     registries.ResourceKey))

    # ------------------------------------------------------------
    section("DeferredRegister：三种创建方式")
    # ------------------------------------------------------------
    # 真实源码里三种都出现过
    blocks = registries.DeferredRegister.createBlocks(u"test_mod")
    check(u"createBlocks 注册表是 block",
          blocks.registry_key.registry() == u"minecraft:block",
          blocks.registry_key.registry())
    items = registries.DeferredRegister.create(
        registries.BUILT_IN_REGISTRIES.ITEM, u"test_mod")
    check(u"create(注册表实例) 得到 item 键",
          items.registry_key.registry() == u"minecraft:item",
          items.registry_key.registry())
    tabs = registries.DeferredRegister.create(
        registries.REGISTRIES.CREATIVE_MODE_TAB, u"test_mod")
    check(u"create(ResourceKey) 得到对应键",
          tabs.registry_key.registry() == u"minecraft:creative_mode_tab",
          tabs.registry_key.registry())

    # ------------------------------------------------------------
    section("DeferredHolder：惰性求值")
    # ------------------------------------------------------------
    created = []

    class FakeBlock(Block):
        def __init__(self):
            Block.__init__(self)
            created.append(self)
            self.name = u"fake_block"

    holder = blocks.register(u"crafting_manaita", FakeBlock)
    check(u"register 返回 DeferredHolder",
          isinstance(holder, registries.DeferredHolder))
    check(u"登记时**不**创建对象（惰性）", created == [], created)

    check(u"Unbound get raises before registration", raises(holder.get))
    check(u"Unbound reads leave supplier untouched", created == [])
    check(u"Factory does not imply binding", holder.isBound() is False)
    blocks.freeze_and_register(registries.BUILT_IN_REGISTRIES.BLOCK)
    value = holder.get()
    check(u"Registration barrier creates object once", created == [value], len(created))
    check(u"再次 get() 复用同一对象", holder.get() is value)
    check(u"getId 是完整位置",
          holder.getId().toString() == u"test_mod:crafting_manaita",
          holder.getId().toString())

    # 属性转发：把 holder 当被注册对象本身用
    check(u"holder 可直接读对象属性", holder.name == u"fake_block", holder.name)
    check(u"hasattr 也能穿透", hasattr(holder, u"name"))
    check(u"未绑定的属性仍报 AttributeError",
          not hasattr(holder, u"no_such_attribute"))

    check(u"路径冲突会报错", raises(blocks.register, u"crafting_manaita", FakeBlock))

    # ------------------------------------------------------------
    section("DeferredHolder：没有工厂时报错而不是静默 None")
    # ------------------------------------------------------------
    orphan = registries.DeferredHolder(blocks.registry_key, registries.ResourceLocation(u"test_mod", u"no_factory_here"))
    check(u"没有工厂的 holder 取值为 None 吗？不，应抛异常",
          raises(orphan.get))
    check(u"isBound 反映是否有工厂", orphan.isBound() is False)
    orphan.bindValue(u"bound")
    check(u"bindValue 之后可取值", orphan.get() == u"bound")

    # ------------------------------------------------------------
    section("freeze_and_register：真正建对象并写表")
    # ------------------------------------------------------------
    registry = registries.Registry(u"minecraft:block")
    fresh = registries.DeferredRegister.createBlocks(u"test_mod")
    fresh.register(u"a", FakeBlock)
    fresh.register(u"b", FakeBlock)
    result = fresh.freeze_and_register(registry)
    check(u"两个条目都建出来了", len(result) == 2, sorted(result.keys()))
    check(u"写进了注册表", registry.size() == 2, registry.size())
    check(u"注册表能按位置取回",
          registry.get(u"test_mod:a") is not None)
    check(u"冻结后不能再登记", raises(fresh.register, u"c", FakeBlock))

    # Factory-less holders exercise the generic internal registry path. Typed
    # Blocks requires a real Block supplier and rejects a null factory earlier.
    broken = registries.DeferredRegister.create(registries.REGISTRIES.BLOCK, u"broken_mod")
    broken.register(u"ok", FakeBlock)
    broken.register(u"bad")            # 没有工厂
    check(u"有条目建不出来时抛异常", raises(broken.freeze_and_register))
    try:
        broken.freeze_and_register()
    except Exception as error:
        check(u"异常信息里点名了出问题的条目",
              u"bad" in u"{}".format(error), u"{}".format(error)[:80])

    # ------------------------------------------------------------
    section("事件总线：订阅与派发")
    # ------------------------------------------------------------
    bus = event.IEventBus(u"test_bus")
    received = []

    def on_tick(e):
        received.append(u"tick")

    def on_key(e):
        received.append(u"key")

    bus.subscribe(on_tick, event.ClientTickEvent.Post)
    bus.subscribe(on_key, event.InputEvent.Key)
    check(u"监听器数", bus.listenerCount() == 2, bus.listenerCount())

    bus.post(event.ClientTickEvent.Post())
    check(u"只触发匹配的监听器", received == [u"tick"], received)
    bus.post(event.InputEvent.Key())
    check(u"第二个监听器被触发", received == [u"tick", u"key"], received)
    check(u"派发过的事件被记录", len(bus.posted) == 2, len(bus.posted))

    # 订阅所有事件
    all_received = []
    bus.subscribe(lambda e: all_received.append(type(e).__name__))
    bus.post(event.RenderFrameEvent.Pre())
    check(u"不指定类型时订阅所有事件",
          all_received == [u"Pre"], all_received)

    # 按父类匹配
    parent_received = []
    bus.subscribe(lambda e: parent_received.append(1), event.ClientTickEvent)
    bus.post(event.ClientTickEvent.Pre())
    check(u"按父类可匹配到子类事件", parent_received == [1], parent_received)

    # ------------------------------------------------------------
    section("事件总线：一个监听器出错不影响其它")
    # ------------------------------------------------------------
    ordered = []

    def boom(e):
        ordered.append(u"boom")
        raise RuntimeError(u"故意出错")

    def after(e):
        ordered.append(u"after")

    error_bus = event.IEventBus(u"err_bus")
    error_bus.subscribe(boom, event.ClientTickEvent.Post)
    error_bus.subscribe(after, event.ClientTickEvent.Post)
    handled = error_bus._dispatch(event.ClientTickEvent.Post())
    check(u"出错的监听器之后仍继续派发",
          ordered == [u"boom", u"after"], ordered)
    check(u"返回值只统计成功的",
          handled == 1, handled)

    # ------------------------------------------------------------
    section("事件基类：可取消语义")
    # ------------------------------------------------------------
    plain = event.Event()
    check(u"基类事件不可取消", plain.isCancelable() is False)
    check(u"基类初始未取消", plain.isCanceled() is False)
    check(u"对不可取消事件调 setCanceled 会报错",
          raises(plain.setCanceled, True))

    cancelable = event.CancelableEvent()
    check(u"可取消事件 isCancelable 为真", cancelable.isCancelable() is True)
    cancelable.setCanceled(True)
    check(u"取消后 isCanceled 为真", cancelable.isCanceled() is True)
    cancelable.cancel()
    check(u"cancel() 生效", cancelable.isCanceled() is True)

    # ------------------------------------------------------------
    section("@SubscribeEvent 签名校验")
    # ------------------------------------------------------------
    @event.SubscribeEvent
    def good_listener(e):
        pass

    check(u"正常签名被标记",
          hasattr(good_listener, "__neoforge_subscribe__"))

    try:
        @event.SubscribeEvent
        def bad_listener():
            pass
        check(u"零参数监听器应报错", False)
    except Exception as error:
        check(u"零参数监听器当场报错",
              isinstance(error, registries.IllegalArgumentException)
              or u"参数" in u"{}".format(error),
              type(error).__name__)

    # 2 个参数是**合法**的：Python 实例方法就是 (self, event)。
    # 校验规则不能一刀切要求 1 个，否则所有正常写法都被误判 —— 这条钉住它。
    @event.SubscribeEvent
    def instance_style(self, e):
        pass

    check(u"2 参数（实例方法 self+event）被接受",
          hasattr(instance_style, "__neoforge_subscribe__"))

    # 3 个参数才是真写错
    try:
        @event.SubscribeEvent
        def bad_listener3(a, b, c):
            pass
        check(u"三参数监听器应报错", False)
    except Exception:
        check(u"三参数监听器当场报错", True)

    # ------------------------------------------------------------
    section("@EventBusSubscriber 装配与 Dist 过滤")
    # ------------------------------------------------------------
    event.EventBusSubscriber.clear_pending()
    calls = []

    @event.EventBusSubscriber(modid=u"test_mod", value=[event.Dist.CLIENT])
    class ClientHandler(object):
        @event.SubscribeEvent
        def onClientTick(e):
            calls.append(u"client")

        @event.SubscribeEvent
        def onRender(e):
            calls.append(u"render")

    @event.EventBusSubscriber(modid=u"test_mod", value=[event.Dist.SERVER])
    class ServerHandler(object):
        @event.SubscribeEvent
        def onServerTick(e):
            calls.append(u"server")

    @event.EventBusSubscriber(modid=u"test_mod")
    class BothHandler(object):
        @event.SubscribeEvent
        def onAnything(e):
            calls.append(u"both")

    check(u"待装配清单记录了 3 个类",
          len(event.EventBusSubscriber.pending()) == 3,
          len(event.EventBusSubscriber.pending()))

    client_bus = event.IEventBus(u"client_bus")
    registered, skipped = event.EventBusSubscriber.register_all(
        client_bus, current_side=event.Dist.CLIENT)
    check(u"客户端环境下装配 2 个客户端监听器 + 1 个不限端的",
          registered == 3, registered)
    check(u"服务端专属的被跳过", skipped == 1, skipped)

    client_bus.post(event.ClientTickEvent.Post())
    check(u"客户端监听器被调用", u"client" in calls, calls)
    client_bus.post(event.RenderFrameEvent.Pre())
    check(u"第二个客户端监听器被调用", u"render" in calls, calls)

    # 服务端环境：客户端专属不应装配
    calls[:] = []
    event.EventBusSubscriber.clear_pending()

    @event.EventBusSubscriber(modid=u"test_mod", value=[event.Dist.CLIENT])
    class OnlyClient(object):
        @event.SubscribeEvent
        def onTick(e):
            calls.append(u"client")

    server_bus = event.IEventBus(u"server_bus")
    registered2, skipped2 = event.EventBusSubscriber.register_all(
        server_bus, current_side=event.Dist.SERVER)
    check(u"服务端环境下客户端处理器被跳过", registered2 == 0 and skipped2 == 1,
          (registered2, skipped2))
    server_bus.post(event.ClientTickEvent.Post())
    check(u"被跳过的处理器确实没跑", calls == [], calls)

    # ------------------------------------------------------------
    section("Dist / FMLEnvironment / OnlyIn")
    # ------------------------------------------------------------
    check(u"Dist.CLIENT 与 SERVER 不等",
          event.Dist.CLIENT != event.Dist.SERVER)
    check(u"Dist 按身份比较",
          (event.Dist.CLIENT == event.Dist.CLIENT) is True)
    check(u"Dist.name()", event.Dist.CLIENT.name() == u"CLIENT")
    check(u"FMLEnvironment 默认 CLIENT",
          event.FMLEnvironment.dist is event.Dist.CLIENT)
    event.FMLEnvironment.setDist(event.Dist.SERVER)
    check(u"可切换环境", event.FMLEnvironment.getDist() is event.Dist.SERVER)
    event.FMLEnvironment.setDist(event.Dist.CLIENT)

    check(u"空端集合视为不限制",
          event.is_side_allowed([], event.Dist.CLIENT) is True)
    check(u"端匹配为真",
          event.is_side_allowed([event.Dist.CLIENT], event.Dist.CLIENT) is True)
    check(u"端不匹配为假",
          event.is_side_allowed([event.Dist.SERVER], event.Dist.CLIENT) is False)

    @event.OnlyIn(event.Dist.CLIENT)
    class ClientOnly(object):
        pass

    check(u"OnlyIn 记下了允许的端",
          getattr(ClientOnly, "__neoforge_only_in__", None) is event.Dist.CLIENT)

    # ------------------------------------------------------------
    section("端到端：mini 模组按真实写法启动")
    # ------------------------------------------------------------
    event.EventBusSubscriber.clear_pending()
    registries.reset_registries()

    class MiniBlock(Block):
        def __init__(self):
            Block.__init__(self)
            self.kind = u"block"

    class MiniItem(object):
        def __init__(self):
            self.kind = u"item"

    # 对应 Java 的静态字段
    MINI_BLOCKS = registries.DeferredRegister.createBlocks(u"mini_mod")
    MINI_ITEMS = registries.DeferredRegister.create(
        registries.BUILT_IN_REGISTRIES.ITEM, u"mini_mod")

    # 对应 Java 的注册项本体
    crafting_block = MINI_BLOCKS.register(u"crafting_manaita", MiniBlock)
    crafting_item = MINI_ITEMS.register(u"crafting_manaita", MiniItem)

    # 对应 @EventBusSubscriber 的处理器类
    tick_log = []

    @event.EventBusSubscriber(modid=u"mini_mod", value=[event.Dist.CLIENT])
    class MiniEventHandler(object):
        @event.SubscribeEvent
        def clientTick(e):
            tick_log.append(u"tick")

    # 对应 @Mod 构造函数：IEventBus + ModContainer
    mod_bus = event.IEventBus(u"mini_mod")
    MINI_BLOCKS.register_event_bus(mod_bus)
    MINI_ITEMS.register_event_bus(mod_bus)

    check(u"两个注册器已挂上总线", len(mod_bus.getRegistries()) == 2,
          len(mod_bus.getRegistries()))

    # 装配事件处理器
    count, _skipped = event.EventBusSubscriber.register_all(
        mod_bus, current_side=event.Dist.CLIENT)
    check(u"事件处理器装配成功", count == 1, count)

    # 注册事件触发：真正建对象并写表
    def lookup(registry_name):
        if registry_name == u"minecraft:block":
            return registries.BUILT_IN_REGISTRIES.BLOCK
        if registry_name == u"minecraft:item":
            return registries.BUILT_IN_REGISTRIES.ITEM
        return None

    results = mod_bus.freeze_registries(lookup)
    check(u"两个注册器都被执行", len(results) == 2, len(results))
    check(u"方块进了 block 表",
          registries.BUILT_IN_REGISTRIES.BLOCK.get(
              u"mini_mod:crafting_manaita") is not None)
    check(u"物品进了 item 表",
          registries.BUILT_IN_REGISTRIES.ITEM.get(
              u"mini_mod:crafting_manaita") is not None)

    # 注册项能当对象用
    check(u"注册项可当对象用（读属性）",
          crafting_block.kind == u"block", crafting_block.kind)
    check(u"另一个注册项也是", crafting_item.kind == u"item", crafting_item.kind)

    # 事件派发
    mod_bus.post(event.ClientTickEvent.Post())
    check(u"模组的事件处理器被调用", tick_log == [u"tick"], tick_log)

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in (
        "net.neoforged.neoforge.registries.DeferredRegister",
        "net.neoforged.neoforge.registries.DeferredHolder",
        "net.minecraft.resources.ResourceLocation",
        "net.minecraft.core.registries.BuiltInRegistries",
    ):
        check(u"registries 映射 {}".format(java_name),
              java_name in registries.JAVA_MAP)

    for java_name in (
        "net.neoforged.bus.api.IEventBus",
        "net.neoforged.bus.api.SubscribeEvent",
        "net.neoforged.fml.common.EventBusSubscriber",
        "net.neoforged.api.distmarker.Dist",
        "net.neoforged.api.distmarker.OnlyIn",
        "net.neoforged.fml.loading.FMLEnvironment",
        # 事件层拆包后，JAVA_MAP 是各子模块合并出来的
        "net.neoforged.neoforge.event.entity.living.LivingDropsEvent",
        "net.neoforged.neoforge.event.entity.player.ItemTooltipEvent",
        "net.neoforged.neoforge.event.tick.PlayerTickEvent",
        "net.neoforged.neoforge.event.level.BlockEvent",
        "net.neoforged.neoforge.event.village.VillagerTradesEvent",
    ):
        check(u"event 映射 {}".format(java_name), java_name in event.JAVA_MAP)

finally:
    event.EventBusSubscriber.clear_pending()

sys.exit(summary())
