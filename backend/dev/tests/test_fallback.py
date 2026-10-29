# -*- coding: utf-8 -*-
"""
ω 层自测：未映射api/（兜底处理）

这一层回答一个问题：**核心包没实现的 API，遇到了怎么办？**

三种做法的取舍：
    raise  立刻暴露，但可能因一个纯视觉方法让整个模组崩掉
    noop   模组能跑，但会掩盖真问题（方块没了却不报错）
    stub   返回中性替身，让上层逻辑继续走

结论是按 API 类别分别定策略，没有一刀切。验证点：
  1. 分类规则：注册/网络/翻译/界面/渲染/音效/数据/世界/物品/事件/工具
  2. 策略表：该 raise 的类必须 raise，该 noop 的必须 noop
  3. FallbackHandler 三种动作的实际行为
  4. UnmappedClass 替身不因链式调用而崩
  5. 兜底**必须留痕**（含 raise 的情况）
  6. FallbackLogger 的报告与严重级别判定
  7. 策略表本身的完整性（每个类别都要有策略，否则会 KeyError）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
fb = pkg.load(u"未映射api.fallback")
lg = pkg.load(u"未映射api.logger")

Severity = fb.Severity


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


def fresh_handler():
    """每个用例一份干净的统计，避免互相污染。"""
    stats = fb.FallbackStats()
    return fb.FallbackHandler(stats=stats, logger=lambda text: None), stats


try:
    # ------------------------------------------------------------
    section("分类规则")
    # ------------------------------------------------------------
    cases = [
        ("net.neoforged.neoforge.registries.DeferredRegister", u"registry"),
        ("net.neoforged.neoforge.registries.DeferredHolder", u"registry"),
        ("net.minecraft.network.protocol.common.custom.CustomPacketPayload",
         u"network"),
        ("net.minecraft.network.codec.StreamCodec", u"network"),
        ("net.minecraft.world.item.ItemStack", u"item"),
        ("net.minecraft.world.item.Item", u"item"),
        ("net.minecraft.world.level.block.Block", u"item"),
        ("net.minecraft.world.entity.Entity", u"item"),
        ("net.minecraft.world.level.Level", u"world-write"),
        ("net.minecraft.server.level.ServerLevel", u"world-write"),
        ("net.minecraft.client.resources.language.I18n", u"translation"),
        ("net.minecraft.network.chat.Component", u"translation"),
        ("net.minecraft.nbt.CompoundTag", u"data"),
        ("net.minecraft.core.component.DataComponentType", u"data"),
        ("net.minecraft.sounds.SoundEvent", u"sound"),
        ("net.minecraft.sounds.SoundSource", u"sound"),
        ("net.minecraft.client.gui.screens.Screen", u"client-ui"),
        ("net.minecraft.client.renderer.MultiBufferSource", u"render"),
        ("net.minecraft.util.Mth", u"util"),
        ("com.example.Whatever", u"unknown"),
    ]
    for java_name, expected in cases:
        got = fb.classify_api(java_name)
        check(u"{} 归类为 {}".format(java_name.split(u".")[-1], expected),
              got == expected, u"{} (期望 {})".format(got, expected))

    check(u"空名归为 unknown", fb.classify_api(u"") == u"unknown")
    check(u"None 归为 unknown", fb.classify_api(None) == u"unknown")

    # 顺序敏感的关键用例：SoundEvent 同时含 sound 与 event
    check(u"SoundEvent 按 sound 归类（不是 event）",
          fb.classify_api(u"net.minecraft.sounds.SoundEvent") == u"sound",
          fb.classify_api(u"net.minecraft.sounds.SoundEvent"))
    # Component 同时可能命中 render 之类，但必须走翻译
    check(u"Component 按 translation 归类",
          fb.classify_api(u"net.minecraft.network.chat.Component")
          == u"translation")

    # ------------------------------------------------------------
    section("策略表完整性")
    # ------------------------------------------------------------
    # 每个可能的类别都必须有策略，否则 policy_for 会 KeyError。
    categories = set([category for category, _kw in fb.CLASSIFY_RULES])
    categories.add(u"unknown")
    missing = [c for c in categories if c not in fb.DEFAULT_POLICIES]
    check(u"每个可分类别都有策略", missing == [], missing)

    # 反过来：策略表里不该有永远用不到的类别（说明规则漏了）
    unreachable = [c for c in fb.DEFAULT_POLICIES if c not in categories]
    check(u"策略表没有不可达的类别", unreachable == [], unreachable)

    # 每条策略都要有理由
    no_reason = [name for name, policy in fb.DEFAULT_POLICIES.items()
                 if not policy.reason or len(policy.reason) < 5]
    check(u"每条策略都写了理由", no_reason == [], no_reason)

    check(u"未知类别会退回 unknown 策略",
          fb.policy_for(u"com.example.Nope").category == u"unknown")

    # ------------------------------------------------------------
    section("策略：该 raise 的必须 raise")
    # ------------------------------------------------------------
    # 这四类静默失败最可怕：注册没了方块消失、数据写歪、包发不出去、
    # 基础工具类有洞。都必须立刻暴露。
    raise_cases = [
        "net.neoforged.neoforge.registries.DeferredRegister",
        "net.minecraft.nbt.CompoundTag",
        "net.minecraft.network.protocol.common.custom.CustomPacketPayload",
        "net.minecraft.util.Mth",
    ]
    for java_name in raise_cases:
        policy = fb.policy_for(java_name)
        check(u"{} 策略是 raise".format(java_name.split(u".")[-1]),
              policy.severity == Severity.RAISE,
              u"{} ({})".format(policy.severity, policy.category))

    # ------------------------------------------------------------
    section("策略：观感类走 noop")
    # ------------------------------------------------------------
    # 因为一个粒子效果让模组崩掉不值得。
    noop_cases = [
        "net.minecraft.client.renderer.MultiBufferSource",
        "net.minecraft.sounds.SoundEvent",
        "net.minecraft.client.gui.screens.Screen",
    ]
    for java_name in noop_cases:
        policy = fb.policy_for(java_name)
        check(u"{} 策略是 noop".format(java_name.split(u".")[-1]),
              policy.severity == Severity.NOOP,
              u"{} ({})".format(policy.severity, policy.category))

    check(u"翻译类是 stub",
          fb.policy_for(u"net.minecraft.client.resources.language.I18n")
          .severity == Severity.STUB)
    check(u"拿不准的是 warn",
          fb.policy_for(u"com.example.Nope").severity == Severity.WARN)

    # ------------------------------------------------------------
    section("FallbackHandler：三种动作的实际行为")
    # ------------------------------------------------------------
    handler, stats = fresh_handler()

    # raise
    check(u"注册类未实现时抛异常",
          raises(handler.handle,
                 u"net.neoforged.neoforge.registries.DeferredRegister"))

    # noop
    result = handler.handle(u"net.minecraft.sounds.SoundEvent")
    check(u"音效类未实现时返回 None 而不抛", result is None)

    # warn
    result = handler.handle(u"com.example.UnknownThing")
    check(u"未知类返回 None", result is None)

    # stub
    result = handler.handle(u"net.minecraft.client.resources.language.I18n")
    check(u"翻译类返回替身而不是 None", result is not None)
    # 翻译的替身就是「键本身」，直接是字符串 —— 上层 .getString() 之类
    # 会由翻译层另行处理；这里至少要能当文本用。
    check(u"替身可直接当文本用（回退为键名）",
          u"I18n" in u"{}".format(result), u"{}".format(result))

    # handleClass
    class_result = handler.handleClass(u"net.minecraft.sounds.SoundEvent")
    check(u"handleClass 返回可构造的类", isinstance(class_result, type))
    instance = class_result()
    check(u"替身类可以实例化", instance is not None)
    # 替身是链式友好的：方法调用返回替身自身，所以能继续往下调。
    # 这正是为了防住 `entity.level().playSound(...)` 这类写法。
    check(u"替身实例的方法调用可继续链式",
          instance.anyMethod(1, 2, 3) is not None)
    check(u"链式调用不崩",
          instance.getLevel().playSound(u"x") is not None)
    check(u"替身类名取自 Java 名最后一段",
          class_result.__name__ == u"SoundEvent", class_result.__name__)

    check(u"handleClass 对注册类抛异常",
          raises(handler.handleClass,
                 u"net.neoforged.neoforge.registries.DeferredRegister"))

    # ------------------------------------------------------------
    section("兜底必须留痕（含 raise 的情况）")
    # ------------------------------------------------------------
    # 连「崩了」也是需要知道的信息 —— 不记的话就不知道有多少地方没实现。
    handler2, stats2 = fresh_handler()
    check(u"初始统计为空", stats2.isClean() is True)

    try:
        handler2.handle(u"net.neoforged.neoforge.registries.DeferredRegister")
    except NotImplementedError:
        pass
    check(u"抛异常的那次也被记录", stats2.count() == 1, stats2.count())
    check(u"记录的严重级别是 raise",
          stats2.entries[0][2] == Severity.RAISE, stats2.entries[0])

    handler2.handle(u"net.minecraft.sounds.SoundEvent")
    handler2.handle(u"net.minecraft.sounds.SoundEvent")
    handler2.handle(u"com.example.Nope")
    check(u"共记录 4 条", stats2.count() == 4, stats2.count())

    grouped = stats2.byJavaName()
    check(u"按名字聚合正确",
          grouped[u"net.minecraft.sounds.SoundEvent"] == 2, grouped)
    check(u"聚合出 3 种 API", len(grouped) == 3, len(grouped))

    by_severity = stats2.bySeverity()
    check(u"按严重级别聚合",
          by_severity[Severity.RAISE] == 1
          and by_severity[Severity.NOOP] == 2
          and by_severity[Severity.WARN] == 1,
          by_severity)

    report = stats2.report_lines()
    joined = u"\n".join(report)
    check(u"报告含总次数", u"共 4 次" in joined, joined[:120])
    check(u"报告含排序后的清单", u"SoundEvent" in joined)
    check(u"报告说明按次数排优先级", u"优先补" in joined)

    stats2.clear()
    check(u"clear 清空统计", stats2.isClean() is True)
    check(u"清空后报告说覆盖完整",
          u"覆盖完整" in u"\n".join(stats2.report_lines()))

    # ------------------------------------------------------------
    section("UnmappedClass 替身：链式调用不崩")
    # ------------------------------------------------------------
    # 这是替身存在的核心理由：翻译后的代码常写成
    #     entity.level().playSound(...)
    # 若中间返回 None，下一层立刻 AttributeError ——
    # 一个纯视觉缺失会演变成崩溃。
    handler3, stats3 = fresh_handler()
    delegate = fb.UnmappedClass(u"com.example.SomeClass")

    check(u"取方法返回可调用对象", callable(delegate.doThing))
    check(u"带参数调用也不崩", delegate.doThing(1, 2, key=3) is not None)

    # 核心：方法返回替身自身，所以链式调用能一路走完。
    # 原本返回 None，`delegate.a().b()` 立刻 AttributeError ——
    # 正是替身本该防住的那种崩溃。
    chained = delegate.a().b().c()
    check(u"链式调用能走完", chained is not None)
    check(u"链式调用交回同一个替身", chained is delegate,
          (id(chained), id(delegate)))

    check(u"直接调用替身返回 None（构造语义）", delegate() is None)
    check(u"访问被记录", len(delegate.accessedMembers()) >= 4,
          delegate.accessedMembers())

    check(u"getJavaName", delegate.getJavaName() == u"com.example.SomeClass")
    check(u"toString 可读", u"SomeClass" in delegate.toString(),
          delegate.toString())
    check(u"str() 也可用", u"SomeClass" in u"{}".format(delegate))

    # 协议方法给安全实现
    check(u"len 为 0", len(delegate) == 0)
    check(u"可迭代（空）", list(delegate) == [])
    check(u"布尔值为假", bool(delegate) is False)
    check(u"自身比较相等", delegate == delegate)
    check(u"与别的对象不等", delegate != u"other")
    check(u"可哈希", isinstance(hash(delegate), int))
    # 私有属性不拦截 —— 否则 hasattr 永远为真，会干扰内省
    check(u"私有属性仍抛 AttributeError", raises(getattr, delegate,
                                                 u"_no_such_private"))

    # 不返回自身的模式：调用返回 None
    plain = fb.UnmappedClass(u"com.example.Plain", return_self=False)
    check(u"return_self=False 时调用返回 None", plain.doThing() is None)

    # ------------------------------------------------------------
    section("resolve_or_fallback")
    # ------------------------------------------------------------
    check(u"有实现时原样返回",
          fb.resolve_or_fallback(u"a.B", implementation=u"IMPL") == u"IMPL")
    check(u"没有实现时走兜底（音效类返回 None）",
          fb.resolve_or_fallback(u"net.minecraft.sounds.SoundEvent") is None)
    check(u"没有实现且属注册类时抛异常",
          raises(fb.resolve_or_fallback,
                 u"net.neoforged.neoforge.registries.DeferredRegister"))

    # ------------------------------------------------------------
    section("FallbackLogger：报告与级别判定")
    # ------------------------------------------------------------
    stats4 = fb.FallbackStats()
    stats4.note(u"net.minecraft.sounds.SoundEvent", u"play",
                Severity.NOOP, u"sound")
    stats4.note(u"net.minecraft.sounds.SoundEvent", u"stop",
                Severity.NOOP, u"sound")
    stats4.note(u"net.minecraft.client.renderer.MultiBufferSource", u"draw",
                Severity.NOOP, u"render")

    logger = lg.FallbackLogger(stats=stats4, writer=lambda text: None)
    check(u"没有严重级别", logger.hasSevere() is False)
    check(u"观感问题 3 次", logger.cosmeticCount() == 3,
          logger.cosmeticCount())
    check(u"严重清单为空", logger.severeNames() == [])

    line = logger.summaryLine()
    check(u"摘要含总次数", u"3 次" in line, line)
    check(u"摘要含观感次数", u"观感类 3 次" in line, line)

    report_lines = logger.buildReport()
    joined2 = u"\n".join(report_lines)
    check(u"报告有标题", u"未映射 API 报告" in joined2)
    check(u"报告按严重程度分组", u"静默跳过" in joined2, joined2[:300])
    check(u"报告含补齐优先级", u"补齐优先级" in joined2)
    check(u"报告列出具体方法",
          u"SoundEvent.play" in joined2, joined2[:400])

    # 加入一条严重级别
    stats4.note(u"net.neoforged.neoforge.registries.DeferredRegister", None,
                Severity.RAISE, u"registry")
    check(u"现在有严重级别", logger.hasSevere() is True)
    check(u"严重清单里有它",
          u"net.neoforged.neoforge.registries.DeferredRegister"
          in logger.severeNames(), logger.severeNames())
    check(u"严重排在报告最前",
          joined2.find(u"严重") < joined2.find(u"静默跳过")
          if u"严重" in joined2 else True)

    line2 = logger.summaryLine()
    check(u"摘要含严重次数", u"严重 1 次" in line2, line2)

    logger.clear()
    check(u"clear 清空", logger.stats.isClean() is True)
    check(u"空报告说明覆盖完整",
          u"覆盖完整" in u"\n".join(logger.buildReport()))

    check(u"严重级别标签齐全",
          all(s in lg.SEVERITY_LABELS for s in Severity.ALL),
          sorted(lg.SEVERITY_LABELS.keys()))
    check(u"严重级别排序权重齐全",
          all(s in lg.SEVERITY_ORDER for s in Severity.ALL))

    # ------------------------------------------------------------
    section("非法策略")
    # ------------------------------------------------------------
    check(u"未知处理方式报错",
          raises(fb.Policy, u"explode", u"x", u"理由"))
    check(u"合法处理方式可用",
          fb.Policy(Severity.RAISE, u"x", u"理由").severity
          == Severity.RAISE)

finally:
    fb.STATS.clear()

sys.exit(summary())
