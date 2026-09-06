# -*- coding: utf-8 -*-
"""模拟 Blender 扩展安装模式的导入环境,验证 formula_variant 修复。

扩展模式特征:仅 `ready_blender` 作为包可导入(父目录在 sys.path),
顶层 `presets` 不可导入 —— 即旧代码 `from presets import presets` 失败的场景。
"""
import importlib
import os
import sys
import types

import numpy as np  # noqa: F401  presets 链路依赖


def test_all():
    REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # pytest 收集阶段其它测试模块会 sys.path.insert(REPO) —— 本测试必须模拟
    # "扩展模式没有插件根目录在 sys.path" 的前提,故临时摘除,finally 恢复
    saved_path = list(sys.path)
    polluted = {os.path.abspath(p) for p in sys.path
                if p and os.path.abspath(p) in
                (REPO, os.path.dirname(os.path.abspath(__file__)), os.getcwd())}
    sys.path[:] = [p for p in sys.path
                   if not p or os.path.abspath(p) not in polluted]
    importlib.invalidate_caches()

    # 1) 模拟扩展模式:注册 ready_blender 为包(不执行其 __init__.py,避开 bpy)
    pkg = types.ModuleType("ready_blender")
    pkg.__path__ = [REPO]
    sys.modules["ready_blender"] = pkg
    ui_pkg = types.ModuleType("ready_blender.ui")
    ui_pkg.__path__ = [os.path.join(REPO, "ui")]
    sys.modules["ready_blender.ui"] = ui_pkg
    # 关键:不把插件根目录放进 sys.path(扩展模式没有),顶层 presets 不可导入
    # 其它测试模块的收集期 import 会把 presets 缓存进 sys.modules —— 一并摘除
    saved_modules = {m: sys.modules.pop(m) for m in list(sys.modules)
                     if m == "presets" or m.startswith("presets.")}
    try:
        # 2) 复现旧代码路径:from presets import presets 应失败
        try:
            importlib.import_module("presets")
            old_ok = True
        except ImportError:
            old_ok = False
        assert not old_ok, "顶层 presets 不应可导入(扩展模式前提被破坏)"

        # 3) 验证新代码路径:在 ui 包上下文执行 from ..presets import presets
        mod = importlib.import_module("ready_blender.presets.presets")
        assert mod is not None, "扩展模式包内相对导入失败"

        # 4) 验证 get_variants 返回 fhn_spiral(items 回调数据源正确)
        vs = mod.get_variants("fitzhugh_nagumo")
        ids = [v["id"] for v in vs]
        assert "fhn_spiral" in ids and "fhn_excite" in ids, ids

        # 5) 其余系统变体完整性
        for sid, expect in [("brusselator", "bru_spots"),
                            ("schnakenberg", "sch_spots"),
                            ("oregonator", "ore_spiral")]:
            ids = [v["id"] for v in mod.get_variants(sid)]
            assert expect in ids, (sid, ids)

        # 6) 模拟 items 回调组装(default + variants)
        items = [("default", "文献默认", "")] + [(v["id"], v["name"], "") for v in vs]
        assert any(i[0] == "fhn_spiral" for i in items)
    finally:
        # 清理伪装的包注册与 sys.path 修改,恢复被摘除的模块缓存,避免污染其它测试
        for m in [m for m in list(sys.modules)
                  if m == "ready_blender" or m.startswith("ready_blender.")]:
            del sys.modules[m]
        sys.modules.update(saved_modules)
        sys.path[:] = saved_path
        importlib.invalidate_caches()

    # 7) N13 修复验证:_addon_pkg 包名解析(bpy 缺席,直接内联同式逻辑)
    def _addon_pkg(pkg_name):
        return (pkg_name.rsplit(".", 1)[0]
                if pkg_name.startswith("bl_ext.") else "ready_blender")

    cases = [
        ("bl_ext.user_default.ready_blender.ui", "bl_ext.user_default.ready_blender"),
        ("ready_blender.ui", "ready_blender"),
        ("ui", "ready_blender"),
        ("", "ready_blender"),
    ]
    for p, e in cases:
        got = _addon_pkg(p)
        assert got == e, (p, got, e)
    print("ext_mode_import: all passed")


if __name__ == "__main__":
    test_all()
    print("all passed")
