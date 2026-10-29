# -*- coding: utf-8 -*-
"""
Σ 层自测：java_stdlib/_base.py + java_stdlib/util.py

为什么这些代码值得逐条测：
    预翻译后的模组代码里写的是 Java 的调用方式（list.get / map.put /
    optional.isPresent），如果这些方法的语义与 java.util 不一致，
    模组的行为就会在很隐蔽的地方出错 —— 例如 Java 的 remove(int)
    和 remove(Object) 是同一个方法名，搞错了会删掉错误的元素。

验证点：
  1. List：get/set/add 重载/remove 重载/indexOf/subList/排序/相等/迭代器
  2. Map：put 返回旧值 / get / getOrDefault / computeIfAbsent / 三种视图
  3. Set：add 返回是否新增、保持插入顺序、按内容判等
  4. Optional / OptionalInt：空值必须抛异常而不是静默返回 None
  5. Objects / Arrays / Collections / UUID / Random / Stream
  6. Java 相等与哈希语义（相等对象必须在 Map 里落到同一个键）
  7. JAVA_MAP 名称映射表覆盖真实模组引用到的类
  8. Python 侧别名（len / 索引 / for 遍历）也能用
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Package, section, check, summary  # noqa: E402

pkg = Package()
util = pkg.load("java_stdlib.util")
base = pkg.load("java_stdlib._base")

JavaList = util.JavaList
JavaMap = util.JavaMap
JavaSet = util.JavaSet
JavaOptional = util.JavaOptional


def raises(func, *args, **kwargs):
    """调用后是否抛异常。"""
    try:
        func(*args, **kwargs)
        return False
    except Exception:
        return True


try:
    # ------------------------------------------------------------
    section("List：读取与越界")
    # ------------------------------------------------------------
    items = JavaList([10, 20, 30])
    check(u"size()", items.size() == 3, items.size())
    check(u"isEmpty() 为假", items.isEmpty() is False)
    check(u"get(0)", items.get(0) == 10, items.get(0))
    check(u"get(2)", items.get(2) == 30, items.get(2))
    check(u"越界 get 抛异常", raises(items.get, 3))
    check(u"负数下标抛异常", raises(items.get, -1))
    check(u"indexOf 命中", items.indexOf(20) == 1, items.indexOf(20))
    check(u"indexOf 未命中返回 -1", items.indexOf(99) == -1, items.indexOf(99))
    check(u"lastIndexOf", JavaList([1, 2, 1]).lastIndexOf(1) == 2)

    # ------------------------------------------------------------
    section("List：add 与 set 的重载语义")
    # ------------------------------------------------------------
    single = JavaList()
    check(u"add(e) 返回 True", single.add(u"a") is True)
    single.add(u"b")
    check(u"顺序追加", list(single.toArray()) == [u"a", u"b"], single.toArray())

    check(u"add(index, e) 插入到指定位置", single.add(1, u"x") is None)
    check(u"插入结果正确", list(single.toArray()) == [u"a", u"x", u"b"], single.toArray())
    check(u"add 到 size() 位置等于追加", single.add(3, u"z") is None)
    check(u"追加结果正确",
          list(single.toArray()) == [u"a", u"x", u"b", u"z"], single.toArray())
    check(u"add 越界抛异常", raises(single.add, 99, u"bad"))

    replaced = JavaList([1, 2, 3])
    old_value = replaced.set(1, 9)
    check(u"set 返回旧值", old_value == 2, old_value)
    check(u"set 后新值生效", replaced.get(1) == 9, replaced.get(1))

    # ------------------------------------------------------------
    section("List：remove 的两个重载（最容易搞错的地方）")
    # ------------------------------------------------------------
    by_index = JavaList([u"a", u"b", u"c"])
    removed = by_index.remove(1)
    check(u"remove(int) 返回被删元素", removed == u"b", removed)
    check(u"remove(int) 后剩两个", list(by_index.toArray()) == [u"a", u"c"], by_index.toArray())

    by_value = JavaList([u"a", u"b", u"c"])
    check(u"remove(Object) 返回 True", by_value.remove(u"b") is True)
    check(u"remove(Object) 后剩两个",
          list(by_value.toArray()) == [u"a", u"c"], by_value.toArray())
    check(u"remove(Object) 未命中返回 False", by_value.remove(u"zzz") is False)
    check(u"remove(Object) 未命中不改动",
          list(by_value.toArray()) == [u"a", u"c"], by_value.toArray())

    check(u"布尔值不被误当作下标", JavaList([True, False]).remove(True) is True)

    # ------------------------------------------------------------
    section("List：视图、排序与相等")
    # ------------------------------------------------------------
    source = JavaList([1, 2, 3, 4, 5])
    sub = source.subList(1, 3)
    check(u"subList 左闭右开", list(sub.toArray()) == [2, 3], sub.toArray())
    check(u"subList 与原列表共享元素",
          (sub.set(0, 99), source.get(1) == 99)[1], source.toArray())
    check(u"subList 区间非法抛异常", raises(source.subList, 3, 1))

    unsorted = JavaList([3, 1, 2])
    unsorted.sort()
    check(u"sort 无参排序", list(unsorted.toArray()) == [1, 2, 3], unsorted.toArray())

    desc = JavaList([1, 3, 2])
    desc.sort(lambda a, b: b - a)
    check(u"sort 用 Comparator 降序", list(desc.toArray()) == [3, 2, 1], desc.toArray())

    reversed_list = JavaList([1, 2, 3])
    reversed_list.reverse()
    check(u"reverse", list(reversed_list.toArray()) == [3, 2, 1], reversed_list.toArray())

    check(u"内容相等即 equals", JavaList([1, 2]).equals(JavaList([1, 2])) is True)
    check(u"顺序不同不相等", JavaList([1, 2]).equals(JavaList([2, 1])) is False)
    check(u"长度不同不相等", JavaList([1]).equals(JavaList([1, 2])) is False)
    check(u"与 Python list 也能比较", JavaList([1, 2]).equals([1, 2]) is True)
    check(u"相等对象 hashCode 相同",
          JavaList([1, 2]).hashCode() == JavaList([1, 2]).hashCode())
    check(u"toString 形如 Java", JavaList([1, None, True]).toString() == u"[1, null, true]",
          JavaList([1, None, True]).toString())

    # ------------------------------------------------------------
    section("List：迭代器（Java 的 hasNext/next）")
    # ------------------------------------------------------------
    it = JavaList([u"a", u"b"]).iterator()
    check(u"hasNext 初始为真", it.hasNext() is True)
    first = it.next()
    check(u"next 取第一个", first == u"a", first)
    check(u"再 hasNext 仍为真", it.hasNext() is True)
    it.next()
    check(u"取完后 hasNext 为假", it.hasNext() is False)
    check(u"越界 next 抛异常", raises(it.next))
    check(u"未 next 就 remove 抛异常", raises(JavaList([1]).iterator().remove))

    removable = JavaList([1, 2, 3]).iterator()
    removable.next()
    removable.remove()
    check(u"Iterator.remove 删掉刚返回的元素",
          list(removable) == [2, 3], list(removable))

    # ------------------------------------------------------------
    section("List：Python 侧别名")
    # ------------------------------------------------------------
    py_list = JavaList([1, 2, 3])
    check(u"len() 可用", len(py_list) == 3, len(py_list))
    check(u"下标取值可用", py_list[0] == 1)
    check(u"for 遍历可用", [x for x in py_list] == [1, 2, 3])
    check(u"in 判断可用", 2 in py_list)
    check(u"切片返回 JavaList", isinstance(py_list[0:2], JavaList))
    check(u"非空对象真值为真", bool(py_list) is True)
    check(u"空对象真值为假", bool(JavaList()) is False)

    # ------------------------------------------------------------
    section("Map：基本操作与空值语义")
    # ------------------------------------------------------------
    m = JavaMap()
    check(u"put 新键返回 None", m.put(u"a", 1) is None, m.put(u"a", 1))
    check(u"size", m.size() == 1, m.size())
    check(u"get 命中", m.get(u"a") == 1, m.get(u"a"))
    check(u"get 未命中返回 None", m.get(u"zzz") is None)
    check(u"put 覆盖返回旧值", m.put(u"a", 2) == 1, m.put(u"a", 2))
    check(u"覆盖后取值更新", m.get(u"a") == 2, m.get(u"a"))

    m.put(u"nullKey", None)
    check(u"允许 null 值", m.get(u"nullKey") is None)
    check(u"null 值的键仍然存在", m.containsKey(u"nullKey") is True)
    check(u"不存在的键 containsKey 为假", m.containsKey(u"nope") is False)

    check(u"getOrDefault 命中", m.getOrDefault(u"a", 99) == 2, m.getOrDefault(u"a", 99))
    check(u"getOrDefault 未命中", m.getOrDefault(u"nope", 99) == 99)

    check(u"containsValue 命中", m.containsValue(2) is True)
    check(u"containsValue 未命中", m.containsValue(12345) is False)

    check(u"remove 返回被删值", m.remove(u"a") == 2, m.remove(u"a"))
    check(u"remove 后查不到", m.containsKey(u"a") is False)

    # ------------------------------------------------------------
    section("Map：putIfAbsent / computeIfAbsent")
    # ------------------------------------------------------------
    cache = JavaMap()
    check(u"computeIfAbsent 首次创建", cache.computeIfAbsent(u"k", lambda k: 42) == 42)
    check(u"computeIfAbsent 二次复用",
          cache.computeIfAbsent(u"k", lambda k: 99) == 42,
          cache.get(u"k"))
    check(u"computeIfAbsent 对 null 值重新计算",
          (cache.put(u"n", None),
           cache.computeIfAbsent(u"n", lambda k: u"filled"))[1] == u"filled",
          cache.get(u"n"))

    absent = JavaMap()
    check(u"putIfAbsent 空位写入返回 None", absent.putIfAbsent(u"a", 1) is None)
    check(u"putIfAbsent 已存在返回旧值", absent.putIfAbsent(u"a", 2) == 1)

    # ------------------------------------------------------------
    section("Map：三种视图与插入顺序")
    # ------------------------------------------------------------
    ordered = JavaMap()
    for key in (u"z", u"a", u"m"):
        ordered.put(key, key.upper())

    check(u"keySet 保持插入顺序",
          list(ordered.keySet().toArray()) == [u"z", u"a", u"m"],
          ordered.keySet().toArray())
    check(u"values 保持插入顺序",
          list(ordered.values().toArray()) == [u"Z", u"A", u"M"],
          ordered.values().toArray())
    check(u"entrySet 保持插入顺序",
          [e.getKey() for e in ordered.entrySet()] == [u"z", u"a", u"m"],
          [e.getKey() for e in ordered.entrySet()])

    entry = ordered.entrySet().toArray()[0]
    check(u"MapEntry.getKey/getValue",
          entry.getKey() == u"z" and entry.getValue() == u"Z",
          (entry.getKey(), entry.getValue()))
    check(u"MapEntry 可解包", tuple(entry) == (u"z", u"Z"), tuple(entry))
    check(u"MapEntry.setValue 返回旧值", entry.setValue(u"new") == u"Z")

    check(u"toString 形如 Java", JavaMap({u"a": 1}).toString() == u"{a=1}",
          JavaMap({u"a": 1}).toString())
    check(u"equals 按内容", JavaMap({u"a": 1}).equals(JavaMap({u"a": 1})) is True)
    check(u"equals 值不同则为假", JavaMap({u"a": 1}).equals(JavaMap({u"a": 2})) is False)
    check(u"相等 Map hashCode 相同",
          JavaMap({u"a": 1}).hashCode() == JavaMap({u"a": 1}).hashCode())

    # ------------------------------------------------------------
    section("Set：唯一性与顺序")
    # ------------------------------------------------------------
    s = JavaSet()
    check(u"add 首次返回 True", s.add(u"a") is True)
    check(u"add 重复返回 False", s.add(u"a") is False)
    check(u"size 不重复计数", s.size() == 1, s.size())
    s.add(u"b")
    check(u"保持插入顺序", list(s.toArray()) == [u"a", u"b"], s.toArray())
    check(u"contains 命中", s.contains(u"a") is True)
    check(u"remove 命中返回 True", s.remove(u"a") is True)
    check(u"remove 未命中返回 False", s.remove(u"zzz") is False)

    check(u"equals 按内容", JavaSet([u"a", u"b"]).equals(JavaSet([u"b", u"a"])) is True)
    check(u"元素不同则不等", JavaSet([u"a"]).equals(JavaSet([u"b"])) is False)

    # ------------------------------------------------------------
    section("回归：entrySet 不能把不同 Entry 去重掉")
    # ------------------------------------------------------------
    # 真实 bug：MapEntry.hashCode 是 key ^ value，
    # 对 "z"/"Z"、"a"/"A" 这类键值，异或结果都是 0，
    # 于是三条不同 Entry 撞成同一个键，entrySet() 只剩一条。
    regression = JavaMap()
    for key in (u"z", u"a", u"m"):
        regression.put(key, key.upper())

    entries = regression.entrySet()
    check(u"entrySet 条数等于 Map 大小", entries.size() == 3,
          u"{} vs {}".format(entries.size(), regression.size()))

    entry_keys = set([e.getKey() for e in entries])
    check(u"三个 Entry 的键都在",
          entry_keys == set([u"z", u"a", u"m"]), entry_keys)

    # Entry 之间必须能区分内容
    e1 = util.MapEntry(u"z", u"Z")
    e2 = util.MapEntry(u"a", u"A")
    check(u"不同内容的 Entry 不相等", e1.equals(e2) is False)
    check(u"内容相同的 Entry 相等",
          e1.equals(util.MapEntry(u"z", u"Z")) is True)
    check(u"Entry 进 Set 不会互相覆盖",
          JavaSet([e1, e2, util.MapEntry(u"m", u"M")]).size() == 3,
          JavaSet([e1, e2, util.MapEntry(u"m", u"M")]).size())

    # 嵌套集合当键也要能区分
    nested = JavaMap()
    nested.put(JavaList([1, 2]), u"a")
    nested.put(JavaList([3, 4]), u"b")
    check(u"嵌套 List 作键不互相覆盖", nested.size() == 2, nested.size())
    check(u"嵌套 List 键取值正确",
          nested.get(JavaList([3, 4])) == u"b", nested.get(JavaList([3, 4])))

    # ------------------------------------------------------------
    section("Java 相等语义：相等对象必须落到同一个键")
    # ------------------------------------------------------------
    # 这是复刻 Java 语义最难的一点：Python 默认按身份哈希，Java 按内容
    keyed = JavaMap()
    keyed.put(JavaList([1, 2]), u"list-value")
    check(u"内容相同的 List 能取回同一个值",
          keyed.get(JavaList([1, 2])) == u"list-value",
          keyed.get(JavaList([1, 2])))

    set_keyed = JavaSet()
    set_keyed.add(JavaList([1]))
    set_keyed.add(JavaList([1]))
    check(u"内容相同的 List 在 Set 里只算一个", set_keyed.size() == 1, set_keyed.size())

    check(u"equals 处理 None", base.equals(None, None) is True)
    check(u"equals 一空一实为假", base.equals(None, 1) is False)
    check(u"hash_code(None) 为 0", base.hash_code(None) == 0, base.hash_code(None))
    check(u"hash_code 相等对象一致",
          base.hash_code(JavaList([1])) == base.hash_code(JavaList([1])))

    # ------------------------------------------------------------
    section("Optional：空值必须抛异常")
    # ------------------------------------------------------------
    present = JavaOptional.of(u"v")
    check(u"of 后 isPresent", present.isPresent() is True)
    check(u"get 取值", present.get() == u"v", present.get())
    check(u"orElse 返回原值", present.orElse(u"other") == u"v")

    empty = JavaOptional.empty()
    check(u"empty 后 isEmpty", empty.isEmpty() is True)
    check(u"空 Optional 取值抛异常", raises(empty.get))
    check(u"空 Optional orElse 返回替代值", empty.orElse(u"other") == u"other",
          empty.orElse(u"other"))
    check(u"空 Optional orElseGet 调用 supplier",
          empty.orElseGet(lambda: u"made") == u"made")
    check(u"空 Optional orElseThrow 抛异常", raises(empty.orElseThrow))
    check(u"of(None) 抛异常", raises(JavaOptional.of, None))
    check(u"ofNullable(None) 得到空", JavaOptional.ofNullable(None).isPresent() is False)

    captured = []
    JavaOptional.of(5).ifPresent(captured.append)
    check(u"ifPresent 对非空执行", captured == [5], captured)
    missed = []
    JavaOptional.empty().ifPresent(missed.append)
    check(u"ifPresent 对空不执行", missed == [], missed)

    check(u"map 转换", JavaOptional.of(3).map(lambda x: x * 2).get() == 6)
    check(u"空 Optional map 仍为空", JavaOptional.empty().map(lambda x: x).isPresent() is False)
    check(u"filter 命中保留", JavaOptional.of(4).filter(lambda x: x > 2).isPresent() is True)
    check(u"filter 未命中变空", JavaOptional.of(1).filter(lambda x: x > 2).isPresent() is False)
    check(u"orNull 便利方法", JavaOptional.empty().orNull() is None)
    check(u"toString 空值形态", JavaOptional.empty().toString() == u"Optional.empty",
          JavaOptional.empty().toString())

    opt_int = util.JavaOptionalInt.of(0)
    check(u"OptionalInt 的 0 是合法值", opt_int.isPresent() is True)
    check(u"OptionalInt.getAsInt", opt_int.getAsInt() == 0)
    check(u"OptionalInt.empty 取值抛异常",
          raises(util.JavaOptionalInt.empty().getAsInt))

    # ------------------------------------------------------------
    section("Objects / Arrays / Collections")
    # ------------------------------------------------------------
    check(u"Objects.isNull", util.Objects.isNull(None) is True)
    check(u"Objects.nonNull", util.Objects.nonNull(0) is True)
    check(u"Objects.equals", util.Objects.equals(u"a", u"a") is True)
    check(u"Objects.requireNonNull 非空放行",
          util.Objects.requireNonNull(u"x") == u"x")
    check(u"Objects.requireNonNull 空值抛异常",
          raises(util.Objects.requireNonNull, None))
    check(u"Objects.toString(null) 返回默认值",
          util.Objects.toString(None, u"-") == u"-")
    check(u"Objects.compare", util.Objects.compare(1, 2) == -1, util.Objects.compare(1, 2))

    check(u"Arrays.asList 多参", list(util.Arrays.asList(1, 2, 3).toArray()) == [1, 2, 3])
    check(u"Arrays.asList 传数组",
          list(util.Arrays.asList([1, 2]).toArray()) == [1, 2],
          util.Arrays.asList([1, 2]).toArray())
    check(u"Arrays.asList 传 JavaList",
          list(util.Arrays.asList(JavaList([7, 8])).toArray()) == [7, 8],
          util.Arrays.asList(JavaList([7, 8])).toArray())
    check(u"Arrays.copyOf 截断", list(util.Arrays.copyOf([1, 2, 3], 2).toArray()) == [1, 2])
    check(u"Arrays.copyOf 补 null",
          list(util.Arrays.copyOf([1], 3).toArray()) == [1, None, None],
          util.Arrays.copyOf([1], 3).toArray())

    # 这三个来自真实模组反编译源码的使用统计（copyOfRange 3 次、equals 1 次）
    check(u"Arrays.copyOfRange 左闭右开",
          list(util.Arrays.copyOfRange([1, 2, 3, 4], 1, 3).toArray()) == [2, 3],
          util.Arrays.copyOfRange([1, 2, 3, 4], 1, 3).toArray())
    check(u"Arrays.copyOfRange 超长补 null",
          list(util.Arrays.copyOfRange([1], 0, 3).toArray()) == [1, None, None],
          util.Arrays.copyOfRange([1], 0, 3).toArray())
    check(u"Arrays.copyOfRange 起点越界抛异常",
          raises(util.Arrays.copyOfRange, [1], 5, 6))
    check(u"Arrays.copyOfRange 终点小于起点抛异常",
          raises(util.Arrays.copyOfRange, [1, 2], 2, 1))
    check(u"Arrays.equals 按元素比较",
          util.Arrays.equals([1, 2], [1, 2]) is True)
    check(u"Arrays.equals 长度不同为假",
          util.Arrays.equals([1], [1, 2]) is False)
    check(u"Arrays.equals 元素不同为假",
          util.Arrays.equals([1], [2]) is False)

    # Java 9 的静态工厂（List.of 4 次、Set.of 2 次、Map.of 1 次）
    check(u"List.of", list(util.JavaList.of(1, 2, 3).toArray()) == [1, 2, 3],
          util.JavaList.of(1, 2, 3).toArray())
    check(u"List.of 传列表",
          list(util.JavaList.of([1, 2]).toArray()) == [1, 2])
    check(u"Set.of rejects duplicates", raises(util.JavaSet.of, 1, 1, 2))
    check(u"Set.of unique values", util.JavaSet.of(1, 2).size() == 2)
    check(u"Map.of", util.JavaMap.of(u"a", 1, u"b", 2).get(u"b") == 2,
          util.JavaMap.of(u"a", 1, u"b", 2).get(u"b"))
    check(u"Map.of 奇数参数抛异常", raises(util.JavaMap.of, u"a", 1, u"b"))
    check(u"List.copyOf", list(util.JavaList.copyOf([1, 2]).toArray()) == [1, 2])
    check(u"Map.copyOf", util.JavaMap.copyOf({u"a": 1}).get(u"a") == 1)
    check(u"Arrays.toString", util.Arrays.toString([1, None]) == u"[1, null]",
          util.Arrays.toString([1, None]))

    fill_target = JavaList([1, 2])
    util.Arrays.fill(fill_target, 0)
    check(u"Arrays.fill", list(fill_target.toArray()) == [0, 0], fill_target.toArray())

    check(u"Collections.emptyList", util.Collections.emptyList().size() == 0)
    check(u"Collections.singletonList",
          list(util.Collections.singletonList(5).toArray()) == [5])
    check(u"Collections.frequency", util.Collections.frequency([1, 1, 2], 1) == 2,
          util.Collections.frequency([1, 1, 2], 1))
    original = JavaList([3, 1])
    copy_list = util.Collections.unmodifiableList(original)
    check(u"unmodifiableList 拒绝写入", raises(copy_list.set, 0, 9))
    original.set(0, 8)
    check(u"unmodifiableList 是实时只读视图",copy_list.get(0)==8,original.toArray())
    rev = JavaList([1, 2])
    util.Collections.reverse(rev)
    check(u"Collections.reverse", list(rev.toArray()) == [2, 1], rev.toArray())

    # ------------------------------------------------------------
    section("UUID / Random / Stream")
    # ------------------------------------------------------------
    one = util.UUID.fromString(u"ABCD1234-1234-1234-1234-123456789ABC")
    check(u"UUID 小写归一", one.toString() == u"abcd1234-1234-1234-1234-123456789abc", one.toString())
    check(u"UUID 相等", one.equals(util.UUID.fromString(u"abcd1234-1234-1234-1234-123456789abc")) is True)
    check(u"UUID 可直接当字符串用", u"{}".format(one) == u"abcd1234-1234-1234-1234-123456789abc")
    check(u"UUID.randomUUID 形态正确",
          len(util.UUID.randomUUID().toString()) == 36,
          util.UUID.randomUUID().toString())

    seeded_a = util.JavaRandom(12345)
    seeded_b = util.JavaRandom(12345)
    check(u"Random 同种子结果一致",
          seeded_a.nextInt(1000) == seeded_b.nextInt(1000))
    check(u"nextInt(1) 恒为 0", util.JavaRandom(1).nextInt(1) == 0)
    check(u"nextInt(0) 抛异常", raises(util.JavaRandom(1).nextInt, 0))
    check(u"nextDouble 在 [0,1)",
          0.0 <= util.JavaRandom(7).nextDouble() < 1.0)
    check(u"nextBoolean 返回布尔",
          isinstance(util.JavaRandom(3).nextBoolean(), bool))

    stream_result = JavaList([1, 2, 3, 4, 5]).toArray()
    stream = util.JavaStream(stream_result).filter(lambda x: x % 2 == 1).map(lambda x: x * 10)
    check(u"Stream 惰性链 filter+map", list(stream.toList().toArray()) == [10, 30, 50],
          stream.toList().toArray())
    check(u"Stream.count", util.JavaStream([1, 2, 3]).count() == 3)
    check(u"Stream.anyMatch", util.JavaStream([1, 2]).anyMatch(lambda x: x == 2) is True)
    check(u"Stream.allMatch", util.JavaStream([1, 2]).allMatch(lambda x: x > 0) is True)
    check(u"Stream.noneMatch", util.JavaStream([1, 2]).noneMatch(lambda x: x > 9) is True)
    check(u"Stream.sorted", list(util.JavaStream([3, 1, 2]).sorted().toList().toArray()) == [1, 2, 3])
    check(u"Stream.distinct 去重",
          list(util.JavaStream([1, 1, 2]).distinct().toList().toArray()) == [1, 2])
    check(u"Stream.limit", list(util.JavaStream([1, 2, 3]).limit(2).toList().toArray()) == [1, 2])
    check(u"Stream.skip", list(util.JavaStream([1, 2, 3]).skip(1).toList().toArray()) == [2, 3])
    check(u"Stream.findFirst 非空",
          util.JavaStream([9]).findFirst().get() == 9)
    check(u"Stream.findFirst 空流返回空 Optional",
          util.JavaStream([]).findFirst().isPresent() is False)
    check(u"Stream.reduce 带初值",
          util.JavaStream([1, 2, 3]).reduce(0, lambda a, b: a + b) == 6)

    # ------------------------------------------------------------
    section("基座：鸭子类型与构造器注入")
    # ------------------------------------------------------------
    check(u"is_java_collection 认得 JavaList",
          base.is_java_collection(JavaList([1])) is True)
    check(u"is_java_collection 不认普通 list",
          base.is_java_collection([1]) is False)
    check(u"to_python_list 处理 JavaList",
          base.to_python_list(JavaList([1, 2])) == [1, 2])
    check(u"to_python_list 处理普通 list", base.to_python_list([1]) == [1])
    check(u"to_python_list 处理 None", base.to_python_list(None) == [])
    check(u"to_python_list 单值包成列表", base.to_python_list(u"x") == [u"x"])
    check(u"to_java_list 包成 JavaList",
          isinstance(base.to_java_list([1]), JavaList))
    check(u"to_java_list 幂等",
          list(base.to_java_list(JavaList([1])).toArray()) == [1])
    check(u"构造器已注入", base.get_java_list_factory() is JavaList)
    check(u"_base 不再有误导性的 JavaList 占位符",
          not hasattr(base, "JavaList"))

    # ------------------------------------------------------------
    section("JAVA_MAP 名称映射表")
    # ------------------------------------------------------------
    expected_mappings = [
        ("java.util.List", JavaList),
        ("java.util.ArrayList", JavaList),
        ("java.util.LinkedList", JavaList),
        ("java.util.Map", JavaMap),
        ("java.util.HashMap", JavaMap),
        ("java.util.LinkedHashMap", util.JavaLinkedHashMap),
        ("java.util.EnumMap", JavaMap),
        ("java.util.Set", JavaSet),
        ("java.util.HashSet", JavaSet),
        ("java.util.EnumSet", util.EnumSet),
        ("java.util.Optional", JavaOptional),
        ("java.util.OptionalInt", util.JavaOptionalInt),
        ("java.util.Iterator", util.JavaIterator),
        ("java.util.Objects", util.Objects),
        ("java.util.Arrays", util.Arrays),
        ("java.util.Collections", util.Collections),
        ("java.util.UUID", util.UUID),
        ("java.util.Random", util.JavaRandom),
        ("java.util.stream.Stream", util.JavaStream),
    ]
    for java_name, expected in expected_mappings:
        check(u"映射 {} -> {}".format(java_name, expected.__name__),
              util.JAVA_MAP.get(java_name) is expected,
              util.JAVA_MAP.get(java_name))

    check(u"接口名与实现类名都覆盖到",
          len(util.JAVA_MAP) >= 25, len(util.JAVA_MAP))

finally:
    pass

sys.exit(summary())
