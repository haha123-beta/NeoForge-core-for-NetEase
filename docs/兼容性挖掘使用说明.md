# NeoCore 0.9.8 兼容性挖掘引擎

工作台左侧“兼容性挖掘”可扫描本机 JAR 目录，查看可搜索、排序的能力排行榜，并下载 A/B/C 任务包。沿用原工作台；CLI 提供完整采样、观察、补丁与前后对比流程。

```powershell
python compatibility_mining.py fetch-modrinth --output corpus --count 100
python compatibility_mining.py scan corpus/jars --output baseline_static --cache cache
python compatibility_mining.py observe baseline_static --backend tools/neocore_gui_092 --output observations
python compatibility_mining.py scan corpus/jars --output baseline --cache cache --reports observations/reports
python compatibility_mining.py propose baseline --output proposal
python compatibility_mining.py validate-patch proposal --apply
python compatibility_mining.py scan corpus/jars --output after_static --cache cache
python compatibility_mining.py observe after_static --backend tools/neocore_gui_092 --output after_observations
python compatibility_mining.py scan corpus/jars --output after --cache cache --reports after_observations/reports
python compatibility_mining.py compare baseline after --output comparison.json
```

命令在 backend/dev 目录执行。每轮使用新的输出目录，旧结果不覆盖。observe 会真正反编译、转换和打包，耗时高于静态扫描；只管理自己启动的后台。外部模组的 class 不被加载执行。生成代码的受控验证使用既有本机 Java 21、真实 Python 2/3 与 SDK 替身，不能代替网易实机验收。

采样通过 [Modrinth 官方搜索接口](https://docs.modrinth.com/api/operations/searchprojects/) 和[版本接口](https://docs.modrinth.com/api/operations/getprojectversions/)，按下载量顺序选择 1.21.1 / NeoForge 匹配版本的 JAR，默认每个最大 20 MiB。使用 API 发布的 SHA512 校验下载内容，并记录来源链接、版本、依赖和 SHA256。它是偏向热门模组的便利样本，不代表生态随机分布。原始第三方 JAR 不随 NeoCore 发行。

能力键来自结构化 API owner/member、语言能力节点或精确的旧诊断合同，重载描述符保留在同一节点内。无从归因的诊断保持独立，不能仅凭文本相似就合并。文件路径只作为证据。相同内容副本去重，同加载器同 modId 的不同版本按一个逻辑模组计算；多 modId 的同一 JAR 按一个联合逻辑单元计数。不同加载器保持独立，不假定同一语义。

优先级 = 影响逻辑模组数 × 平均去重逻辑源文件数 × 基础能力权重 ÷ 修复复杂度。支持 `scan --weights weights.json`：`{"java.nested_record":{"foundation_weight":3,"complexity":12}}`。权重和复杂度是公开的人工策略估值，不是机器推断的实际开发时长。历史报告单独留档，不参与当前受益与分数；当前报告必须匹配输入与源码指纹。静态疑点、当前首阻断、包级 Mixin 要求分别标明来源。后续隐藏阻断只有重新转换才能暴露。

A 只允许闭合、逐字审查的配方；当前实现 Optional.ofNullable 的引用参数子集，复用已有运行时，不包含装箱或完整泛型推断。propose 生成候选 adapter、测试与差异。validate-patch 将当前源码隔离复制，执行 Java/Python2/Python3 对照和全量回归，全部通过且原源码未变时才自动应用；不接受任意补丁目标、任意脚本或外部提供的配方。应用前的文件保留在 proposal/before，可按差异回退后重扫。

全量 Java 对照还需已有的固定版本 references 集合（原版类、映射和历史对照夹具），默认读取 backend/dev/references，也可设置环境变量 NEOCORE_REFERENCE_ROOT。本机开发环境已有该集合；发行包不附带这些第三方原件。缺少时明确拒绝应用，不跳过全量回归。扫描、排名、任务导出与普通转换不依赖这套全量对照夹具。

历史对照脚本默认读取 references 同级的 builds，独立存放时可设置 NEOCORE_VALIDATION_BUILD_ROOT。验证副本只复制所需 DS-03、DS-10、DS-16 和原模型夹具，不复制整个历史 builds；全量测试中的旧 DS 配置测试仍显式核查其约定的本机正式路径。新的自动补丁对照与编译测试在隔离候选中运行。这些外部历史测试前置条件会明确报缺失，不能作为静默略过测试的理由。

验证还复制 mixin_r75/input.json 和真实 Python 2 运行时到旧对照脚本约定的位置，仅供本机私有验证，不随发行。为避开旧 Python 2 imp 探针对中文模块路径的限制，候选默认放在开发盘根的 NeoCoreValidation098，可用 NEOCORE_VALIDATION_ROOT 指定另一个 ASCII 路径；proposal/validation/stage.json 记录实际位置。临时文件同样留在该候选内。旧测试保留 Windows 本机编码读取 JDK 输出，Python 日志使用 UTF-8；不以全局 UTF-8 模式误解码 javap 的本机输出。正式工程和普通工作台目录可继续使用中文路径，验证副本保留供审查。

B 导出带输入槽、拒绝条件、对照检查步骤的 lowering 模板任务；不把模板当作已实现的通用转换。C 导出适合 6.1 审查的代表案例、真实描述符、现有测试候选和风险。任务包只是数据，不会自动启动或联系其他智能体。新增 A 配方必须由维护者审查实现，不能仅因频率高就自动放行。

缓存绑定 JAR 内容、编译器/运行时/索引/挖掘器指纹、Java 目标与读取限额，并检查缓存内容摘要；它用于避免重复分析，不是对本机恶意修改的安全认证。ZIP/类大小、重复条目、加密条目和读取失败显式记录；PARTIAL 不能当作完成覆盖。嵌套依赖 JAR 只列清单，尚不递归分析；第三方依赖缺失单独列为依赖能力。静态扫描无法证明完整泛型、反射、并发和运行路径。

compare 仅比较同 SHA256 的输入交集。静态发现减少与实际生成文件增加分别统计，生成比例仅在同输入、同源文件分母、各自源码匹配的报告之间比较。没有成功观察报告的模组不计算生成增益。新增样本不能算作兼容率提升，首诊断减少不能算作救活整个模组。所有自动产物的 engine_verified 保持 false，网易行为由实机验收。

大批次报告按 200 行分页，支持只看当前观察阻断或静态疑点。任务包的 tasks/A.jsonl、B.jsonl、C.jsonl 保存全部能力任务；tasks/index.json 提供 UTF-8 字节偏移和长度，方便按能力直接读取。排名靠前的任务另有单独 JSON/Markdown，cohort.json 保留全部输入定位信息，避免数万小文件拖慢 Windows。summary.json、cohort.json 和 comparison_basis.json 是小型读取入口，后两者绑定原始 run.json 的摘要。比较时仍验证原始证据完整性；挖掘规则指纹改变则拒绝宣称前后增益。
