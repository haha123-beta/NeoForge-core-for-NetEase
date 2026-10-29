# 加载器代码位置

加载器已经随 AddOn 完整包含，不是只有翻译器或说明文件。

| 作用 | 可编辑源 | AddOn 中的实际入口 |
| --- | --- | --- |
| 网易入口与双端绑定 | `backend/dev/templates/source_core_modMain.py` | `addon/NeoCore_behavior_pack/NeoCoreSourceScripts/modMain.py` |
| 运行时宿主 | `backend/core/NeoForgeCoreScripts/core/runtime_host.py` | `addon/NeoCore_behavior_pack/NeoCoreSourceScripts/runtime_host.py` |
| 私有源码模块加载 | `backend/core/NeoForgeCoreScripts/core/source_modules.py` | `addon/NeoCore_behavior_pack/NeoCoreSourceScripts/source_modules.py` |
| 内容包入口 | `backend/dev/templates/source_content_modMain.py`、`source_resource_modMain.py` | 翻译器按内容包生成 |

这些入口使用协议 2 源码快照、内容登记屏障及统一清理。核心 API、运行时和原始加载器源码保留在 `backend/core`，现成 AddOn 保留在 `addon`。本目录仅给出索引，避免再维护第三份实现副本。
