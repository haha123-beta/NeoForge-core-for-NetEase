# -*- coding: utf-8 -*-
# neoforge/config.py
# β 层：NeoForge 配置系统（ModConfigSpec）
#
# 真实用法（从反编译源码逐字提取）：
#
#   public class ManaitaPlusLegacyConfig {
#       private static final ModConfigSpec.Builder BUILDER = new ModConfigSpec.Builder();
#
#       private static final ModConfigSpec.BooleanValue creative_range_destroy =
#           BUILDER.comment("This determines whether the creative can use range mining")
#                  .define("creative_range_destroy", false);
#
#       private static final ModConfigSpec.IntValue experience_drops_doubling =
#           BUILDER.comment("ExperienceDropsDoubling")
#                  .defineInRange("experience_drops_doubling_value", 4, 1, Integer.MAX_VALUE);
#
#       public static final ModConfigSpec SPEC = BUILDER.build();
#       public static int item_drops_doubling_value;          // 取值缓存
#
#       @SubscribeEvent
#       static void onLoad(ModConfigEvent.Loading event) {
#           if (event.getConfig().getModId().equals("manaita_plus_legacy")
#                   && event.getConfig().getSpec() == SPEC) {
#               item_drops_doubling_value = (Integer) item_drops_doubling.get();
#           }
#       }
#   }
#
#   注册（在 @Mod 构造函数里）：
#       modContainer.registerConfig(ModConfig.Type.COMMON, SPEC);
#       modContainer.registerConfig(ModConfig.Type.CLIENT, SPEC);
#
# 三个必须照 Java 来的语义：
#   1. `comment(...)` 返回 Builder 自身，所以能 `.comment(x).define(...)` 链式调用；
#   2. `define*` 会**在 builder 上登记**一个配置项并返回它的句柄，
#      `build()` 才把所有登记项收进 SPEC；
#   3. 句柄的 `get()` 返回**当前生效值**，配置没加载时是默认值 ——
#      模组代码在 onLoad 里把 get() 抄进静态字段，之后就读静态字段。
#
# 关于「读配置文件」：核心读写走字典/字符串，不碰文件系统。
# 原因见 概览.md「待验证的部署问题」第 4 条 —— os 不在官方模块白名单里，
# 所以文件 I/O 被隔离在明确标注的可选函数中，默认不参与加载流程。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import
from java_stdlib.lang import JavaString

try:
    from java_stdlib._base import (
        IllegalArgumentException,
        IllegalStateException,
    )
    from java_stdlib.lang import java_to_string
except ImportError:
    from _base import (  # type: ignore
        IllegalArgumentException,
        IllegalStateException,
    )
    from lang import java_to_string  # type: ignore


# ============================================================
# ModConfig.Type
# ============================================================

class _ConfigType(object):
    """配置作用域：对应 ModConfig.Type 的枚举成员。"""

    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name

    def toString(self):
        return self._name

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    def __hash__(self):
        return id(self)

    def __str__(self):
        return self._name

    def __repr__(self):
        return u"<ModConfig.Type.{}>".format(self._name)


class ModConfig(object):
    """
    对应 net.neoforged.fml.config.ModConfig。

    一个实例代表「某个模组某一份已加载的配置」。
    模组在 ModConfigEvent 里通过 event.getConfig() 拿到它，
    再比对 getModId / getSpec 确认「这份配置是不是我的」。

    关于 Type：
      Java 里 Type 是 ModConfig 的内部枚举。Python 里如果直接在类体里写
      `class Type: COMMON = ModConfig.COMMON`，会因为**类体执行时 ModConfig
      这个名字还不存在**而 NameError（实测踩到）。
      所以枚举成员先在模块层建好，类定义完之后再挂上去（见文件下方）。
    """

    def __init__(self, config_type, spec, modid=None, file_name=None):
        self._file_name = file_name
        self._type = config_type
        self._spec = spec
        self._modid = java_to_string(modid) if modid is not None else None

    def getFileName(self):
        return self._file_name

    def getType(self):
        return self._type

    def getSpec(self):
        return self._spec

    def getModId(self):
        # DS-08（A08）：Java 侧 getModId() 返回 java.lang.String，生成的
        # `event.getConfig().getModId().equals("...")` 会对返回值调用 String 方法。
        # 有效字符串统一以已有 JavaString 形式返回（与 ModContainer.getModId 一致），
        # 保留空值路径（官方证据未要求改变 None 行为）；不改变 get()/其它字符串约定。
        if self._modid is not None:
            return JavaString(self._modid)
        if self._spec is not None and self._spec.modid is not None:
            return JavaString(self._spec.modid)
        return None

    def setModId(self, modid):
        self._modid = java_to_string(modid)
        return None

    def __repr__(self):
        return u"<ModConfig {} modid={}>".format(self._type, self.getModId())


# 配置作用域常量：先建好，稍后同时挂到 ModConfig 与 ModConfig.Type 上。
# 两个入口都要能用（真实代码写 ModConfig.Type.COMMON）。
_CONFIG_TYPE_COMMON = _ConfigType(u"COMMON")
_CONFIG_TYPE_CLIENT = _ConfigType(u"CLIENT")
_CONFIG_TYPE_SERVER = _ConfigType(u"SERVER")
_CONFIG_TYPE_STARTUP = _ConfigType(u"STARTUP")

ModConfig.COMMON = _CONFIG_TYPE_COMMON
ModConfig.CLIENT = _CONFIG_TYPE_CLIENT
ModConfig.SERVER = _CONFIG_TYPE_SERVER
ModConfig.STARTUP = _CONFIG_TYPE_STARTUP


class _ModConfigType(object):
    """对应 ModConfig.Type：只是把四个枚举成员归在一起，方便 ModConfig.Type.COMMON。"""

    COMMON = _CONFIG_TYPE_COMMON
    CLIENT = _CONFIG_TYPE_CLIENT
    SERVER = _CONFIG_TYPE_SERVER
    STARTUP = _CONFIG_TYPE_STARTUP


ModConfig.Type = _ModConfigType


class IConfigSpec(object):
    """对应 net.neoforged.fml.config.IConfigSpec：配置规格的接口标记。"""

    def isEmpty(self):
        raise NotImplementedError()


# ============================================================
# 配置值句柄
# ============================================================

class ConfigValue(object):
    """
    配置项句柄基类。

    真实模组拿到的是 IntValue / BooleanValue 这类具体句柄，
    调 `.get()` 取当前值。
    """

    _type_name = u"Value"

    def __init__(self, path, default, comment=None, spec=None):
        self.path = java_to_string(path)
        self._default = default
        self._value = default
        self.comment_text = comment
        self._spec = spec

    # ---------------- 取值 / 赋值 ----------------

    def get(self):
        return self._value

    def getDefault(self):
        return self._default

    def set(self, value):
        """直接设值（用于加载配置与自测）。真实代码很少这样调。"""
        self._value = self._coerce(value)
        return None

    def reset(self):
        self._value = self._default
        return None

    def _coerce(self, value):
        """把外部值转成本配置项的类型。子类覆盖以做校验。"""
        return value

    def getPath(self):
        return self.path

    def getComment(self):
        return self.comment_text

    # ---------------- 展示 ----------------

    def toString(self):
        return java_to_string(self._value)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return u"<{}.{} = {!r}>".format(self._type_name, self.path, self._value)


class BooleanValue(ConfigValue):
    """对应 ModConfigSpec.BooleanValue。"""

    _type_name = u"BooleanValue"

    def _coerce(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = java_to_string(value).strip().lower()
        if text in (u"true", u"1", u"yes"):
            return True
        if text in (u"false", u"0", u"no"):
            return False
        raise IllegalArgumentException(
            u"{} 需要布尔值，收到 {!r}".format(self.path, value))

    def getAsBoolean(self):
        # 官方方法体（21.1.233 universal jar javap -c）：
        #   checkcast java/lang/Boolean; invokevirtual Boolean.booleanValue()Z; ireturn
        # 读取当前值并返回基本 boolean（不是 Java Boolean 包装对象）。
        value = self.get()
        return bool(value.booleanValue() if hasattr(value, "booleanValue") else value)


class _RangedIntegerValue(ConfigValue):
    """对应 ModConfigSpec.IntValue，带范围校验。"""

    _type_name = u"IntValue"

    def __init__(self, path, default, comment=None, spec=None,
                 min_value=None, max_value=None):
        ConfigValue.__init__(self, path, default, comment, spec)
        self.min_value = min_value
        self.max_value = max_value
        self._check_range(default)

    def _check_range(self, value):
        if self.min_value is not None and value < self.min_value:
            raise IllegalArgumentException(
                u"{} 的值 {} 小于下限 {}".format(self.path, value, self.min_value))
        if self.max_value is not None and value > self.max_value:
            raise IllegalArgumentException(
                u"{} 的值 {} 大于上限 {}".format(self.path, value, self.max_value))

    def _coerce(self, value):
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise IllegalArgumentException(
                u"{} 需要整数，收到 {!r}".format(self.path, value))
        self._check_range(number)
        return number

    def getMin(self):
        return self.min_value

    def getMax(self):
        return self.max_value

class IntValue(_RangedIntegerValue):
    _type_name = u"IntValue"

    def getAsInt(self):
        # 官方方法体（21.1.233 universal jar javap -c）：
        #   checkcast java/lang/Integer; invokevirtual Integer.intValue()I; ireturn
        # 读取当前值并返回基本 int（范围校验仍在 set/load 的 _coerce 中生效）。
        value = self.get()
        return int(value.intValue() if hasattr(value, "intValue") else value)


class LongValue(_RangedIntegerValue):
    """Independent Java sibling of IntValue; never inherits getAsInt."""

    _type_name = u"LongValue"

    def getAsLong(self):
        value = self.get()
        return int(value.longValue() if hasattr(value, "longValue") else value)


class DoubleValue(ConfigValue):
    """对应 ModConfigSpec.DoubleValue，带范围校验。"""

    _type_name = u"DoubleValue"

    def __init__(self, path, default, comment=None, spec=None,
                 min_value=None, max_value=None):
        ConfigValue.__init__(self, path, default, comment, spec)
        self.min_value = min_value
        self.max_value = max_value

    def _coerce(self, value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise IllegalArgumentException(
                u"{} 需要浮点数，收到 {!r}".format(self.path, value))
        if self.min_value is not None and number < self.min_value:
            raise IllegalArgumentException(
                u"{} 的值 {} 小于下限 {}".format(self.path, number, self.min_value))
        if self.max_value is not None and number > self.max_value:
            raise IllegalArgumentException(
                u"{} 的值 {} 大于上限 {}".format(self.path, number, self.max_value))
        return number

    def getAsDouble(self):
        # 官方方法体（21.1.233 universal jar javap -c）：
        #   checkcast java/lang/Double; invokevirtual Double.doubleValue()D; dreturn
        # 读取当前值并返回基本 double（范围校验仍在 set/load 的 _coerce 中生效）。
        value = self.get()
        return float(value.doubleValue() if hasattr(value, "doubleValue") else value)


class StringValue(ConfigValue):
    """对应 ModConfigSpec.ConfigValue<String>。"""

    _type_name = u"StringValue"

    def _coerce(self, value):
        return java_to_string(value)


class ListValue(ConfigValue):
    """对应 defineList 产出的列表配置项。"""

    _type_name = u"ListValue"

    def _coerce(self, value):
        if isinstance(value, (list, tuple)):
            return [item for item in value]
        # 单个值也接受，包成单元素列表（与 Java 的宽松读取一致）
        return [value]


# ============================================================
# ModConfigSpec
# ============================================================

class ModConfigSpec(IConfigSpec):
    """
    对应 net.neoforged.neoforge.common.ModConfigSpec。

    它是「一份配置的定义 + 当前值」的整体，由 Builder.build() 产出。
    模组用 `event.getConfig().getSpec() == SPEC` 判断这份配置是不是自己的，
    所以 SPEC 必须是**稳定对象**（身份比较）。
    """

    def __init__(self, modid=None, config_registry=None):
        self._config_registry = config_registry if config_registry is not None else ConfigRegistry()
        self._closed = False
        self.modid = modid
        self._values = []
        self._by_path = {}
        self._loaded = False

    # ---------------- 查询 ----------------

    def getValues(self):
        return list(self._values)

    def size(self):
        return len(self._values)

    def isEmpty(self):
        return len(self._values) == 0

    def getValue(self, path):
        return self._by_path.get(java_to_string(path))

    def hasValue(self, path):
        return java_to_string(path) in self._by_path

    def isLoaded(self):
        return self._loaded

    def markLoaded(self):
        self._loaded = True
        return None

    # ---------------- 加载 ----------------

    def loadFrom(self, mapping):
        """
        从 {路径: 值} 载入配置。

        对应 Java 里「FML 读取配置文件后填进 SPEC」这一步。
        未出现在 mapping 里的项保持默认值；
        出现但非法的值会抛异常并**点名是哪个键** ——
        静默忽略会让用户改了配置却不生效，极难排查。
        """
        if mapping is None:
            self._loaded = True
            return 0

        if not isinstance(mapping, dict):
            raise IllegalArgumentException("Configuration must be a JSON object")
        staged = []
        for path in sorted(mapping.keys()):
            key = java_to_string(path)
            value = mapping[path]
            target = self._by_path.get(key)
            if target is None:
                # 未知键不报错：配置文件里常有历史遗留项，
                # 因为一个多余键就让模组起不来不值得。
                continue
            try:
                staged.append((target, target._coerce(value)))
            except Exception as error:
                raise IllegalArgumentException(
                    u"配置项 {} 的值 {!r} 非法: {}".format(key, value, error))

        # Validate the complete document before publishing any new values.
        for target, value in staged:
            target._value = value
        self._loaded = True
        return len(staged)

    def toDict(self):
        """导出当前值 {路径: 值}，便于自测与诊断。"""
        result = {}
        for value in self._values:
            result[value.path] = value.get()
        return result

    def __repr__(self):
        return u"<ModConfigSpec modid={} {} 项>".format(self.modid,
                                                        len(self._values))


# ============================================================
# Builder
# ============================================================

class ModConfigSpecBuilder(object):
    """
    对应 ModConfigSpec.Builder。

    链式约定：comment / translation / push / pop 返回自身，
    只有 define* 返回配置项句柄 —— 与 Java 完全一致。

    真实代码的写法：
        BUILDER.comment("说明").defineInRange("key", 4, 1, Integer.MAX_VALUE)
    即「先写注释，再定义项」，注释作用于紧跟其后的那一项。
    """

    # Java 里 Integer.MAX_VALUE，配置里常作为上限
    INT_MAX = 2147483647
    INT_MIN = -2147483648

    def __init__(self, modid=None, config_registry=None):
        self._config_registry = config_registry if config_registry is not None else ConfigRegistry()
        self._closed = False
        self.modid = modid
        self._pending_comment = None
        self._pending_translation = None
        self._path_stack = []
        self._defined = []
        self._built = None

    # ---------------- 链式设置 ----------------

    def comment(self, *lines):
        """设置下一项的注释；支持多行（Java 也是可变参数）。"""
        self._pending_comment = u"\n".join(
            [java_to_string(line) for line in lines])
        return self

    def translation(self, key):
        """设置下一项的翻译键。"""
        self._pending_translation = java_to_string(key)
        return self

    def push(self, path):
        """进入子节点，后续 define 的路径会带上这个前缀。"""
        self._path_stack.append(java_to_string(path))
        return self

    def pop(self, count=1):
        """退出若干层子节点。"""
        for _index in range(int(count)):
            if self._path_stack:
                self._path_stack.pop()
        return self

    def worldRestart(self):
        """标记需重启世界才生效；Python 实现里没有实际作用，保留以兼容调用。"""
        return self

    # ---------------- 定义配置项 ----------------

    def _full_path(self, path):
        text = java_to_string(path)
        if self._path_stack:
            return u".".join(self._path_stack + [text])
        return text

    def _take_comment(self):
        comment = self._pending_comment
        self._pending_comment = None
        self._pending_translation = None
        return comment

    def define(self, path, default):
        """
        对应 Builder.define(path, default)。

        按默认值的 Python 类型选句柄类型 —— Java 靠泛型，
        Python 靠值本身，这样 define("x", False) 得到 BooleanValue。
        """
        full = self._full_path(path)
        comment = self._take_comment()

        if isinstance(default, bool):
            value = BooleanValue(full, default, comment)
        elif isinstance(default, int):
            value = IntValue(full, default, comment)
        elif isinstance(default, float):
            value = DoubleValue(full, default, comment)
        else:
            value = StringValue(full, default, comment)

        return self._add(full, value)

    def defineInRange(self, path, default, min_value, max_value):
        """对应 defineInRange(path, default, min, max)：带范围校验。"""
        full = self._full_path(path)
        comment = self._take_comment()

        # 上下限一律用**关键字**传：构造函数中间还夹着 spec 参数，
        # 按位置传会把 min/max 整体串位（实测踩到：
        # 「4 小于下限 2147483647」就是 min 收到了 max 的值）。
        if isinstance(default, bool):
            # 布尔没有范围概念，Java 也不会这么用
            value = BooleanValue(full, default, comment)
        elif isinstance(default, float):
            value = DoubleValue(full, default, comment,
                                min_value=min_value, max_value=max_value)
        else:
            value = IntValue(full, default, comment,
                             min_value=min_value, max_value=max_value)

        return self._add(full, value)

    def _defineLongRange(self, path, default, min_value, max_value):
        # Called by the compiler after selecting the official JJJ overload.
        full = self._full_path(path)
        value = LongValue(full, default, self._take_comment(),
                          min_value=min_value, max_value=max_value)
        return self._add(full, value)

    def defineList(self, path, default):
        """对应 defineList：值是一个列表。"""
        full = self._full_path(path)
        comment = self._take_comment()
        value = ListValue(full, list(default), comment)
        return self._add(full, value)

    def _add(self, full_path, value):
        if self._built is not None:
            raise IllegalStateException(
                u"build() 之后不能再定义配置项（{}）".format(full_path))
        for existing_path, _handle in self._defined:
            if existing_path == full_path:
                raise IllegalArgumentException(
                    u"配置项 {} 重复定义".format(full_path))
        self._defined.append((full_path, value))
        return value

    # ---------------- 构建 ----------------

    def build(self):
        """
        对应 Builder.build()：产出 ModConfigSpec。

        同一 Builder 重复 build 返回**同一个** SPEC ——
        模组用 `getSpec() == SPEC` 做身份比较，
        若每次 build 都造新对象，这个判断会永远为假。
        """
        if self._built is not None:
            return self._built

        spec = ModConfigSpec(self.modid)
        for path, handle in self._defined:
            handle._spec = spec
            spec._values.append(handle)
            spec._by_path[path] = handle
        self._built = spec
        return spec


# Builder 的可用名字：Java 里是 ModConfigSpec.Builder 内部类
ModConfigSpec.Builder = ModConfigSpecBuilder


# ============================================================
# 模组容器
# ============================================================

class ConfigRegistry(object):
    """Session-owned configuration names; no process-global mod ownership."""
    def __init__(self):
        self._files = {}

    def register(self, owner, config):
        name = config.getFileName()
        if name in self._files:
            previous = self._files[name][1]
            raise IllegalStateException("Config file conflict: " + name +
                " (already registered by " + str(previous.getModId()) + ")")
        self._files[name] = (owner, config)

    def remove_owner(self, owner):
        for name, record in list(self._files.items()):
            if record[0] is owner:
                del self._files[name]


class ModContainer(object):
    """
    对应 net.neoforged.fml.ModContainer。

    @Mod 构造函数会收到它，用来注册配置：
        modContainer.registerConfig(ModConfig.Type.COMMON, SPEC);
    """

    def __init__(self, modid=None, config_registry=None):
        self._config_registry = config_registry if config_registry is not None else ConfigRegistry()
        self._closed = False
        self.modid = java_to_string(modid) if modid is not None else None
        self._configs = []

    def registerConfig(self, config_type, spec, fileName=None):
        """
        注册一份配置。

        Java 有两种重载：registerConfig(Type, IConfigSpec) 与
        registerConfig(Type, IConfigSpec, String fileName)。
        这里用可选参数承接（Python 没有重载，同 Boolean.toStringValue 的处理思路）。
        """
        if self._closed:
            raise IllegalStateException("Mod container is closed")
        if spec.isEmpty():
            return None
        if fileName is None:
            fileName = u"{}-{}.toml".format(self.modid, config_type.name().lower())
        config = ModConfig(config_type, spec, self.modid, java_to_string(fileName))
        self._config_registry.register(self, config)
        self._configs.append(config)
        return None

    def close(self):
        self._closed = True
        self._config_registry.remove_owner(self)
        self._configs = []

    def getConfigs(self):
        return list(self._configs)

    def getConfig(self, config_type):
        for config in self._configs:
            if config.getType() is config_type:
                return config
        return None

    def getModId(self):
        return JavaString(self.modid)

    def __repr__(self):
        return u"<ModContainer {} {} 份配置>".format(self.modid,
                                                     len(self._configs))


class FMLModContainer(ModContainer):
    def __init__(self,modid=None,config_registry=None):
        ModContainer.__init__(self,modid,config_registry)
        self._event_bus=None
    def getEventBus(self):
        if self._event_bus is None:raise IllegalStateException("FML mod event bus is not attached")
        return self._event_bus


# ============================================================
# Explicit host-supplied configuration I/O; no forbidden filesystem imports.
# ============================================================

def load_config_file(spec, path, storage=None):
    """storage.read_text(path) returns text or None for a missing document."""
    if storage is None:
        raise NotImplementedError("Configuration I/O requires an explicit storage adapter")
    import json
    source = storage.read_text(path)
    if source is None:
        spec.markLoaded()
        return 0
    try:
        data = json.loads(source)
    except ValueError as error:
        raise IllegalArgumentException("Invalid configuration JSON: " + str(error))
    if not isinstance(data, dict):
        raise IllegalArgumentException("Configuration JSON root must be an object")
    return spec.loadFrom(data)


def save_config_file(spec, path, storage=None):
    """The host adapter owns file creation, persistence and write failures."""
    if storage is None:
        raise NotImplementedError("Configuration I/O requires an explicit storage adapter")
    import json
    storage.write_text(path, json.dumps(spec.toDict(), indent=2, sort_keys=True))


# ============================================================
# 名称映射表
# ============================================================

JAVA_MAP = {
    "net.neoforged.neoforge.common.ModConfigSpec": ModConfigSpec,
    "net.neoforged.neoforge.common.ModConfigSpec$Builder": ModConfigSpecBuilder,
    "net.neoforged.neoforge.common.ModConfigSpec$BooleanValue": BooleanValue,
    "net.neoforged.neoforge.common.ModConfigSpec$IntValue": IntValue,
    "net.neoforged.neoforge.common.ModConfigSpec$LongValue": LongValue,
    "net.neoforged.neoforge.common.ModConfigSpec$DoubleValue": DoubleValue,
    "net.neoforged.neoforge.common.ModConfigSpec$ConfigValue": ConfigValue,
    "net.neoforged.fml.config.ModConfig": ModConfig,
    "net.neoforged.fml.config.ModConfig$Type": ModConfig.Type,
    "net.neoforged.fml.config.IConfigSpec": IConfigSpec,
    "net.neoforged.fml.ModContainer": ModContainer,
    "net.neoforged.fml.javafmlmod.FMLModContainer": FMLModContainer,
}


__all__ = [
    "ModConfig", "IConfigSpec",
    "ConfigValue", "BooleanValue", "IntValue", "LongValue",
    "DoubleValue", "StringValue", "ListValue",
    "ModConfigSpec", "ModConfigSpecBuilder",
    "ModContainer",
    "load_config_file", "save_config_file",
    "JAVA_MAP",
]
