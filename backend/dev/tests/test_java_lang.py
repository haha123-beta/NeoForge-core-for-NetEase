# -*- coding: utf-8 -*-
"""
Σ 层自测：java_stdlib/lang.py（java.lang 复刻）

为什么这些必须逐条测：
    Java 与 Python 在很多地方「名字一样、语义不同」，照抄就会出隐蔽 bug：
      - Java 的 Math.round 是四舍五入，Python 的 round 是银行家舍入
        （round(2.5)：Java 得 3，Python 得 2）
      - Java 的 compareTo 返回负/0/正，不是布尔
      - Java 的 String.trim 只去码位 <= 0x20，Python 的 strip 去得更多
      - Java 的 split 用正则且默认丢尾部空串，Python 的 split 用字面量
      - Java 的 parseInt 失败抛 NumberFormatException，不是 ValueError

方案说明（重要）：
    本层**不**给 str 注入方法 —— Python 3 不允许
    （TypeError: cannot set 'length' attribute of immutable type 'str'），
    所以走两条路，两条都要验：
      StringOps.length(s)     函数式，接受任意值（含 None），推荐
      JavaString(s).length()  方法式，用于需要保留方法调用形态的场合

验证点：
  1. StringOps 的每个方法按 Java 语义工作
  2. 原生字符串**完全不受影响**（没有注入副作用）
  3. JavaString 的方法形式可用
  4. 与 Python 语义不同的那些点逐个核对
  5. String 静态方法（valueOf/format/join）
  6. StringBuilder 链式调用与变异操作
  7. 数值包装类型、Math、ThreadLocal/Runnable/Enum/Object/System
  8. JAVA_MAP 对照真实模组引用的覆盖率
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
lang = pkg.load("java_stdlib.lang")

String = lang.String
StringOps = lang.StringOps
JavaString = lang.JavaString
StringBuilder = lang.StringBuilder
Integer = lang.Integer


def raises(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("方案前提：确认不能给 str 注入方法")
    # ------------------------------------------------------------
    # 这条断言是「为什么要有 StringOps」的证据，别删
    check(u"原生 str 上没有 length 方法（Py3 不允许注入）",
          not hasattr(u"abc", "length"))
    check(u"injection_report 如实报告注入数为 0",
          lang.injection_report()[0][1] == 0, lang.injection_report())
    check(u"确实没有给 str 注入 substring", not hasattr(u"abc", "substring"))

    # ------------------------------------------------------------
    section("StringOps：长度与取值")
    # ------------------------------------------------------------
    s = u"Hello World"
    check(u"length()", StringOps.length(s) == 11, StringOps.length(s))
    check(u"isEmpty 假", StringOps.isEmpty(s) is False)
    check(u"isEmpty 真", StringOps.isEmpty(u"") is True)
    check(u"charAt(0)", StringOps.charAt(s, 0) == u"H", StringOps.charAt(s, 0))
    check(u"charAt 越界抛异常", raises(StringOps.charAt, s, 99))
    check(u"charAt 负数抛异常", raises(StringOps.charAt, s, -1))
    check(u"toCharArray", StringOps.toCharArray(u"ab") == [u"a", u"b"])

    # 接受任意值：这是函数式方案的关键优势
    check(u"length 接受 None -> 'null' 的长度",
          StringOps.length(None) == 4, StringOps.length(None))
    check(u"length 接受整数", StringOps.length(12345) == 5, StringOps.length(12345))
    check(u"length 接受布尔", StringOps.length(True) == 4, StringOps.length(True))
    check(u"length 接受 JavaString", StringOps.length(JavaString(u"abc")) == 3)

    # ------------------------------------------------------------
    section("StringOps：截取（左闭右开）")
    # ------------------------------------------------------------
    check(u"substring(0, 5)", StringOps.substring(s, 0, 5) == u"Hello")
    check(u"substring(6) 到末尾", StringOps.substring(s, 6) == u"World")
    check(u"substring 区间非法抛异常", raises(StringOps.substring, s, 5, 2))
    check(u"substring 起点越界抛异常", raises(StringOps.substring, s, 99))
    check(u"subSequence 同 substring",
          StringOps.subSequence(s, 0, 5) == u"Hello")

    # ------------------------------------------------------------
    section("StringOps：查找")
    # ------------------------------------------------------------
    check(u"indexOf 命中", StringOps.indexOf(s, u"World") == 6)
    check(u"indexOf 未命中返回 -1", StringOps.indexOf(s, u"zzz") == -1)
    check(u"indexOf 带起点", StringOps.indexOf(s, u"o", 5) == 7)
    check(u"lastIndexOf", StringOps.lastIndexOf(u"a.b.c", u".") == 3)
    check(u"contains", StringOps.contains(s, u"World") is True)
    check(u"contains 不存在", StringOps.contains(s, u"zzz") is False)
    check(u"startsWith", StringOps.startsWith(s, u"Hello") is True)
    check(u"startsWith 带偏移", StringOps.startsWith(s, u"World", 6) is True)
    check(u"endsWith", StringOps.endsWith(s, u"World") is True)
    check(u"matches 正则", StringOps.matches(u"abc123", u"[a-z]+\\d+") is True)
    check(u"matches 不匹配", StringOps.matches(u"abc", u"\\d+") is False)

    # ------------------------------------------------------------
    section("StringOps：比较")
    # ------------------------------------------------------------
    check(u"equals 内容相同为真", StringOps.equals(u"abc", u"abc") is True)
    check(u"equals 内容不同为假", StringOps.equals(u"abc", u"abd") is False)
    check(u"equals(null) 为假", StringOps.equals(u"abc", None) is False)
    check(u"equals(数字) 为假（不是字符串）",
          StringOps.equals(u"1", 1) is False, StringOps.equals(u"1", 1))
    check(u"equalsIgnoreCase", StringOps.equalsIgnoreCase(u"ABC", u"abc") is True)

    # compareTo 返回负/0/正，不是布尔
    check(u"compareTo 相等返回 0", StringOps.compareTo(u"b", u"b") == 0)
    check(u"compareTo 小于返回负", StringOps.compareTo(u"a", u"b") < 0)
    check(u"compareTo 大于返回正", StringOps.compareTo(u"c", u"b") > 0)
    check(u"compareTo 返回整数而非布尔",
          isinstance(StringOps.compareTo(u"a", u"b"), int))
    check(u"compareToIgnoreCase",
          StringOps.compareToIgnoreCase(u"A", u"a") == 0)

    # ------------------------------------------------------------
    section("与 Python 内建语义不同的方法")
    # ------------------------------------------------------------
    # trim：Java 只去码位 <= 0x20
    check(u"trim 去空格", StringOps.trim(u"  x  ") == u"x")
    check(u"trim 去制表与换行", StringOps.trim(u"\t\nx\r ") == u"x")
    check(u"trim 保留非 ASCII 空白（Python strip 会去掉）",
          StringOps.trim(u"\u3000x\u3000") == u"\u3000x\u3000",
          repr(StringOps.trim(u"\u3000x\u3000")))
    check(u"对照：Python 的 strip 确实会去掉它",
          u"\u3000x\u3000".strip() == u"x")

    # replace：字面量替换（不是正则）
    check(u"replace 是字面量替换",
          StringOps.replace(u"a.b", u".", u"-") == u"a-b")
    check(u"replaceAll 才用正则",
          StringOps.replaceAll(u"a1b2", u"\\d", u"-") == u"a-b-")
    check(u"replaceFirst 只换第一个",
          StringOps.replaceFirst(u"a1b2", u"\\d", u"-") == u"a-b2")

    # split：正则 + 默认丢尾部空串
    check(u"split 用正则", StringOps.split(u"a1b2c", u"\\d") == [u"a", u"b", u"c"])
    check(u"split 默认丢掉尾部空串",
          StringOps.split(u"a,b,,", u",") == [u"a", u"b"],
          StringOps.split(u"a,b,,", u","))
    check(u"split 保留中间空串",
          StringOps.split(u"a,,b", u",") == [u"a", u"", u"b"],
          StringOps.split(u"a,,b", u","))
    check(u"split limit>0 保留尾部空串",
          StringOps.split(u"a,b,,", u",", -1) == [u"a", u"b", u"", u""],
          StringOps.split(u"a,b,,", u",", -1))

    # ------------------------------------------------------------
    section("原生字符串完全不受影响（无注入副作用）")
    # ------------------------------------------------------------
    raw = u"hello world"
    check(u"是真 str", type(raw) is str)
    check(u"len() 仍可用", len(raw) == 11)
    check(u"切片仍可用", raw[0:5] == u"hello")
    check(u"拼接仍可用", raw + u"!" == u"hello world!")
    check(u"in 判断仍可用", u"world" in raw)
    check(u"startswith 原样", raw.startswith(u"hello"))
    check(u"strip 原样", u" x ".strip() == u"x")
    check(u"split 原样（字面量、不丢空串）",
          u"a,b,,".split(u",") == [u"a", u"b", u"", u""])
    check(u"字典键仍可用", {raw: 1}[u"hello world"] == 1)
    check(u"能参与排序", sorted([u"b", u"a"]) == [u"a", u"b"])
    check(u"format 仍可用", u"{}-{}".format(1, 2) == u"1-2")

    # ------------------------------------------------------------
    section("JavaString：方法形式")
    # ------------------------------------------------------------
    js = JavaString(u"Hello World")
    check(u"JavaString 是 str 的子类", isinstance(js, str))
    check(u"length()", js.length() == 11)
    check(u"isEmpty()", JavaString(u"").isEmpty() is True)
    check(u"charAt()", js.charAt(0) == u"H")
    check(u"substring(0,5)", js.substring(0, 5) == u"Hello")
    check(u"substring 结果仍是 JavaString",
          isinstance(js.substring(0, 5), JavaString))
    check(u"indexOf 命中", js.indexOf(u"World") == 6)
    check(u"indexOf 未命中返回 -1", js.indexOf(u"zzz") == -1)
    check(u"contains", js.contains(u"World") is True)
    check(u"startsWith", js.startsWith(u"Hello") is True)
    check(u"endsWith", js.endsWith(u"World") is True)
    check(u"equals", js.equals(u"Hello World") is True)
    check(u"equals(null) 为假", js.equals(None) is False)
    check(u"compareTo 返回整数", isinstance(js.compareTo(u"x"), int))
    check(u"toLowerCase", js.toLowerCase() == u"hello world")
    check(u"toUpperCase 结果是 JavaString",
          isinstance(js.toUpperCase(), JavaString))
    check(u"trim", JavaString(u"  x  ").trim() == u"x")
    check(u"split 返回 JavaString 列表",
          all([isinstance(p, JavaString) for p in JavaString(u"a,b").split(u",")]))
    check(u"toCharArray", js.toCharArray()[0] == u"H")
    check(u"concat", JavaString(u"a").concat(u"b") == u"ab")
    check(u"hashCode 与 StringOps 一致",
          js.hashCode() == StringOps.hashCode(u"Hello World"))
    check(u"toString", js.toString() == u"Hello World")

    # JavaString 也能直接当 str 用
    check(u"JavaString 可切片", js[0:5] == u"Hello")
    check(u"JavaString 可与 str 拼接", js + u"!" == u"Hello World!")
    check(u"JavaString 可作字典键", {js: 1}[u"Hello World"] == 1)
    check(u"to_java_string 转换", isinstance(lang.to_java_string(1), JavaString))
    check(u"to_java_string(None) 得到 'null'",
          lang.to_java_string(None) == u"null")

    # ------------------------------------------------------------
    section("String 静态方法")
    # ------------------------------------------------------------
    check(u"valueOf 字符串", String.valueOf(u"x") == u"x")
    check(u"valueOf 整数", String.valueOf(42) == u"42")
    check(u"valueOf null 得到 'null'", String.valueOf(None) == u"null",
          String.valueOf(None))
    check(u"valueOf True 得到 'true'", String.valueOf(True) == u"true")
    check(u"valueOf False 得到 'false'", String.valueOf(False) == u"false")
    check(u"valueOf 浮点整数形态", String.valueOf(2.0) == u"2.0")
    check(u"join", String.join(u"-", u"a", u"b") == u"a-b")
    check(u"join 传列表", String.join(u",", [u"a", u"b"]) == u"a,b")
    check(u"join 含 null", String.join(u",", [u"a", None]) == u"a,null")
    check(u"copyValueOf", String.copyValueOf([u"a", u"b"]) == u"ab")

    check(u"format %s", String.format(u"%s!", u"x") == u"x!")
    check(u"format %d", String.format(u"%d", 7) == u"7")
    check(u"format %% 转义", String.format(u"100%%") == u"100%")
    check(u"format %s 遇到 null", String.format(u"%s", None) == u"null")
    check(u"format 多个占位符", String.format(u"%s=%d", u"a", 1) == u"a=1")
    check(u"format %x", String.format(u"%x", 255) == u"ff")
    check(u"format 不认识的占位符原样保留",
          String.format(u"%q", 1) == u"%q", String.format(u"%q", 1))
    check(u"format 参数不足时不崩", isinstance(String.format(u"%s%s", u"a"), str))

    # ------------------------------------------------------------
    section("StringBuilder")
    # ------------------------------------------------------------
    builder = StringBuilder()
    check(u"append 返回自身（支持链式）", builder.append(u"a") is builder)
    builder.append(u"b").append(1).append(None)
    check(u"链式 append 结果", builder.toString() == u"ab1null",
          builder.toString())
    # "a" + "b" + "1" + "null" = 7 个字符
    check(u"length()", builder.length() == 7, builder.length())
    check(u"charAt", builder.charAt(0) == u"a")
    check(u"构造时带初值", StringBuilder(u"x").toString() == u"x")
    check(u"insert", StringBuilder(u"ac").insert(1, u"b").toString() == u"abc")
    check(u"insert 越界抛异常", raises(StringBuilder(u"a").insert, 9, u"x"))
    check(u"deleteCharAt",
          StringBuilder(u"abc").deleteCharAt(1).toString() == u"ac")
    check(u"delete 区间",
          StringBuilder(u"abcde").delete(1, 3).toString() == u"ade")
    check(u"replace 区间",
          StringBuilder(u"abc").replace(1, 2, u"X").toString() == u"aXc")
    check(u"reverse", StringBuilder(u"abc").reverse().toString() == u"cba")
    check(u"setLength 截断", StringBuilder(u"abc").setLength(2).toString() == u"ab")
    check(u"setLength 补 NUL 字符",
          len(StringBuilder(u"a").setLength(3).toString()) == 3)
    check(u"setLength 负数抛异常", raises(StringBuilder(u"a").setLength, -1))
    check(u"clear", StringBuilder(u"abc").clear().toString() == u"")
    check(u"isEmpty", StringBuilder().isEmpty() is True)
    check(u"substring", StringBuilder(u"abc").substring(1) == u"bc")
    check(u"indexOf", StringBuilder(u"abc").indexOf(u"b") == 1)
    check(u"StringBuffer 同实现", lang.StringBuffer is StringBuilder)
    check(u"len() 可用", len(StringBuilder(u"abc")) == 3)
    check(u"相等比较", StringBuilder(u"abc") == StringBuilder(u"abc"))
    check(u"appendCodePoint", StringBuilder().appendCodePoint(65).toString() == u"A")

    # ------------------------------------------------------------
    section("数值包装类型")
    # ------------------------------------------------------------
    check(u"Integer.parseInt", Integer.parseInt(u"42") == 42)
    check(u"Integer.parseInt 负数", Integer.parseInt(u"-7") == -7)
    check(u"parseInt 失败抛异常", raises(Integer.parseInt, u"abc"))
    try:
        Integer.parseInt(u"abc")
        check(u"parseInt 异常类型正确", False)
    except Exception as error:
        check(u"parseInt 异常类型正确",
              isinstance(error, lang.NumberFormatException), type(error).__name__)
    check(u"parseInt 带进制", Integer.parseInt(u"ff", 16) == 255)
    check(u"MAX_VALUE", Integer.MAX_VALUE == 2147483647)
    check(u"MIN_VALUE", Integer.MIN_VALUE == -2147483648)
    check(u"Integer.compare", Integer.compare(1, 2) == -1)
    check(u"Integer.valueOf", Integer.valueOf(u"5").intValue() == 5)
    check(u"Integer.valueOf(int)", Integer.valueOf(5).intValue() == 5)
    check(u"toHexString", Integer.toHexString(255) == u"ff")
    check(u"toBinaryString", Integer.toBinaryString(5) == u"101")
    check(u"toOctalString", Integer.toOctalString(8) == u"10")
    check(u"toHexString 负数按无符号", Integer.toHexString(-1) == u"ffffffff",
          Integer.toHexString(-1))
    check(u"Integer.toString 带进制（用 toStringRadix）",
          Integer.toStringRadix(255, 16) == u"ff",
          Integer.toStringRadix(255, 16))
    check(u"Integer.toStringRadix 默认十进制",
          Integer.toStringRadix(255) == u"255")
    check(u"实例 toString 仍可用", Integer(7).toString() == u"7")
    check(u"bitCount", Integer.bitCount(7) == 3)
    check(u"max/min", Integer.max(1, 2) == 2 and Integer.min(1, 2) == 1)
    check(u"进制越界抛异常", raises(Integer.toString, 1, 99))

    boxed = Integer(10)
    check(u"包装类型可参与加法", boxed + 5 == 15)
    check(u"包装类型可参与反向加法", 5 + boxed == 15)
    check(u"包装类型可参与比较", boxed > 5)
    check(u"包装类型可当列表下标", [0, 1, 2][Integer(1)] == 1)
    check(u"intValue", boxed.intValue() == 10)
    check(u"doubleValue", boxed.doubleValue() == 10.0)
    check(u"equals 与整数", boxed.equals(10) is True)
    check(u"byteValue 回绕", Integer(200).byteValue() == -56,
          Integer(200).byteValue())
    check(u"shortValue 回绕", Integer(40000).shortValue() == -25536,
          Integer(40000).shortValue())

    check(u"Long.parseLong", lang.Long.parseLong(u"123") == 123)
    check(u"Long.compare", lang.Long.compare(1, 2) == -1)
    check(u"Long.toHexString", lang.Long.toHexString(255) == u"ff")

    check(u"Double.parseDouble", lang.Double.parseDouble(u"1.5") == 1.5)
    check(u"Double.parseDouble 失败抛异常", raises(lang.Double.parseDouble, u"x"))
    check(u"Double.compare NaN 最大", lang.Double.compare(float(u"nan"), 1.0) == 1)
    check(u"Double.isNaN", lang.Double.isNaN(float(u"nan")) is True)
    check(u"Double 转字符串整数形态", lang.Double(2.0).toString() == u"2.0")
    check(u"Double.intValue 向零截断", lang.Double(2.9).intValue() == 2)
    check(u"Double.intValue 负数向零截断", lang.Double(-2.9).intValue() == -2)
    check(u"Float.parseFloat", lang.Float.parseFloat(u"2.5") == 2.5)
    check(u"Float.isNaN", lang.Float.isNaN(float(u"nan")) is True)

    check(u"Boolean.parseBoolean('true')", lang.Boolean.parseBoolean(u"true") is True)
    check(u"Boolean.parseBoolean('TRUE')", lang.Boolean.parseBoolean(u"TRUE") is True)
    check(u"parseBoolean('yes') 为假（Java 语义）",
          lang.Boolean.parseBoolean(u"yes") is False)
    check(u"parseBoolean(null) 为假", lang.Boolean.parseBoolean(None) is False)
    check(u"Boolean.toStringValue（静态入口）",
          lang.Boolean.toStringValue(True) == u"true",
          lang.Boolean.toStringValue(True))
    check(u"Boolean.hashCodeValue", lang.Boolean.hashCodeValue(True) == 1231)
    check(u"Boolean 实例 toString 仍可用",
          lang.Boolean(True).toString() == u"true")
    check(u"logicalXor", lang.Boolean.logicalXor(True, False) is True)
    check(u"Boolean 可当真值用", bool(lang.Boolean(True)) is True)

    check(u"Character.isDigit", lang.Character.isDigit(u"7") is True)
    check(u"Character.isLetter", lang.Character.isLetter(u"a") is True)
    check(u"getNumericValue 非数字返回 -1",
          lang.Character.getNumericValue(u"x") == -1)
    check(u"Character.toUpperCase", lang.Character.toUpperCase(u"a") == u"A")

    # ------------------------------------------------------------
    section("Math（Java 语义 vs Python 语义）")
    # ------------------------------------------------------------
    check(u"Java Math.round(2.5) == 3", lang.Math.round(2.5) == 3,
          lang.Math.round(2.5))
    check(u"Python round(2.5) == 2（对照，说明两者确实不同）", round(2.5) == 2)
    check(u"Math.round(-2.5) == -2", lang.Math.round(-2.5) == -2)
    check(u"Math.round(2.4) == 2", lang.Math.round(2.4) == 2)
    check(u"Math.round 返回整数类型",
          isinstance(lang.Math.round(2.5), int))
    check(u"Math.round(NaN) == 0", lang.Math.round(float(u"nan")) == 0)
    check(u"Math.floor 返回整数", lang.Math.floor(2.9) == 2
          and isinstance(lang.Math.floor(2.9), int))
    check(u"Math.ceil 返回整数", lang.Math.ceil(2.1) == 3
          and isinstance(lang.Math.ceil(2.1), int))
    check(u"Math.abs", lang.Math.abs(-5) == 5)
    check(u"Math.max/min", lang.Math.max(1, 2) == 2 and lang.Math.min(1, 2) == 1)
    check(u"Math.floorDiv 向下取整", lang.Math.floorDiv(-7, 2) == -4,
          lang.Math.floorDiv(-7, 2))
    check(u"Math.floorMod", lang.Math.floorMod(-7, 2) == 1)
    check(u"floorDiv 除零抛 ArithmeticException", raises(lang.Math.floorDiv, 1, 0))
    check(u"Math.sqrt", lang.Math.sqrt(9.0) == 3.0)
    check(u"Math.pow", lang.Math.pow(2, 10) == 1024.0)
    check(u"Math.signum", lang.Math.signum(-3) == -1.0)
    check(u"Math.toRadians", abs(lang.Math.toRadians(180) - lang.Math.PI) < 1e-9)
    check(u"Math.random 返回浮点", isinstance(lang.Math.random(), float))

    # ------------------------------------------------------------
    section("ThreadLocal / Runnable / Enum / Object / System")
    # ------------------------------------------------------------
    local = lang.ThreadLocal()
    check(u"ThreadLocal 初始为 None", local.get() is None)
    local.set(u"v")
    check(u"ThreadLocal 取值", local.get() == u"v")
    local.remove()
    check(u"ThreadLocal remove 后为 None", local.get() is None)
    check(u"ThreadLocal getOrCreate", local.getOrCreate(lambda: u"made") == u"made")
    check(u"getOrCreate 二次复用", local.getOrCreate(lambda: u"other") == u"made")

    calls = []
    runnable = lang.Runnable(lambda: calls.append(1))
    runnable.run()
    check(u"Runnable 执行", calls == [1])
    check(u"Runnable 可调用", callable(runnable))
    check(u"空 Runnable 抛异常", raises(lang.Runnable().run))

    class Size(lang.Enum):
        pass

    small = Size()
    small._name = u"SMALL"
    small._ordinal = 0
    large = Size()
    large._name = u"LARGE"
    large._ordinal = 1
    Size._values = (small, large)

    check(u"Enum.name", small.name() == u"SMALL")
    check(u"Enum.ordinal", large.ordinal() == 1)
    check(u"Enum.values", len(Size.values()) == 2)
    check(u"Enum.valueOf", Size.valueOf(u"LARGE") is large)
    check(u"Enum.valueOf 未命中抛异常", raises(Size.valueOf, u"NOPE"))
    check(u"Enum 按身份比较", (small == small) is True and (small == large) is False)
    check(u"Enum.compareTo", large.compareTo(small) == 1)
    check(u"Enum.toString", small.toString() == u"SMALL")

    obj = lang.Object()
    check(u"Object.equals 是身份比较", obj.equals(obj) is True)
    check(u"Object.getClass", obj.getClass() is lang.Object)
    check(u"Object.toString 非空", len(obj.toString()) > 0)
    check(u"Object.hashCode 稳定", obj.hashCode() == obj.hashCode())

    check(u"System.currentTimeMillis 是整数",
          isinstance(lang.System.currentTimeMillis(), int))
    check(u"System.nanoTime 是整数", isinstance(lang.System.nanoTime(), int))
    check(u"System.identityHashCode", lang.System.identityHashCode(obj) == obj.hashCode() and -2147483648 <= obj.hashCode() <= 2147483647)
    check(u"System.lineSeparator", lang.System.lineSeparator() == u"\n")
    check(u"System.getProperty 返回默认值",
          lang.System.getProperty(u"any", u"d") == u"d")

    src = [1, 2, 3, 4]
    dest = [0, 0, 0, 0]
    lang.System.arraycopy(src, 1, dest, 0, 2)
    check(u"System.arraycopy", dest == [2, 3, 0, 0], dest)

    # ------------------------------------------------------------
    section("JAVA_MAP 覆盖率（对照真实模组引用）")
    # ------------------------------------------------------------
    expected = [
        "java.lang.String", "java.lang.StringBuilder", "java.lang.Integer",
        "java.lang.Boolean", "java.lang.Math", "java.lang.Float",
        "java.lang.Comparable", "java.lang.Enum", "java.lang.Runnable",
        "java.lang.System", "java.lang.ThreadLocal", "java.lang.Object",
        "java.lang.Long", "java.lang.Double", "java.lang.Character",
        "java.lang.Byte", "java.lang.Short", "java.lang.Number",
        "java.lang.Exception", "java.lang.Throwable",
        "java.lang.IllegalStateException", "java.lang.IllegalArgumentException",
        "java.lang.AssertionError", "java.lang.RuntimeException",
    ]
    missing = [name for name in expected if name not in lang.JAVA_MAP]
    check(u"已实现的 java.lang 类型全部在映射表里", missing == [], missing)
    check(u"映射表条目数 >= 25", len(lang.JAVA_MAP) >= 25, len(lang.JAVA_MAP))

    smoke_args = {
        String: (), StringBuilder: (), lang.Integer: (0,), lang.Long: (0,),
        lang.Float: (0.0,), lang.Double: (0.0,), lang.Boolean: (False,),
        lang.Byte: (0,), lang.Short: (0,), lang.Character: (u"a",),
        lang.Math: (), lang.Object: (), lang.System: (),
        lang.ThreadLocal: (), lang.Runnable: (), lang.Comparable: (),
        lang.Enum: (), lang.Number: (), JavaString: (u"",),
    }
    failures = []
    for java_name, impl in lang.JAVA_MAP.items():
        if not isinstance(impl, type):
            failures.append(u"{}: 映射目标不是类".format(java_name))
            continue
        args = smoke_args.get(impl, ())
        try:
            impl(*args)
        except Exception as error:
            failures.append(u"{}: {}".format(java_name, error))
    check(u"映射的类都能构造实例（冒烟）", failures == [], failures)

    # ------------------------------------------------------------
    section("回归：静态方法与实例方法不能同名（Python 无重载）")
    # ------------------------------------------------------------
    # 真实踩过的坑：
    #   Java 允许 Integer.toString(int, int) 与实例的 toString() 并存，
    #   Python 不行 —— 后定义的实例方法会**覆盖**静态方法，
    #   于是 Boolean.toString(True) 走进了实例方法，报「bool 没有 _value」。
    # 约定：Java 里同时存在两种形态时，静态入口用不冲突的名字
    #       （toStringRadix / toStringValue / hashCodeValue），
    #       实例方法委托给它，两边共用一份逻辑。
    check(u"Integer 静态进制入口叫 toStringRadix",
          hasattr(Integer, "toStringRadix"))
    check(u"Integer(7).toString() 仍可用", Integer(7).toString() == u"7")
    check(u"Boolean 静态入口叫 toStringValue",
          hasattr(lang.Boolean, "toStringValue"))
    check(u"Boolean 静态入口可不传实例调用",
          lang.Boolean.toStringValue(False) == u"false")
    check(u"Boolean 静态入口接受实例",
          lang.Boolean.toStringValue(lang.Boolean(True)) == u"true")
    check(u"Boolean.hashCodeValue 可直接调用",
          lang.Boolean.hashCodeValue(True) == 1231)
    check(u"Boolean 实例 toString 与静态入口结果一致",
          lang.Boolean(True).toString() == lang.Boolean.toStringValue(True))

    # 逐个确认「静态入口」在传原始值时不会去找实例属性
    for label, call in (
        ("Integer.toStringRadix", lambda: Integer.toStringRadix(255, 16)),
        ("Boolean.toStringValue", lambda: lang.Boolean.toStringValue(True)),
        ("Boolean.hashCodeValue", lambda: lang.Boolean.hashCodeValue(False)),
    ):
        try:
            call()
            check(u"{} 传原始值不报错".format(label), True)
        except Exception as error:
            check(u"{} 传原始值不报错".format(label), False,
                  u"{}: {}".format(type(error).__name__, error))

    # Java 里这些 toString 是静态的，本层用不冲突的名字暴露静态入口
    check(u"Long.toStringValue 静态可用（传原始值）",
          lang.Long.toStringValue(42) == u"42", lang.Long.toStringValue(42))
    check(u"Long.toStringValue 也接受实例",
          lang.Long.toStringValue(lang.Long(7)) == u"7")
    check(u"Double.toStringValue 静态可用",
          lang.Double.toStringValue(1.5) == u"1.5",
          lang.Double.toStringValue(1.5))
    check(u"Double 实例 toString 与静态入口一致",
          lang.Double(2.0).toString() == lang.Double.toStringValue(2.0))
    check(u"Character.toStringValue 静态可用",
          lang.Character.toStringValue(u"x") == u"x")
    check(u"Character 实例 toString 可用",
          lang.Character(u"y").toString() == u"y")

finally:
    pass

sys.exit(summary())
