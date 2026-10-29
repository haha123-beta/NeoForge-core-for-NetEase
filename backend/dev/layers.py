# -*- coding: utf-8 -*-
"""
layers —— 核心包分层目录的**单一来源**

为什么单独放一个文件：
  这个列表原先在 `run_selftest.py` / `py3only_lint.py` / `whitelist_lint.py`
  里各写了一遍，三份容易漂移。实测已经因此漏检过两次：
    - 第一次：只扫 core/container，漏掉入口 modMain.py，
      里面藏着 3 处 Py2 不兼容的写法（游戏里会加载失败）；
    - 第二次：neoforge/ 写完后没加进来，新代码两处 `except ... as ...` 没被发现。
  每写一层就要改三处，迟早会再漏。所以收成一个常量，三处都从这取。
"""

# 核心包的分层目录（脚本文件夹就是 import 根）
LAYER_DIRS = (
    "core",          # α / γ 层与对外接口
    "container",     # 运行时容器
    "java_stdlib",   # Σ 层：Java 标准库替换
    "neoforge",      # β 层：NeoForge API 映射
    "minecraft",     # θ 层：Minecraft API 映射
    "launcher_skip", # δ 层：启动层跳过
    u"未映射api",     # ω 层：兜底处理
    "shader",        # ζ 层：着色器
)


def describe():
    """返回人类可读的一行说明（供自测输出用）。"""
    return u"、".join(LAYER_DIRS)
