# -*- coding: utf-8 -*-
# 未映射api/__init__.py
# ω 层：未映射 API 的兜底处理（包的对外入口）
#
# 这一层回答一个问题：**核心包没实现的 API，遇到了怎么办？**
#
# 三种做法的取舍（详见 fallback.py 的策略表）：
#   raise  立刻暴露，但可能因一个纯视觉方法让整个模组崩掉
#   noop   模组能跑，但会掩盖真问题
#   stub   返回中性替身，让上层逻辑继续走
#
# 结论是**按 API 类别分别定策略**，没有一刀切的答案：
#   注册/数据/网络 → raise（静默失败最可怕）
#   渲染/音效/界面 → noop（只影响观感，不值得崩）
#   翻译           → stub（回退为键本身，界面上看得出问题）
#   拿不准         → warn（记录后继续，但留下痕迹）
#
# 无论哪种策略，**兜底都会留痕** —— 记录进 FallbackStats，
# 由 FallbackLogger 输出成「还缺哪些接口」的待办清单。
#
# 编码约定：只用 Python 2 与 Python 3 语义完全一致的语法。

from __future__ import print_function
from __future__ import absolute_import

from 未映射api.fallback import (  # noqa: F401
    Severity,
    Policy,
    DEFAULT_POLICIES,
    CLASSIFY_RULES,
    classify_api,
    policy_for,
    FallbackStats,
    STATS,
    UnmappedClass,
    FallbackHandler,
    DEFAULT_HANDLER,
    resolve_or_fallback,
)

from 未映射api.logger import (  # noqa: F401
    FallbackLogger,
    SEVERITY_LABELS,
    SEVERITY_ORDER,
)


__all__ = [
    # 策略
    "Severity", "Policy", "DEFAULT_POLICIES", "CLASSIFY_RULES",
    "classify_api", "policy_for",
    # 统计与报告
    "FallbackStats", "STATS", "FallbackLogger",
    "SEVERITY_LABELS", "SEVERITY_ORDER",
    # 替身与处理器
    "UnmappedClass", "FallbackHandler", "DEFAULT_HANDLER",
    "resolve_or_fallback",
]
