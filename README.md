# NeoCore 0.9.9

共同创建：**haha123-beta 与 ChatGPT（OpenAI AI 助手）**。贡献说明见 [AUTHORS.md](AUTHORS.md)。

Java / NeoForge 模组到网易目标内容的实验性转换器，包含 NeoCore Compatibility Mining Engine（兼容性挖掘引擎）。当前固定参考 Minecraft 1.21.1 / NeoForge 21.1.233，网易运行行为由实机验收确认。

## 0.9.9 修复重点

本版将 0.9.8 的真实首阻断用于受审查的批量修复。新增 Java Unicode 预处理和物理行号映射、公开字段与同名方法的分离存储、已审查继承关系在重载/泛型边界中的复用、注册工厂的目标类型推断，以及现有文本、配置注册 API 的严格接线。外部 GUI/渲染泛型父类、Mixin 与耐久事件仍保留阻断。

详细验证与固定分母对照见 [0.9.9 验收](docs/0.9.9验收.md)。

## 沿用的挖掘功能

- 批量读取 JAR 字节码，按 API 合同和语言语义聚类，按潜在受益模组/源文件数排序。
- 区分静态疑点、真实转换首阻断和实际生成增量；内容副本与同模组多个版本去重。
- A 类精确受审查配方生成 adapter、测试和差异，验证后应用；B 类审查模板；C 类复杂语义任务包。
- 保留原工作台样式，支持命令行、Modrinth 采样、完整任务 JSONL 和修复前后对比。
- Optional.ofNullable 引用参数子集编译合同。未实现完整泛型、Mixin、反射或跨引擎玩法自动兼容。

## 启动

源码整理版保留必要的 Windows 解析组件，移出了 Zig、tree-sitter CLI 等大型重编译工具链及全部缓存/工作区。它不是免环境 EXE。

1. 推荐安装 **Windows x64 Python 3.14**，与随包解析二进制匹配，本次验证使用 Python 3.14.3。其他 Python 版本需替换匹配版本的解析绑定；其他系统还需自行重建语法库，不能直接使用随包 DLL。
2. 仅做静态挖掘可直接运行 `python run_neocore.py mining --help`。
3. 做 JAR 转换需 JDK 21，以及含 `org.benf.cfr.reader.Main` 的 CFR JAR。CFR 获取方式见 [官方页面](https://www.benf.org/other/cfr/)。本包不附带第三方模组、Minecraft JAR、CFR 或完整 Python 2 运行时。
4. 将 `local_env.example.cmd` 复制为 `local_env.cmd`，填写所需工具路径；该本机文件不会被 Git 跟踪。也可在终端设置同名环境变量。
5. 双击 `启动NeoCore.cmd`，或运行 `python run_neocore.py gui`。`backend.json` 会自动按当前目录生成，移动文件夹后重新启动即可。

```powershell
python run_neocore.py mining scan "D:/Mods" --output mining-runs/baseline
python run_neocore.py mining --help
python run_neocore.py cli --help
```

直接在终端运行 Python 时，需自行设置环境变量；`local_env.cmd` 由三个 `.cmd` 启动入口读取。JDK 可通过 PATH / JAVA_HOME 配置，或显式设置 NEOCORE_JAVA、NEOCORE_JAVA_HOME；CFR 使用 NEOCORE_CFR_JAR；真实 Py2 对照使用 NEOCORE_PYTHON2。完整历史回归还需要固定版本 references 和历史夹具；若缺失，验证会失败，不能把缺失测试当作通过。部分历史对照脚本保留开发路径示例，需要维护者按本机参考集配置。

详见 [挖掘使用说明](docs/兼容性挖掘使用说明.md) 和 [验证范围](docs/验证范围.md)。

## AddOn 与加载器

核心行为包、资源包及加载入口随源码提供，见 [addon](addon/README.md) 和 [加载器说明](loader/README.md)。重新生成核心 AddOn：`python scripts/build_addon.py`。生成目录默认为 `outputs/addon-0.9.9`。

## 上传 GitHub

推荐解压后使用 GitHub Desktop / Git 将此目录作为仓库上传，代码即可在线浏览。网页直接上传 ZIP 只会存储这个 ZIP，不会自动展开成仓库代码。GitHub 网页单文件限制和上传方法见 [官方文档](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)。

`.gitignore` 已排除本机配置、凭据、原始 JAR、运行工作区和构建缓存。不要把新产生的 backend.json、local_env.cmd、工作区或原始模组重新打包提交。文件哈希清单见 SOURCE_MANIFEST.json。

## 许可

项目自有代码采用 **PolyForm Noncommercial 1.0.0**，仅授予协议规定的非商业用途许可。完整条款见 [LICENSE](LICENSE) 和 [官方协议](https://polyformproject.org/licenses/noncommercial/1.0.0)，署名声明见 [NOTICE](NOTICE)。商业使用须另行取得权利人许可。

第三方解析组件及语法继续适用其原许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
