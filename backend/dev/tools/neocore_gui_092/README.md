# NeoCore 0.9.2 转换工具

本目录是0.9.2开发候选，尚未完成最终发行验收；真实模组仍按逐项报告验收，不表示60/130目标完成或网易兼容已验证。发行报告记录本轮回归、后台转换和运行时验证范围。

需要Python3.11+以及backend.json指向的本机dev转换器。Java字节码使用已有JDK/CFR准备源码，不执行输入模组、Mixin插件或ASM transformer；不是免环境EXE。

## 网页使用

双击启动NeoCore.cmd。先导入前置库JAR，将“处理用途”改为“前置库”并转换。ABI和实际生成模块完成后，在消费者模组下勾选该前置库，再开始转换。无需手填ABI路径。

任务保存其采用的依赖快照；前置库后来重新转换不会静默替换已采用的ABI。清单或模块缺失、修改、来源摘要不符、重复版本等会明确报错。只有真实生成且依赖完整的类型可用于ABI解析；必需变换未支持的库不能被标为可用实现。

## 文字后台

```powershell
.\NeoCore文字.cmd start
.\NeoCore文字.cmd convert "F:\测试\前置库.jar" --library
.\NeoCore文字.cmd wait 前置库任务ID
.\NeoCore文字.cmd convert "F:\测试\模组.jar" --dependency 前置库任务ID
.\NeoCore文字.cmd wait 模组任务ID
.\NeoCore文字.cmd report 模组任务ID
.\NeoCore文字.cmd download 模组任务ID "F:\测试\审查结果.zip"
```

多个前置库重复填写--dependency。import只导入；已有任务用export 任务ID --library或export 任务ID --dependency 前置库任务ID重新处理。--json放在命令前用于机器读取。部分转换的wait会以非零状态退出，但仍能report和download审查包。

## 两种ZIP

**源码审查包 SOURCE_REVIEW_ZIP**：部分转换、前置库、纯资源或尚未满足打包条件时提供。包含translated_sources、java_context、content、reports、dependencies及review_manifest.json。实际生成的Python与未转换Java上下文分开；依赖保持独立目录。它不是网易行为包，不能直接作为已兼容模组导入。

**网易测试ZIP NETEASE_TEST_ZIP**：只有已有代码/声明/兼容/入口检查满足时，才走原行为包打包链。仍是待审查产物，打包不等于网易加载或可玩。

网页和CLI都会区分两者，下载和恢复会核对产物摘要。审查包的manifest记录输入JAR摘要和后端源码指纹；不包含原始JAR、class文件或工作区鉴权凭据。

## 非Java内容

Java/code、data JSON、assets/resources、metadata/dependencies、Mixin/AT五路扫描。recipe、tag、loot table、advancement和未知data有逐文件原因和摘要。原始Java版JSON目前主要原样保留，尚未映射成网易格式。无Java时显示“不适用”，不显示空模组0/0。

Extra Recipe固定原JAR含374 data JSON（371recipe、3tag），另3资源和5元数据，共382项；后台可导入并下载保真审查包。服务声明只保留，不执行。含Java的转换目前只接入NeoForge；其他来源的纯资源可保留。

## 本机接口

工作区当前窗口.json含本机URL/token，不要分享。所有/api请求带X-NeoCore-Token。

- GET /api/state：任务、ABI摘要、当前正式版与开发版信息。
- GET /api/job/id：任务状态与产物种类。
- GET /api/report/id：result、source_reports、job_reports、content_reports、dependency_abis完整结果。
- POST /api/import：原JAR字节和URL编码X-Filename。
- POST /api/export：JSON {"id":"任务ID","purpose":"mod或library","dependency_ids":["前置库任务ID"]}。
- GET /download/id：经摘要校验的对应ZIP。
- GET /api/events/id?after=字节游标：最多128条完整事件及下一游标；可断线续读，不推算百分比。
- POST /api/cancel：JSON {"id":"任务ID"}；取消排队或运行任务，回收子进程树。
- GET /api/diagnostic/id：阶段、逐文件、进程资源及错误证据；没有Python产物也可读取。
- GET /diagnostic-download/id：校验任务归属后下载脱敏证据ZIP。
- POST /api/shutdown：仅空闲可退出。

网页、CLI与HTTP共用持久化串行队列。旧版backend.json中的dependency_abis绝对路径仍可使用；不要同时重复选择同一个库。

文字端也可使用 `cancel 任务ID`、`events 任务ID`、`diagnostic 任务ID`。
任务ID可以在刷新后继续查询；状态区分检查、部分生成、失败、超时、取消、审查包以及运行时未验证。
阶段资源指标带有范围：父进程高水位不等于单文件独占峰值，Windows Job提交内存也不等于RSS。
解析采用串行、有界、定期回收的独立工作进程；每次请求核对源码、类型环境与任务上下文摘要。
单任务IR缓存不跨任务复用，缓存失效或超限后仍完整解析。

## 验收边界

已验证编译后的前置库JAR→CFR→ABI→CLI消费者转换→报告/下载→实际Python2运行，并验证漏选依赖和依赖模块篡改。网页也实际验证了勾选依赖、转换成功状态及正确的审查包下载标签。

真实网易独立依赖包链接尚未验收，当前含已翻译依赖的消费者先输出审查包；不会静默合并进核心。必需Mixin/ASM、原生API与复杂语言缺口仍可能阻断。所有engine_verified为false。固定样本计数以本次工具链验证报告为准，不能将工具链联通换算成模组兼容率。
