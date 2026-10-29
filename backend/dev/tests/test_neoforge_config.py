# -*- coding: utf-8 -*-
"""
β 层自测：neoforge/config.py（ModConfigSpec）

真实依据（逐字来自反编译源码）：
    private static final ModConfigSpec.Builder BUILDER = new ModConfigSpec.Builder();

    private static final ModConfigSpec.BooleanValue creative_range_destroy =
        BUILDER.comment("...").define("creative_range_destroy", false);

    private static final ModConfigSpec.IntValue experience_drops_doubling =
        BUILDER.comment("ExperienceDropsDoubling")
               .defineInRange("experience_drops_doubling_value", 4, 1, Integer.MAX_VALUE);

    public static final ModConfigSpec SPEC = BUILDER.build();

    static void onLoad(ModConfigEvent.Loading event) {
        if (event.getConfig().getModId().equals("manaita_plus_legacy")
                && event.getConfig().getSpec() == SPEC) {
            item_drops_doubling_value = (Integer) item_drops_doubling.get();
        }
    }

验证点：
  1. Builder 的链式约定（comment 返回自身、define 返回句柄）
  2. define 按默认值类型自动选句柄类型
  3. defineInRange 的范围校验（默认值越界当场报错、设值越界报错）
  4. build() 的幂等性（关系到 `getSpec() == SPEC` 的身份比较）
  5. loadFrom 的加载语义（未给的保持默认、非法的点名报错）
  6. ModContainer.registerConfig 与 ModConfig.Type
  7. 端到端：照真实写法写一个配置类，走完「定义→构建→事件加载→取值」
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
config = pkg.load("neoforge.config")
event = pkg.load("neoforge.event")

ModConfigSpec = config.ModConfigSpec
Builder = config.ModConfigSpecBuilder


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("Builder：链式约定")
    # ------------------------------------------------------------
    builder = Builder(u"test_mod")
    check(u"comment 返回自身（可链式）", builder.comment(u"说明") is builder)
    check(u"translation 返回自身", builder.translation(u"key") is builder)
    check(u"push 返回自身", builder.push(u"section") is builder)
    check(u"pop 返回自身", builder.pop() is builder)
    check(u"define 返回句柄而不是 builder",
          not isinstance(builder.define(u"x", 1), Builder))

    # ------------------------------------------------------------
    section("define：按默认值类型选句柄")
    # ------------------------------------------------------------
    b = Builder()
    boolean_handle = b.define(u"flag", False)
    int_handle = b.define(u"count", 4)
    double_handle = b.define(u"ratio", 1.5)
    string_handle = b.define(u"name", u"hello")

    check(u"bool 默认值得到 BooleanValue",
          isinstance(boolean_handle, config.BooleanValue),
          type(boolean_handle).__name__)
    check(u"int 默认值得到 IntValue",
          isinstance(int_handle, config.IntValue), type(int_handle).__name__)
    check(u"float 默认值得到 DoubleValue",
          isinstance(double_handle, config.DoubleValue),
          type(double_handle).__name__)
    check(u"字符串默认值得到 StringValue",
          isinstance(string_handle, config.StringValue),
          type(string_handle).__name__)

    check(u"未加载时 get() 是默认值", boolean_handle.get() is False)
    check(u"整型默认值", int_handle.get() == 4, int_handle.get())
    check(u"getDefault 与默认值一致", int_handle.getDefault() == 4)
    check(u"getPath 正确", int_handle.getPath() == u"count", int_handle.getPath())

    # ------------------------------------------------------------
    section("comment 作用于紧跟其后的项")
    # ------------------------------------------------------------
    c = Builder()
    c.comment(u"第一项说明")
    with_comment = c.define(u"a", 1)
    without_comment = c.define(u"b", 2)
    check(u"注释挂到了第一项",
          with_comment.getComment() == u"第一项说明",
          with_comment.getComment())
    check(u"注释不会粘到第二项",
          without_comment.getComment() is None, without_comment.getComment())

    c2 = Builder()
    c2.comment(u"第一行", u"第二行")
    multi = c2.define(u"m", 0)
    check(u"多行注释用换行拼接",
          multi.getComment() == u"第一行\n第二行", repr(multi.getComment()))

    # ------------------------------------------------------------
    section("defineInRange：范围校验")
    # ------------------------------------------------------------
    r = Builder()
    ranged = r.defineInRange(u"size", 4, 1, Builder.INT_MAX)
    check(u"范围内默认值可用", ranged.get() == 4)
    check(u"记录了上下限",
          ranged.getMin() == 1 and ranged.getMax() == Builder.INT_MAX,
          (ranged.getMin(), ranged.getMax()))

    check(u"默认值低于下限当场报错",
          raises(r.defineInRange, u"bad_low", 0, 1, 10))
    check(u"默认值高于上限当场报错",
          raises(r.defineInRange, u"bad_high", 99, 1, 10))

    ranged.set(7)
    check(u"设值在范围内生效", ranged.get() == 7, ranged.get())
    check(u"设值低于下限报错", raises(ranged.set, 0))
    check(u"设值高于上限报错", raises(ranged.set, 99999999999))
    check(u"非法设值后原值不变", ranged.get() == 7, ranged.get())
    check(u"设非数字报错", raises(ranged.set, u"abc"))

    check(u"Integer.MAX_VALUE 常量正确",
          Builder.INT_MAX == 2147483647, Builder.INT_MAX)

    # ------------------------------------------------------------
    section("push/pop：子节点路径")
    # ------------------------------------------------------------
    p = Builder()
    p.push(u"general")
    nested = p.define(u"flag", True)
    check(u"push 后路径带前缀", nested.getPath() == u"general.flag",
          nested.getPath())
    p.pop()
    top = p.define(u"flag", False)
    check(u"pop 后回到顶层", top.getPath() == u"flag", top.getPath())
    check(u"不同前缀下同名键不冲突", nested.get() is True and top.get() is False)

    # ------------------------------------------------------------
    section("build：身份稳定性")
    # ------------------------------------------------------------
    s_builder = Builder(u"test_mod")
    s_builder.define(u"a", 1)
    spec1 = s_builder.build()
    spec2 = s_builder.build()
    check(u"重复 build 返回同一 SPEC（身份比较才成立）",
          spec1 is spec2, u"{} vs {}".format(id(spec1), id(spec2)))
    check(u"SPEC 收集了所有项", spec1.size() == 1, spec1.size())
    check(u"SPEC 不是空的", spec1.isEmpty() is False)
    check(u"SPEC 记住 modid", spec1.modid == u"test_mod", spec1.modid)
    check(u"可按路径取句柄", spec1.getValue(u"a") is not None)
    check(u"未定义路径取到 None", spec1.getValue(u"nope") is None)
    check(u"hasValue 正确",
          spec1.hasValue(u"a") is True and spec1.hasValue(u"nope") is False)
    check(u"build 之后不能再定义",
          raises(s_builder.define, u"b", 1))

    dup = Builder()
    dup.define(u"x", 1)
    check(u"同路径重复定义报错", raises(dup.define, u"x", 2))

    # ------------------------------------------------------------
    section("loadFrom：加载语义")
    # ------------------------------------------------------------
    spec = (Builder(u"test_mod")
            .comment(u"标志").define(u"flag", False))
    b2 = Builder(u"test_mod")
    h_flag = b2.comment(u"标志").define(u"flag", False)
    h_count = b2.comment(u"数量").defineInRange(u"count", 4, 1, 100)
    spec = b2.build()

    check(u"初始未标记已加载", spec.isLoaded() is False)
    applied = spec.loadFrom({u"flag": True, u"count": 8})
    check(u"两项都被载入", applied == 2, applied)
    check(u"布尔被载入", h_flag.get() is True)
    check(u"整数被载入", h_count.get() == 8, h_count.get())
    check(u"载入后标记为已加载", spec.isLoaded() is True)

    # 未提供的保持默认
    b3 = Builder()
    kept = b3.define(u"only", 5)
    spec3 = b3.build()
    spec3.loadFrom({})
    check(u"未提供的项保持默认值", kept.get() == 5, kept.get())

    # 非法值要点名报错
    b4 = Builder()
    b4.defineInRange(u"ranged", 5, 1, 10)
    spec4 = b4.build()
    try:
        spec4.loadFrom({u"ranged": 999})
        check(u"非法值应报错", False)
    except Exception as error:
        check(u"非法值报错", True)
        check(u"错误信息点名了出错的键",
              u"ranged" in u"{}".format(error), u"{}".format(error)[:60])

    # 未知键被忽略而不是报错
    b5 = Builder()
    b5.define(u"known", 1)
    spec5 = b5.build()
    applied5 = spec5.loadFrom({u"known": 2, u"legacy_key": u"whatever"})
    check(u"未知键被忽略（不因为多余键起不来）", applied5 == 1, applied5)
    check(u"已知键仍然生效", spec5.getValue(u"known").get() == 2)

    check(u"loadFrom(None) 不报错", spec5.loadFrom(None) == 0)

    # 字符串值的宽松解析
    b6 = Builder()
    h_bool = b6.define(u"flag", False)
    h_int = b6.define(u"num", 0)
    spec6 = b6.build()
    spec6.loadFrom({u"flag": u"true", u"num": u"42"})
    check(u"字符串 'true' 可解析为布尔", h_bool.get() is True)
    check(u"字符串 '42' 可解析为整数", h_int.get() == 42, h_int.get())

    check(u"toDict 导出当前值",
          spec6.toDict() == {u"flag": True, u"num": 42}, spec6.toDict())

    # ------------------------------------------------------------
    section("defineList")
    # ------------------------------------------------------------
    lb = Builder()
    list_handle = lb.defineList(u"items", [u"a", u"b"])
    check(u"defineList 得到 ListValue",
          isinstance(list_handle, config.ListValue))
    check(u"列表默认值", list_handle.get() == [u"a", u"b"], list_handle.get())
    list_handle.set([u"c"])
    check(u"列表可设值", list_handle.get() == [u"c"])
    list_handle.set(u"single")
    check(u"单值被包成列表", list_handle.get() == [u"single"])

    # ------------------------------------------------------------
    section("ModContainer 与 ModConfig.Type")
    # ------------------------------------------------------------
    container = config.ModContainer(u"manaita_plus_legacy")
    check(u"ModContainer 记住 modid",
          container.getModId() == u"manaita_plus_legacy")

    common_builder = Builder(u"manaita_plus_legacy")
    common_builder.define("enabled", True)
    common_spec = common_builder.build()
    client_builder = Builder(u"manaita_plus_legacy")
    client_builder.define("enabled", True)
    client_spec = client_builder.build()
    container.registerConfig(config.ModConfig.Type.COMMON,
                                          common_spec)
    container.registerConfig(config.ModConfig.Type.CLIENT,
                                          client_spec)

    cfg_common = container.getConfig(config.ModConfig.Type.COMMON)
    cfg_client = container.getConfig(config.ModConfig.Type.CLIENT)
    check(u"注册了两份配置", len(container.getConfigs()) == 2)
    check(u"getConfig 按类型取回", container.getConfig(config.ModConfig.Type.COMMON)
          is cfg_common)
    check(u"未注册的类型取到 None",
          container.getConfig(config.ModConfig.Type.SERVER) is None)
    check(u"ModConfig 记住 spec", cfg_common.getSpec() is common_spec)
    check(u"ModConfig.getModId 正确",
          cfg_common.getModId() == u"manaita_plus_legacy", cfg_common.getModId())
    check(u"ModConfig.getType 正确",
          cfg_common.getType() is config.ModConfig.COMMON)

    check(u"Type 按身份比较",
          config.ModConfig.Type.COMMON is config.ModConfig.COMMON)
    check(u"COMMON 与 CLIENT 不同",
          config.ModConfig.COMMON != config.ModConfig.CLIENT)
    check(u"Type.name()", config.ModConfig.COMMON.name() == u"COMMON")

    # ------------------------------------------------------------
    section("端到端：照真实写法走完整流程")
    # ------------------------------------------------------------
    event.EventBusSubscriber.clear_pending()

    # 对应 Java 的 ModConfigSpec.Builder BUILDER = new ModConfigSpec.Builder();
    BUILDER = config.ModConfigSpec.Builder()

    # 对应那一串链式 define
    creative_range_destroy = (
        BUILDER.comment(u"This determines whether the creative can use range mining")
               .define(u"creative_range_destroy", False))
    experience_drops_doubling = (
        BUILDER.comment(u"ExperienceDropsDoubling")
               .defineInRange(u"experience_drops_doubling_value", 4, 1,
                              config.ModConfigSpecBuilder.INT_MAX))
    crafting_doubling = (
        BUILDER.comment(u"CraftingDoubling")
               .defineInRange(u"crafting_doubling_value", 64, 1,
                              config.ModConfigSpecBuilder.INT_MAX))

    # 对应 public static final ModConfigSpec SPEC = BUILDER.build();
    SPEC = BUILDER.build()
    check(u"SPEC 有 3 项", SPEC.size() == 3, SPEC.size())

    # 对应那些 public static 字段（取值缓存）
    state = {u"creative_range_destroy_value": None,
             u"experience_drops_doubling_value": None,
             u"crafting_doubling_value": None}

    # 对应 @EventBusSubscriber + @SubscribeEvent 的加载回调
    @event.EventBusSubscriber(modid=u"manaita_plus_legacy")
    class ManaitaPlusLegacyConfig(object):
        @event.SubscribeEvent
        def onLoad(e):
            # 对应 event.getConfig().getModId().equals(...) && getSpec() == SPEC
            cfg = e.getConfig()
            if cfg is not None and cfg.getModId() == u"manaita_plus_legacy" \
                    and cfg.getSpec() is SPEC:
                state[u"creative_range_destroy_value"] = creative_range_destroy.get()
                state[u"experience_drops_doubling_value"] = \
                    experience_drops_doubling.get()
                state[u"crafting_doubling_value"] = crafting_doubling.get()

    # 对应 @Mod 构造函数里的 modContainer.registerConfig(...)
    mod_container = config.ModContainer(u"manaita_plus_legacy")
    mod_container.registerConfig(config.ModConfig.Type.COMMON, SPEC)

    bus = event.IEventBus(u"manaita_plus_legacy")
    count, _skipped = event.EventBusSubscriber.register_all(bus)
    check(u"配置回调已装配", count == 1, count)

    # 触发 ModConfigEvent.Loading
    bus.post(event.ModConfigEvent.Loading(mod_container.getConfig(
        config.ModConfig.Type.COMMON)))

    check(u"回调把默认值抄进了缓存字段",
          state[u"experience_drops_doubling_value"] == 4,
          state[u"experience_drops_doubling_value"])
    check(u"布尔默认值也抄进来了",
          state[u"creative_range_destroy_value"] is False,
          state[u"creative_range_destroy_value"])

    # 现在模拟「用户改了配置文件」
    SPEC.loadFrom({u"experience_drops_doubling_value": 16,
                   u"creative_range_destroy": True})

    # 触发 Reloading
    bus.post(event.ModConfigEvent.Reloading(mod_container.getConfig(
        config.ModConfig.Type.COMMON)))
    check(u"重载后缓存字段更新为 16",
          state[u"experience_drops_doubling_value"] == 16,
          state[u"experience_drops_doubling_value"])
    check(u"重载后布尔也更新",
          state[u"creative_range_destroy_value"] is True)

    # 别的模组的配置不应触发我们的回调
    other_container = config.ModContainer(u"other_mod")
    other_spec = config.ModConfigSpecBuilder().build()
    other_container.registerConfig(config.ModConfig.Type.COMMON, other_spec)
    state[u"experience_drops_doubling_value"] = u"未改动"
    bus.post(event.ModConfigEvent.Loading(other_container.getConfig(
        config.ModConfig.Type.COMMON)))
    check(u"别的模组的配置不会动我们的值",
          state[u"experience_drops_doubling_value"] == u"未改动",
          state[u"experience_drops_doubling_value"])

    # ------------------------------------------------------------
    section("名称映射表")
    # ------------------------------------------------------------
    for java_name in (
        "net.neoforged.neoforge.common.ModConfigSpec",
        "net.neoforged.neoforge.common.ModConfigSpec$Builder",
        "net.neoforged.neoforge.common.ModConfigSpec$IntValue",
        "net.neoforged.neoforge.common.ModConfigSpec$BooleanValue",
        "net.neoforged.fml.config.ModConfig",
        "net.neoforged.fml.config.IConfigSpec",
        "net.neoforged.fml.ModContainer",
        # 配置事件搬到 event 包之后仍在总表里
        "net.neoforged.fml.event.config.ModConfigEvent",
        "net.neoforged.fml.event.config.ModConfigEvent$Loading",
    ):
        if java_name in config.JAVA_MAP:
            check(u"config 映射 {}".format(java_name), True)
        else:
            check(u"event 映射 {}".format(java_name),
                  java_name in event.JAVA_MAP)

finally:
    event.EventBusSubscriber.clear_pending()

sys.exit(summary())
