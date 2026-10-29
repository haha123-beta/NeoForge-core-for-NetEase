# -*- coding: utf-8 -*-
# 接口.py
# 对外公开的接口，供其他附加包调用

from __future__ import print_function
from __future__ import absolute_import

import os
import sys

# 尝试导入 alpha_neoforge
try:
    from core.alpha_neoforge import (
        register_modpack as _register_modpack,
        get_registered_modpacks as _get_registered_modpacks,
        find_modpack_by_id as _find_modpack_by_id,
        list_all_modpacks as _list_all_modpacks
    )
    print(u"[接口] 使用相对导入加载 alpha_neoforge")
    
except ImportError:
    try:
        from alpha_neoforge import (
            register_modpack as _register_modpack,
            get_registered_modpacks as _get_registered_modpacks,
            find_modpack_by_id as _find_modpack_by_id,
            list_all_modpacks as _list_all_modpacks
        )
        print(u"[接口] 使用绝对导入加载 alpha_neoforge")
        
    except ImportError:
        try:
            script_dir = os.path.dirname(os.path.dirname(__file__))
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            from alpha_neoforge import (
                register_modpack as _register_modpack,
                get_registered_modpacks as _get_registered_modpacks,
                find_modpack_by_id as _find_modpack_by_id,
                list_all_modpacks as _list_all_modpacks
            )
            print(u"[接口] 通过 sys.path 加载 alpha_neoforge")
            
        except ImportError as e:
            print(u"[接口] 所有导入方式均失败: {}".format(e))
            def _register_modpack(path):
                return {"success": False, "message": u"alpha_neoforge 未加载"}
            def _get_registered_modpacks():
                return {}
            def _find_modpack_by_id(id):
                return None
            def _list_all_modpacks():
                pass


def register_modpack(resources_path):
    """注册一个模组包"""
    return _register_modpack(resources_path)


def get_registered_modpacks():
    """获取所有已注册的模组包"""
    return _get_registered_modpacks()


def find_modpack_by_id(mod_id):
    """根据模组 ID 查找已注册的模组信息"""
    return _find_modpack_by_id(mod_id)


def list_all_modpacks():
    """在控制台列出所有已注册的模组包"""
    _list_all_modpacks()


def is_mod_loaded(mod_id):
    """检查某个模组是否已加载"""
    return find_modpack_by_id(mod_id) is not None


def get_mod_count():
    """获取已注册的模组数量"""
    return len(get_registered_modpacks())


__all__ = [
    "register_modpack",
    "get_registered_modpacks",
    "find_modpack_by_id",
    "list_all_modpacks",
    "is_mod_loaded",
    "get_mod_count",
]


if __name__ == "__main__":
    print(u"\n[接口] 自测模式")
    print(u"[接口] 可用函数: {}".format(__all__))
    result = register_modpack(".")
    print(u"[接口] 注册结果: {}".format(result))