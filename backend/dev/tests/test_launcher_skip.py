# -*- coding: utf-8 -*-
"""
δ 层自测：launcher_skip/（启动层跳过）

真实依据（逐字来自反编译源码）：
    @Mod(value="manaita_plus_legacy")
    public class ManaitaPlusLegacy {
        public ManaitaPlusLegacy(IEventBus modEventBus, ModContainer modContainer) {
            ManaitaPlusLegacyAttributeCore.init();   // 核心初始化
            ...
            BLOCKS.register(modEventBus);            // 注册（不能跳！）
            modContainer.registerConfig(ModConfig.Type.COMMON, SPEC);
        }
    }

    @SubscribeEvent
    public static void onClientSetup(FMLClientSetupEvent event) {
        event.enqueueWork(() -> { ... });            // 启动阶段才有意义
    }

    真实引用：FMLClientSetupEvent 4、enqueueWork 12、
             RegisterShadersEvent 7、RegisterKeyMappingsEvent 3、
             RegisterMenuScreensEvent 3、RegisterClientExtensionsEvent 3

验证点：
  1. @Mod 的三种装饰器写法（@Mod / @Mod(value=) / @Mod()）
  2. 跳过规则：加载器生命周期 / 客户端，必须跳过
  3. **注册与配置绝不能跳**（最严重的错误模式）
  4. MUST_RUN 白名单能救下长得像客户端事件的网络注册事件
  5. enqueueWork 从「排队」改为「直接执行」
  6. LaunchSequence 跑完整启动，且审计记录完整
  7. 构造失败必须向上抛（不能变成「加载成功但功能全无」）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
rules = pkg.load("launcher_skip.rules")
seq = pkg.load("launcher_skip.sequence")
event = pkg.load("neoforge.event")
registries = pkg.load("neoforge.registries")
config = pkg.load("neoforge.config")


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("@Mod 装饰器：三种写法")
    # ------------------------------------------------------------
    # 这里踩过两次同类的坑（SubscribeEvent），所以三种写法都要钉住。
    @seq.Mod
    class Plain(object):
        pass

    check(u"@Mod 不带括号被识别为入口类",
          seq.is_mod_class(Plain) is True)
    check(u"不带括号时类本身没有被替换",
          isinstance(Plain, type), type(Plain).__name__)

    @seq.Mod(value="a_mod")
    class WithValue(object):
        pass

    check(u"@Mod(value=) 记录 modid",
          seq.get_modid(WithValue) == u"a_mod", seq.get_modid(WithValue))
    check(u"类仍然是类", isinstance(WithValue, type))

    @seq.Mod()
    class WithEmpty(object):
        pass

    check(u"@Mod() 也能工作", seq.is_mod_class(WithEmpty) is True)
    check(u"@Mod() 没有 modid", seq.get_modid(WithEmpty) is None)

    class NotMod(object):
        pass

    check(u"普通类不是入口类", seq.is_mod_class(NotMod) is False)
    check(u"普通类没有 modid", seq.get_modid(NotMod) is None)

    # ------------------------------------------------------------
    section("跳过规则：加载器（客户端专属的跳过）")
    # ------------------------------------------------------------
    for java_name in (
        "net.neoforged.fml.event.lifecycle.FMLClientSetupEvent",
        "net.neoforged.fml.event.lifecycle.FMLLoadCompleteEvent",
        "net.neoforged.fml.event.lifecycle.InterModEnqueueEvent",
        "net.neoforged.fml.event.lifecycle.InterModProcessEvent",
    ):
        decision = rules.decide(java_name)
        short = java_name.split(".")[-1]
        check(u"跳过 {}".format(short), decision.isSkip(), decision.toString())
        check(u"  {} 有具体理由".format(short),
              len(decision.reason) > 5, decision.reason)

    # ------------------------------------------------------------
    section("双端通用的初始化事件不能跳")
    # ------------------------------------------------------------
    # 这里是我改过一次的设计错误：最初把 FML*SetupEvent 整类
    # 当「加载器生命周期」跳过，等于悄悄丢掉了模组的通用初始化。
    # FMLCommonSetupEvent 是**双端都跑**的，里面的副作用在基岩版同样需要。
    for java_name in (
        "net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent",
        "net.neoforged.fml.event.lifecycle.FMLDedicatedServerSetupEvent",
    ):
        decision = rules.decide(java_name)
        short = java_name.split(".")[-1]
        check(u"执行 {}".format(short), decision.isRun(), decision.toString())
        check(u"  {} 的类别是 common-setup".format(short),
              decision.category == u"common-setup", decision.category)

    # 对照：客户端专属 vs 双端通用，判定必须不同
    client_setup = rules.decide(
        "net.neoforged.fml.event.lifecycle.FMLClientSetupEvent")
    common_setup = rules.decide(
        "net.neoforged.fml.event.lifecycle.FMLCommonSetupEvent")
    check(u"客户端初始化跳过、通用初始化执行",
          client_setup.isSkip() and common_setup.isRun(),
          (client_setup.action, common_setup.action))

    # ------------------------------------------------------------
    section("enqueueWork 改为直接执行（不是跳过）")
    # ------------------------------------------------------------
    # enqueueWork 本身不是客户端行为，只是线程交接 ——
    # 能执行就不要跳过，跳过是不可逆的信息丢失。
    decision = rules.decide(
        "net.neoforged.fml.event.lifecycle.ParallelDispatchEvent",
        "enqueueWork")
    check(u"enqueueWork 判定为 defer", decision.isDefer(), decision.toString())
    check(u"defer 的原因说明是线程交接",
          u"主线程" in decision.reason, decision.reason)
    check(u"defer 类别是 thread-handoff",
          decision.category == u"thread-handoff", decision.category)

    # 同一个类的其他方法仍然按类别走（ParallelDispatchEvent 是父类，
    # 自己没有类别规则，默认执行）
    check(u"ParallelDispatchEvent 本身默认执行",
          rules.decide(
              "net.neoforged.fml.event.lifecycle.ParallelDispatchEvent"
          ).isRun())

    check(u"注册表方法级规则是执行",
          rules.decide(
              "net.neoforged.neoforge.registries.DeferredRegister",
              "register").isRun())
    check(u"配置方法级规则是执行",
          rules.decide("net.neoforged.fml.ModContainer",
                       "registerConfig").isRun())

    # ------------------------------------------------------------
    section("跳过规则：客户端")
    # ------------------------------------------------------------
    client_cases = [
        ("net.neoforged.neoforge.client.event.RegisterShadersEvent",
         u"client-render"),
        ("net.neoforged.neoforge.client.event.RegisterKeyMappingsEvent",
         u"client-input"),
        ("net.neoforged.neoforge.client.event.RegisterMenuScreensEvent",
         u"client-screen"),
        ("net.neoforged.neoforge.client.extensions.common.RegisterClientExtensionsEvent",
         u"client-extension"),
        ("net.minecraft.client.Minecraft", u"client-render"),
        ("net.minecraft.client.gui.screens.inventory.AbstractContainerScreen",
         u"client-screen"),
    ]
    for java_name, expected_category in client_cases:
        decision = rules.decide(java_name)
        check(u"跳过 {}（类别 {}）".format(java_name.split(".")[-1],
                                          expected_category),
              decision.isSkip() and decision.category == expected_category,
              u"{} / {}".format(decision.action, decision.category))

    # ------------------------------------------------------------
    section("注册与配置绝不能跳（最严重的错误模式）")
    # ------------------------------------------------------------
    # 跳过注册会让所有方块物品变成空气，而且**不报错** ——
    # 玩家只看到「模组加载了但什么都没出现」，极难排查。
    must_run = [
        "net.neoforged.neoforge.registries.RegisterEvent",
        "net.neoforged.neoforge.registries.NewRegistryEvent",
        "net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent",
        "net.neoforged.fml.event.config.ModConfigEvent",
        "net.neoforged.fml.event.config.ModConfigEvent$Loading",
        "net.neoforged.fml.event.config.ModConfigEvent$Reloading",
    ]
    for java_name in must_run:
        decision = rules.decide(java_name)
        check(u"必须执行 {}".format(java_name.split(".")[-1]),
              decision.isRun(), decision.toString())

    # 关键对照：这两个名字几乎一样，但一个必须跑、一个要跳。
    # 靠前缀匹配会一起跳掉，所以必须先判白名单。
    payload = rules.decide(
        "net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent")
    client_ext = rules.decide(
        "net.neoforged.neoforge.client.extensions.common."
        "RegisterClientExtensionsEvent")
    check(u"网络注册事件必须执行", payload.isRun())
    check(u"客户端扩展事件要跳过", client_ext.isSkip())
    check(u"两者判定确实不同", payload.action != client_ext.action,
          (payload.action, client_ext.action))

    check(u"注册表方法级规则是执行",
          rules.decide(
              "net.neoforged.neoforge.registries.DeferredRegister",
              "register").isRun())
    check(u"配置方法级规则是执行",
          rules.decide("net.neoforged.fml.ModContainer",
                       "registerConfig").isRun())

    # ------------------------------------------------------------
    section("未知项默认执行")
    # ------------------------------------------------------------
    # 默认执行是刻意的：漏跳只是多做无用功，错跳会让功能静默消失。
    unknown = rules.decide("com.example.SomethingUnknown")
    check(u"未知类默认执行", unknown.isRun(), unknown.toString())
    check(u"未知的原因说明是默认值",
          u"默认执行" in unknown.reason, unknown.reason)
    check(u"未分类的 category 是 None", unknown.category is None)
    check(u"classify 对未知返回 None",
          rules.classify("com.example.Nope") is None)

    # ------------------------------------------------------------
    section("enqueueWork：排队改为直接执行")
    # ------------------------------------------------------------
    setup_event = seq.FMLClientSetupEvent()
    ran = []
    setup_event.enqueueWork(lambda: ran.append(1))
    check(u"enqueueWork 不立即执行", ran == [], ran)
    setup_event.drainWork()
    check(u"记录了执行次数", len(setup_event.executed) == 1)
    check(u"记录了延迟调用次数", setup_event.enqueue_calls == 1)
    check(u"enqueueWork(None) 报错", raises(setup_event.enqueueWork, None))
    check(u"isComplete 恒为真（直接执行模式下任务不会积压）",
          setup_event.isComplete() is True)

    check(u"FMLCommonSetupEvent 也是直接执行",
          isinstance(seq.FMLCommonSetupEvent(), seq.ParallelDispatchEvent))
    check(u"FMLLoadCompleteEvent 存在",
          isinstance(seq.FMLLoadCompleteEvent(), seq.ParallelDispatchEvent))
    check(u"FML 事件类来自 neoforge 层（不是 δ 层另起一套）",
          seq.FMLClientSetupEvent.__module__ == u"neoforge.event.fml.lifecycle",
          seq.FMLClientSetupEvent.__module__)
    check(u"与 neoforge.event 导出的是同一个类",
          seq.FMLClientSetupEvent is event.FMLClientSetupEvent)

    # ------------------------------------------------------------
    section("LaunchRecord：审计凭据")
    # ------------------------------------------------------------
    record = seq.LaunchRecord(u"test_mod")
    check(u"初始无记录", len(record.ran) == 0 and len(record.skipped) == 0)
    check(u"初始无错误", record.hasErrors() is False)

    record.note_run(u"构造入口类", u"TestMod")
    record.note_skip(u"SomeClientThing", u"客户端渲染", u"client-render")
    record.note_skip(u"AnotherClientThing", u"客户端界面", u"client-screen")
    record.note_skip(u"ThirdClientThing", u"客户端渲染", u"client-render")
    record.note_defer(u"enqueueWork", u"已在主线程")

    check(u"记录执行项", len(record.ran) == 1)
    check(u"记录跳过项", len(record.skipped) == 3)

    grouped = record.skipReasons()
    check(u"跳过项按类别汇总", len(grouped) == 2, sorted(grouped.keys()))
    check(u"client-render 有 2 项", len(grouped[u"client-render"]) == 2,
          grouped[u"client-render"])

    lines = record.summary_lines()
    joined = u"\n".join(lines)
    check(u"摘要含执行步数", u"执行 1 步" in joined, joined[:80])
    check(u"摘要含跳过步数", u"跳过 3 步" in joined, joined[:80])
    check(u"摘要含类别", u"client-render" in joined)
    check(u"摘要含改为直接执行", u"改为直接执行" in joined)

    # ------------------------------------------------------------
    section("LaunchSequence：完整启动")
    # ------------------------------------------------------------
    # 照真实模组的写法搭一个入口类
    bus = event.IEventBus(u"manaita_plus_legacy")
    container = config.ModContainer(u"manaita_plus_legacy")

    startup_log = []

    BLOCKS = registries.DeferredRegister.createBlocks(u"manaita_plus_legacy")
    ITEMS = registries.DeferredRegister.create(
        registries.BUILT_IN_REGISTRIES.ITEM, u"manaita_plus_legacy")

    @seq.Mod(value="manaita_plus_legacy")
    class ManaitaPlusLegacy(object):
        def __init__(self, mod_event_bus, mod_container):
            # 对应 Java 里那一串 *_Core.init()
            startup_log.append(u"init")
            # 对应 BLOCKS.register(modEventBus)
            BLOCKS.register_event_bus(mod_event_bus)
            ITEMS.register_event_bus(mod_event_bus)
            startup_log.append(u"register")
            # 对应 modContainer.registerConfig(...)
            config_builder = config.ModConfigSpecBuilder()
            config_builder.define("enabled", True)
            mod_container.registerConfig(config.ModConfig.Type.COMMON,
                                         config_builder.build())
            startup_log.append(u"config")

    sequence = seq.LaunchSequence(bus, container)
    instance, launch_record = sequence.run(ManaitaPlusLegacy)

    check(u"入口类被构造", isinstance(instance, ManaitaPlusLegacy))
    check(u"构造过程完整跑完（init→register→config）",
          startup_log == [u"init", u"register", u"config"], startup_log)
    check(u"注册器挂上了总线（注册没被跳过）",
          len(bus.getRegistries()) == 2, len(bus.getRegistries()))
    check(u"配置已注册（配置没被跳过）",
          container.getConfig(config.ModConfig.Type.COMMON) is not None)
    check(u"启动了启动期事件", launch_record is not None)
    check(u"启动没有出错", launch_record.hasErrors() is False,
          launch_record.errors)

    # 审计记录
    check(u"记录了构造入口类",
          any(u"构造入口类" in name for name, _ in launch_record.ran),
          launch_record.ran)

    # ------------------------------------------------------------
    section("LaunchSequence：客户端处理器被审查跳过")
    # ------------------------------------------------------------
    bus2 = event.IEventBus(u"test_mod")
    container2 = config.ModContainer(u"test_mod")

    @seq.Mod(value="test_mod")
    class TestMod(object):
        def __init__(self, mod_event_bus, mod_container):
            pass

    # 审查依据是 @SubscribeEvent 装饰时记下的事件参数名
    # （真实代码的参数名就是事件类名的小写）。
    event_mod = pkg.load("neoforge.event")

    class ClientHandler(object):
        @event_mod.SubscribeEvent
        def onClientSetup(fmlClientSetupEvent):
            pass

        @event_mod.SubscribeEvent
        def registerShaders(registerShadersEvent):
            pass

        @event_mod.SubscribeEvent
        def onServerTick(clientTickEvent):
            # 参数名带 client，属于客户端，应被跳过
            pass

        @event_mod.SubscribeEvent
        def onConfig(modConfigEvent):
            # 配置事件必须执行，绝不跳过
            pass

        def not_a_listener(self, event):
            pass

    sequence2 = seq.LaunchSequence(bus2, container2)
    sequence2.construct_mod(TestMod)
    skipped_count = sequence2.audit_handlers([ClientHandler])

    check(u"审查出 3 个客户端处理器", skipped_count == 3, skipped_count)
    check(u"跳过项进了记录", len(sequence2.record.skipped) == 3,
          sequence2.record.skipped)
    check(u"FML 客户端初始化被识别为客户端专属加载器事件",
          any(item[2] == u"loader-client-lifecycle"
              for item in sequence2.record.skipped),
          sequence2.record.skipped)
    check(u"渲染相关被识别为客户端渲染",
          any(item[2] == u"client-render"
              for item in sequence2.record.skipped),
          sequence2.record.skipped)
    check(u"没有 @SubscribeEvent 的方法不被算进去",
          not any(u"not_a_listener" in item[0]
                  for item in sequence2.record.skipped),
          sequence2.record.skipped)
    check(u"配置处理器没有被跳过（配置绝不能跳）",
          not any(u"onConfig" in item[0]
                  for item in sequence2.record.skipped),
          sequence2.record.skipped)

    # 关键：construct_mod 不会冲掉之前记下的跳过项
    sequence3 = seq.LaunchSequence(bus2, container2)
    sequence3.audit_handlers([ClientHandler])
    before = len(sequence3.record.skipped)
    sequence3.construct_mod(TestMod)
    check(u"构造入口类不会冲掉已有的跳过记录",
          len(sequence3.record.skipped) == before,
          (before, len(sequence3.record.skipped)))

    # ------------------------------------------------------------
    section("构造失败必须向上抛")
    # ------------------------------------------------------------
    # 注册失败若被吞掉，会得到「加载成功但功能全无」这种最难查的状态。
    @seq.Mod(value="broken_mod")
    class BrokenMod(object):
        def __init__(self, mod_event_bus, mod_container):
            raise RuntimeError(u"注册时出错")

    broken_sequence = seq.LaunchSequence(event.IEventBus(u"broken"),
                                         config.ModContainer(u"broken_mod"))
    check(u"构造异常会向上抛",
          raises(broken_sequence.construct_mod, BrokenMod))
    check(u"异常同时被记进 record",
          broken_sequence.record.hasErrors() is True,
          broken_sequence.record.errors)
    check(u"错误里保留了原始异常",
          isinstance(broken_sequence.record.errors[0][1], RuntimeError))

    check(u"construct_mod(None) 报错",
          raises(broken_sequence.construct_mod, None))
    check(u"LaunchSequence 需要事件总线", raises(seq.LaunchSequence, None,
                                                config.ModContainer()))

    # ------------------------------------------------------------
    section("派发启动期事件")
    # ------------------------------------------------------------
    setup_bus = event.IEventBus(u"setup_bus")
    setup_container = config.ModContainer(u"setup_bus")
    setup_calls = []

    def on_setup(e):
        setup_calls.append(u"setup")

    setup_bus.subscribe(on_setup, seq.FMLCommonSetupEvent)

    setup_seq = seq.LaunchSequence(setup_bus, setup_container)
    handled = setup_seq.dispatch_setup_events(seq.FMLCommonSetupEvent())
    check(u"启动事件被派发", handled == 1, handled)
    check(u"处理器被调用", setup_calls == [u"setup"], setup_calls)
    check(u"派发记进了 record",
          any(u"派发" in name for name, _ in setup_seq.record.ran),
          setup_seq.record.ran)

    # enqueueWork 在派发时被记为「改为直接执行」。
    # 注意要用**不被跳过**的事件来验：FMLClientSetupEvent 整类会被跳过，
    # 拿它测 enqueueWork 是自相矛盾的（事件都跳过了，里面的任务当然不跑）。
    work_bus = event.IEventBus(u"work_bus")
    work_seq = seq.LaunchSequence(work_bus, config.ModContainer(u"work_bus"))
    work_done = []

    def on_common_setup(fmlCommonSetupEvent):
        fmlCommonSetupEvent.enqueueWork(lambda: work_done.append(1))

    work_bus.subscribe(on_common_setup, seq.FMLCommonSetupEvent)
    work_seq.dispatch_setup_events(seq.FMLCommonSetupEvent())
    check(u"enqueueWork 里的任务真的跑了（事件未被跳过）",
          work_done == [1], work_done)
    check(u"记录了「改为直接执行」",
          len(work_seq.record.deferred) == 1, work_seq.record.deferred)

    # 对照：被跳过的事件，其处理器确实不会执行 —— 这是跳过的意义所在
    skip_bus = event.IEventBus(u"skip_bus")
    skip_seq = seq.LaunchSequence(skip_bus, config.ModContainer(u"skip_bus"))
    skip_ran = []

    def on_client_setup(fmlClientSetupEvent):
        skip_ran.append(1)

    skip_bus.subscribe(on_client_setup, seq.FMLClientSetupEvent)
    handled_skip = skip_seq.dispatch_setup_events(seq.FMLClientSetupEvent())
    check(u"被客户端专属事件不派发（返回 0）", handled_skip == 0, handled_skip)
    check(u"其处理器确实没跑", skip_ran == [], skip_ran)
    check(u"跳过项进了记录，可审计",
          len(skip_seq.record.skipped) == 1, skip_seq.record.skipped)

    # ------------------------------------------------------------
    section("报告生成")
    # ------------------------------------------------------------
    names = [
        "net.neoforged.fml.event.lifecycle.FMLClientSetupEvent",
        "net.neoforged.neoforge.client.event.RegisterShadersEvent",
        "net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent",
        "com.example.Unknown",
    ]
    stats = rules.summarize(names)
    check(u"汇总出 2 项跳过", len(stats[u"skip"]) == 2, len(stats[u"skip"]))
    check(u"汇总出 2 项执行", len(stats[u"run"]) == 2, len(stats[u"run"]))

    report = rules.report_lines(names)
    joined_report = u"\n".join(report)
    check(u"报告含跳过", u"[跳过]" in joined_report)
    check(u"报告含执行", u"[执行]" in joined_report)
    check(u"报告含具体理由",
          u"客户端专属的加载器阶段" in joined_report, joined_report[:300])

finally:
    event.EventBusSubscriber.clear_pending()

sys.exit(summary())
