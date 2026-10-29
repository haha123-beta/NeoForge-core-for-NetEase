# -*- coding: utf-8 -*-
# 未映射api/logger.py
# ω 层：兜底记录的输出
#
# 为什么单独一个文件：
#   `fallback.py` 负责「怎么处理」，这里负责「怎么让人看见」。
#   真机上模组出问题时，最有用的就是一份能直接读的清单：
#   哪些 API 没实现、各出现了多少次、严重程度如何。
#
#   这份清单同时是**开发待办**：按次数排序就是补齐的优先级。
#   （与 dev/api_coverage.py 的区别：那边是静态分析「还有哪些类没实现」，
#    这里是运行期实测「实际被调用到、但没实现」的，更贴近真实。）
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

try:
    from java_stdlib._base import IllegalArgumentException
    from java_stdlib.lang import java_to_string
except ImportError:
    from _base import IllegalArgumentException  # type: ignore
    from lang import java_to_string  # type: ignore

# 导入同目录的 fallback。
#
# 注意**不要**写成 `from 未映射api.fallback import ...` ——
# 那会把中文目录名当作标识符，而项目约定禁止非 ASCII 标识符
# （Python 2 里很可能直接是语法错误）。
# 用显式相对导入，两个版本都稳。目录名本身是中文不受影响。
from 未映射api.fallback import (  # noqa: E402
    Severity,
    FallbackStats,
    STATS,
)


# 严重程度的中文说明，用于报告
SEVERITY_LABELS = {
    Severity.RAISE: u"严重（会抛异常）",
    Severity.WARN: u"警告",
    Severity.STUB: u"替身",
    Severity.NOOP: u"静默跳过",
    Severity.NULL: u"返回空值",
}

# 按严重程度排序用的权重（越严重越靠前）
SEVERITY_ORDER = {
    Severity.RAISE: 0,
    Severity.WARN: 1,
    Severity.STUB: 2,
    Severity.NOOP: 3,
    Severity.NULL: 4,
}


class FallbackLogger(object):
    """
    收集并输出兜底记录。

    与 FallbackStats 的分工：
      FallbackStats  存原始条目（数据）
      FallbackLogger 决定怎么呈现（视图）
    """

    def __init__(self, stats=None, writer=None):
        self.stats = stats if stats is not None else STATS
        self._writer = writer if writer is not None else (
            lambda text: print(text))
        self.lines = []

    # ---------------- 输出 ----------------

    def emit(self, text):
        self.lines.append(text)
        self._writer(text)
        return None

    def writeReport(self, limit=30):
        """输出完整报告，返回行数。"""
        for line in self.buildReport(limit):
            self.emit(line)
        return len(self.lines)

    def buildReport(self, limit=30):
        """构造报告行（不打印，便于自测断言）。"""
        lines = []
        lines.append(u"=" * 60)
        lines.append(u"未映射 API 报告")
        lines.append(u"=" * 60)

        if self.stats.isClean():
            lines.append(u"没有走到任何兜底 —— 本次运行覆盖完整。")
            return lines

        lines.append(u"共 {} 次调用没有实现".format(self.stats.count()))
        lines.append(u"")

        # 按严重程度分组
        grouped = {}
        for java_name, member, severity, _category in self.stats.entries:
            key = severity or Severity.NULL
            grouped.setdefault(key, []).append((java_name, member))

        for severity in sorted(grouped, key=lambda s: SEVERITY_ORDER.get(s, 9)):
            items = grouped[severity]
            label = SEVERITY_LABELS.get(severity, java_to_string(severity))
            lines.append(u"--- {} （{} 次）---".format(label, len(items)))
            for java_name, member in items[:limit]:
                if member:
                    lines.append(u"    {}.{}".format(java_name, member))
                else:
                    lines.append(u"    {}".format(java_name))
            if len(items) > limit:
                lines.append(u"    …还有 {} 条".format(len(items) - limit))
            lines.append(u"")

        # 待办：按次数排序
        lines.append(u"--- 补齐优先级（按实际调用次数）---")
        ordered = sorted(self.stats.byJavaName().items(),
                         key=lambda item: (-item[1], item[0]))
        for java_name, times in ordered[:limit]:
            lines.append(u"    {:>4} 次  {}".format(times, java_name))
        if len(ordered) > limit:
            lines.append(u"    …还有 {} 种".format(len(ordered) - limit))

        return lines

    # ---------------- 判定 ----------------

    def hasSevere(self):
        """
        是否存在「严重」级别的兜底。

        真机自检用：有严重级别说明有功能是真的坏了，
        而不仅仅是观感问题。
        """
        for _java_name, _member, severity, _category in self.stats.entries:
            if severity == Severity.RAISE:
                return True
        return False

    def severeNames(self):
        """列出所有严重级别的 Java 名（去重）。"""
        names = []
        for java_name, _member, severity, _category in self.stats.entries:
            if severity == Severity.RAISE and java_name not in names:
                names.append(java_name)
        return names

    def cosmeticCount(self):
        """纯观感问题（渲染/音效）的次数。"""
        total = 0
        for _java_name, _member, severity, _category in self.stats.entries:
            if severity in (Severity.NOOP, Severity.NULL):
                total += 1
        return total

    def summaryLine(self):
        """一行摘要，适合放在启动日志末尾。"""
        if self.stats.isClean():
            return u"未映射 API: 无"
        return u"未映射 API: {} 次（其中观感类 {} 次，严重 {} 次）".format(
            self.stats.count(), self.cosmeticCount(),
            len(self.severeNames()))

    def clear(self):
        self.lines = []
        self.stats.clear()
        return None

    def __repr__(self):
        return u"<FallbackLogger {} 条记录>".format(self.stats.count())


__all__ = ["FallbackLogger", "SEVERITY_LABELS", "SEVERITY_ORDER"]
