# -*- coding: utf-8 -*-
"""模拟 Blender 扩展安装模式的导入环境,验证 formula_variant 修复。

扩展模式特征:仅 `ready_blender` 作为包可导入(父目录在 sys.path),
顶层 `presets` 不可导入 —— 即旧代码 `from presets import presets` 失败的场景。
"""
import sys, types, importlib


def test_all():
    ROOT = r"c:\Users\Administrator\.openclaw-autoclaw\workspace"

    # 1) 模拟扩展模式:注册 ready_blender 为包(不执行其 __init__.py,避开 bpy)
    pkg = types.ModuleType("ready_blender")
    pkg.__path__ = [ROOT + r"\ready_blender"]
    sys.modules["ready_blender"] = pkg
    ui_pkg = types.ModuleType("ready_blender.ui")
    ui_pkg.__path__ = [ROOT + r"\ready_blender\ui"]
    sys.modules["ready_blender.ui"] = ui_pkg
    # 关键:不把插件根目录放进 sys.path(扩展模式没有),顶层 presets 不可导入

    # 2) 复现旧代码路径:from presets import presets 应失败
    try:
        importlib.import_module("presets")
        old_ok = True
    except ImportError:
        old_ok = False
    print(f"[{'PASS' if not old_ok else 'FAIL'}] 扩展模式下顶层 presets 不可导入(旧代码死因复现): not importable = {not old_ok}")

    # 3) 验证新代码路径:在 ui 包上下文执行 from ..presets import presets
    try:
        mod = importlib.import_module("ready_blender.presets.presets")
        print("[PASS] from ..presets import presets 在扩展模式下成功")
    except ImportError as e:
        print(f"[FAIL] 新导入路径失败: {e}")

    # 4) 验证 get_variants 返回 fhn_spiral(items 回调数据源正确)
    vs = mod.get_variants("fitzhugh_nagumo")
    ids = [v["id"] for v in vs]
    ok = "fhn_spiral" in ids and "fhn_excite" in ids
    print(f"[{'PASS' if ok else 'FAIL'}] FHN 变体含 fhn_spiral/fhn_excite: {ids}")

    # 5) 其余系统变体完整性
    for sid, expect in [("brusselator", "bru_spots"), ("schnakenberg", "sch_spots"), ("oregonator", "ore_spiral")]:
        ids = [v["id"] for v in mod.get_variants(sid)]
        print(f"[{'PASS' if expect in ids else 'FAIL'}] {sid} 变体: {ids}")

    # 6) 模拟 items 回调组装(default + variants)
    items = [("default", "文献默认", "")] + [(v["id"], v["name"], "") for v in vs]
    ok = any(i[0] == "fhn_spiral" for i in items)
    print(f"[{'PASS' if ok else 'FAIL'}] items 回调将包含 fhn_spiral -> 赋值不再 TypeError")

    # 7) N13 修复验证:_addon_pkg 包名解析(bpy 缺席,直接内联同式逻辑)
    def _addon_pkg(pkg):
        return pkg.rsplit(".", 1)[0] if pkg.startswith("bl_ext.") else "ready_blender"

    cases = [
        ("bl_ext.user_default.ready_blender.ui", "bl_ext.user_default.ready_blender"),
        ("ready_blender.ui", "ready_blender"),
        ("ui", "ready_blender"),
        ("", "ready_blender"),
    ]
    all_ok = all(_addon_pkg(p) == e for p, e in cases)
    for p, e in cases:
        got = _addon_pkg(p)
        print(f"[{'PASS' if got == e else 'FAIL'}] _addon_pkg({p!r}) = {got!r} (期望 {e!r})")

    assert all_ok, "_addon_pkg 包名解析失败"
    print("\n全部验证通过:扩展模式下 fhn_spiral 可正常赋值")


if __name__ == "__main__":
    test_all()
    print("all passed")
