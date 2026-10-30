# NeoCore AddOn 与游戏加载入口

这里是用本仓库核心源码生成的独立网易电脑版 AddOn；不包含任何用户模组或原始第三方 JAR。

- `NeoCore_behavior_pack/manifest.json`：0.9.9 行为包声明。
- `NeoCore_behavior_pack/NeoCoreSourceScripts/modMain.py`：网易双端入口，注册和关闭核心宿主。
- `NeoCore_behavior_pack/NeoCoreSourceScripts/runtime_host.py`：加载会话和 SDK 宿主。
- `NeoCore_behavior_pack/NeoCoreSourceScripts/source_modules.py`：私有源码模块加载器。
- `NeoCore_behavior_pack/NeoCoreSourceScripts/source_snapshot.py`：核心源码快照，必须和加载器一起保留。
- `NeoCore_resource_pack/`：核心配套资源包。

游戏中同时启用核心行为包和资源包。其他模组需要独立翻译为内容包后再启用；这里不直接执行 Java JAR。当前参考 Minecraft 1.21.1 / NeoForge 21.1.233；网易引擎验证与本地 SDK 替身测试分别记录，不把本地启动当作游戏实测通过。

可编辑源在 `backend/core/NeoForgeCoreScripts`，加载器在其中的 `core/runtime_host.py`、`core/source_modules.py`，入口模板在 `backend/dev/templates`。修改这些源文件后运行 `python scripts/build_addon.py 新输出目录` 重新生成；不要只修改快照中的一份副本。

加载器登记协议版本与工具发行版本分开管理。分发本 AddOn 时同时保留仓库的 LICENSE 和 NOTICE。
