# NeoCore 0.9.1 兼容性分析器

这是独立开发工具。生产核心、翻译器、API、守卫和游戏包继续使用冻结的 **0.9.0**；0.9.1 不靠增加 API 提高转换率。

## 运行

核心分析代码只使用 Python 标准库（3.11+）。本机完整流程验证环境为 Windows x64、`F:\python.exe` 3.14.3、JDK 21.0.10。CFR 对照明确通过子进程使用冻结 0.9.0 的 tree-sitter 解析器及其二进制扩展，需要兼容解释器；没有把任何分析模块装进游戏 Scripts，也没有执行输入模组 JAR。

```powershell
F:\python.exe -B D:\NeoCore工具\dev\tools\compat_analyzer_091\cli.py --version
F:\python.exe -B D:\NeoCore工具\dev\tools\compat_analyzer_091\cli.py lock-default F:\分析\versions.lock.json
F:\python.exe -B D:\NeoCore工具\dev\tools\compat_analyzer_091\cli.py verify F:\分析\versions.lock.json
F:\python.exe -B D:\NeoCore工具\dev\tools\compat_analyzer_091\cli.py analyze F:\分析\versions.lock.json F:\分析\新结果目录
F:\python.exe -B D:\NeoCore工具\dev\tools\compat_analyzer_091\tests.py
```

先创建锁文件的父目录。锁文件和结果目录存在时拒绝覆盖，不静默重新设定基线。`lock-default` 是本项目 0.9.0/砧板的本机配置生成器，固定 MC1.21.1、NeoForge21.1.233、FML4.0.42；换目标版本需要新的明确 profile，不能把 main 源码塞进旧 profile。

移机时应保持原文件字节，显式调整锁里的路径，并重新生成运行清单。来源哈希、固定版本二进制和 0.9.0 封存包的核对不能关闭。缺文件、错误哈希、损坏 class、解析失败、目标版本错误、CFR 对照失败、工具源码或锁在分析期间变化，均失败并退出非零，不输出通过状态。

## 输出

- `official_abi.json.gz`：完整所选 ABI，类、字段、精确 descriptor、泛型 signature、继承、访问标志、常量、record 组件、来源版本和哈希。Minecraft 补丁类覆盖基础类，其他异字节重复类标记歧义；不默默取第一个。
- `analysis.json`：所有 class 事实、符号引用、字节码调用位置/行号、invokedynamic/bootstrap handle、CFR 对照、逐文件阻断图、依赖边、潜在环、AT/服务声明和未知项。
- `ranking.json`：候选修复及成员范围、影响文件、成本估计、单项情景与贪心修复集合。
- `report.html`：可直接离线打开的静态报告，所有模组文本转义，无网络脚本。
- `versions.lock.json`、`run_manifest.json`：输入、生产保护清单、工具/解释器版本、源码与结果 SHA、完成或失败状态。

索引来源是版本匹配的 class 二进制，不使用未锁定的 FancyModLoader-main。Curios 作为匹配版本的**分析 ABI**独立索引，未提供 Python 实现，也不进入核心；没有验证到目标 JEI 时保留 `UNRESOLVED_VERSION`，不拿其他 MC/平台的包代替。JDK 仅索引锁中列出的模块。内嵌 JAR 不自动成为 classpath 提供者，需要独立锁定其版本；缺参考类/祖先时返回 UNKNOWN，不断言官方 API 不存在。

## 如何读“阻断”

1. `MEASURED_DIAGNOSTIC` 是 0.9.0 后台已经实际报出的诊断，原行完整保留。
2. `STATIC_REQUIREMENT` 等条目来自所有 class 引用、参考 ABI 和冻结导出表，反映其他已见需求。它们可能在可选、客户端或不可达代码里，不能当成已发生的执行失败。
3. 参考 ABI 的 `FOUND` 只说明正确版本里有该声明，不表示 NeoCore 有相同行为。
4. `NO_EXPORTED_PROVIDER` 证明没有登记的生产导出，并不证明仓库里不存在任何未导出代码。已有实现的行为仍为 UNVERIFIED。
5. Python 方法明确 NotImplementedError 且官方方法非 abstract 时才提出具体未实现行为线索。合法的 UnsupportedOperationException、抽象方法本身不自动算缺陷。
6. 98 个人工文件都保留“编译器停在首诊断，后续语义阻断未探索”的未知边界。15 个生成文件的缺依赖边保持真实报告原状。

反射、动态分派、side/config 条件和完整执行可达性没有被证明。字段名的静态出现不是所有构造路径都赋值的证明；Python 没有 private 也不能替代 AT 字段与行为校验。

## 排序的含义

候选集合按测得诊断覆盖、静态需求覆盖和依赖闭包排序，成本是启发式单位，并按所涉成员数调整。算法为确定性贪心，不保证全局最优。

“仅诊断情景”假设所选修复正确且没有未知后续编译错误；“全部已见需求清除”还要求所见静态需求全部消除。二者都是图上的条件推演。`scenario_generation_range` 的下界为 0，范围不是数学保证边界，`measured_new_generated=null`、`measurement_performed=false`。不能把情景上界写成新转换率。

依赖环不会因为闭包迭代而自动消失。第三方依赖候选不会被排进核心实现队列；JVM/ASM 或已跳过可选插件也不作为默认 0.9.2 核心修复。它们仍在完整报告中，不会为了指标被删去。

## 验收与回滚

`checks/acceptance.py <证据根>` 核对两次完整分析的字节一致性、98/15 文件、191/130 class/CFR、真实后台重跑和下载 ZIP 差异。`checks/python2_smoke.py <证据根>` 单独在真实 Python 2 加载冻结核心及重跑生成的两个配置类，验证加载/重载，确保不导入分析器。集成检查使用此任务记录的 `final_b`/`final_c`、replay 文件；先按发行报告复现相应数据目录。

本工具不覆盖 0.9.0，停止使用独立工具即可回到原流程；完整 0.9.0 ZIP、源码/核心 ZIP 和 Git bundle 保持原字节。不要用本分析包替换游戏核心，也不要自动删除其他 AI 的工作。分析结果不是网易加载/玩法验收。
