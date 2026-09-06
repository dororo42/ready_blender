# -*- coding: utf-8 -*-
"""Ready: Reaction-Diffusion — Blender 插件入口。

净室实现:算法来自公开文献(Pearson 1993 等),不包含任何 GPL 代码翻译。
许可:GPL-3.0-or-later(上官方平台要求)或按需调整(净室保证切换成本为零)。

导入说明(兼容两种加载模式):
  - 包模式:Blender 4.2+ 扩展系统把本目录作为包 ready_blender 加载(__package__ 非空);
  - 顶层模式:旧式目录加载把 __init__.py 当顶层模块加载(__package__ 为空)。
  _imp() 优先按包内相对路径导入,失败时兜底为顶层绝对导入。
"""
import importlib as _importlib
import os as _os
import sys as _sys

bl_info = {
    "name": "Ready: Reaction-Diffusion",
    "author": "Ready Blender Port Team",
    "version": (0, 1, 1),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar > Ready",
    "description": "Reaction-diffusion simulation on meshes and grids (Gray-Scott).",
    "category": "Simulation",
}

_ADDON_ROOT = _os.path.dirname(_os.path.realpath(__file__))

# 防1布防:启动自检结果(包模式下关键子模块可达性;非空=安装损坏)
SELF_CHECK_ERRORS = []


def _imp(subpath: str):
    """按包内相对路径导入模块(如 "ui.operators"),兼容包模式与顶层模式。"""
    if __package__:
        try:
            return _importlib.import_module("." + subpath, __package__)
        except ImportError:
            pass
    if _ADDON_ROOT not in _sys.path:
        _sys.path.insert(0, _ADDON_ROOT)
    return _importlib.import_module(subpath)


def _self_check():
    """启动自检(防 dev/安装态分叉缺陷,如 v1.5 的 fhn_spiral 枚举错误):
    包模式下验证关键子模块经相对导入可达——正是 ui/ 等子模块运行时依赖的路径。
    失败不阻断注册(保持可用性),错误收集到 SELF_CHECK_ERRORS 供面板提示。
    """
    SELF_CHECK_ERRORS.clear()
    if not __package__:
        return  # 顶层模式无相对导入,跳过
    for sub in ("core.rule", "core.vertex_rd", "presets.presets",
                "backend.numba_backend", "adapters.mesh_adapter",
                "controller.engine", "fileio.vtk_xml"):
        try:
            _importlib.import_module("." + sub, __package__)
        except ImportError as e:
            SELF_CHECK_ERRORS.append(f"{sub}: {e}")
    if SELF_CHECK_ERRORS:
        print(f"[ready_blender] 启动自检失败({len(SELF_CHECK_ERRORS)} 项),"
              f"插件可能安装损坏,请重装扩展:\n  " + "\n  ".join(SELF_CHECK_ERRORS))


def register():
    _self_check()  # 防1:启动自检(结果供面板提示)
    ui_props = _imp("ui.properties")
    ui_prefs = _imp("ui.preferences")
    ui_ops = _imp("ui.operators")
    ui_panels = _imp("ui.panels")
    ui_previews = _imp("ui.previews")
    session = _imp("controller.session")
    import bpy
    ui_previews.register()

    ReadySettings = ui_props.ReadySettings

    def _safe_register(cls):
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass  # 已注册(上次启用中途崩溃残留),幂等跳过

    _safe_register(ReadySettings)
    if hasattr(bpy.types.Scene, "ready_settings"):
        del bpy.types.Scene.ready_settings
    bpy.types.Scene.ready_settings = bpy.props.PointerProperty(type=ReadySettings)

    for cls in (ui_ops.RD_OT_init, ui_ops.RD_OT_play, ui_ops.RD_OT_pause,
                ui_ops.RD_OT_step, ui_ops.RD_OT_reset, ui_ops.RD_OT_bake,
                ui_ops.RD_OT_cancel_bake, ui_ops.RD_OT_brush,
                ui_ops.RD_OT_preset_load, ui_ops.RD_OT_update_display,
                ui_ops.RD_OT_import_pattern,
                ui_ops.RD_OT_mesh_prep, ui_ops.RD_OT_mesh_triangulate_copy,
                ui_ops.RD_OT_material_from_rd,
                ui_ops.RD_OT_add_displacement_gn,
                ui_ops.RD_OT_apply_vertex_displacement,
                ui_ops.RD_OT_subdivide_copy,
                ui_ops.RD_OT_remesh_copy,
                ui_ops.RD_OT_pattern_map_pick,
                ui_ops.RD_OT_import_preset_json,
                ui_ops.RD_OT_paste_preset_json,
                ui_ops.RD_OT_open_rdtool_web,
                ui_ops.RD_OT_grow3d_pipeline):
        _safe_register(cls)

    _safe_register(ui_prefs.ReadyPreferences)
    _safe_register(ui_prefs.RD_OT_numba_install)
    _safe_register(ui_prefs.RD_OT_numba_check)
    _safe_register(ui_panels.RD_PT_main)
    _safe_register(ui_panels.RD_PT_image)

    # F11:向引擎注册显示/重建回调(解耦 controller→ui 反向依赖)
    engine = _imp("controller.engine").get_engine()
    engine.display_hook = ui_ops.RD_OT_update_display.run_safe
    engine.rebuild_hook = ui_ops.init_engine_from_settings

    session.register_handlers()


def unregister():
    session = _imp("controller.session")
    ui_ops = _imp("ui.operators")
    ui_panels = _imp("ui.panels")
    ui_prefs = _imp("ui.preferences")
    ui_props = _imp("ui.properties")
    ui_prefs = _imp("ui.preferences")
    ui_previews = _imp("ui.previews")
    engine_mod = _imp("controller.engine")
    scheduler_mod = _imp("controller.scheduler")
    import bpy
    ui_previews.unregister()

    scheduler_mod.get_preview().stop()
    session.unregister_handlers()
    engine_mod.reset_engine()
    # 还原自动转换的 Image Editor 区域
    try:
        ui_props._restore_area()
    except Exception:
        pass
    # F13:清空密度检测缓存
    try:
        from adapters.mesh_adapter import clear_density_cache
        clear_density_cache()
    except Exception:
        pass

    def _safe_unregister(cls):
        try:
            bpy.utils.unregister_class(cls)
        except (ValueError, RuntimeError):
            pass  # 未注册或已注销,幂等跳过

    _safe_unregister(ui_prefs.RD_OT_numba_check)
    _safe_unregister(ui_prefs.RD_OT_numba_install)
    _safe_unregister(ui_prefs.ReadyPreferences)
    _safe_unregister(ui_panels.RD_PT_main)
    _safe_unregister(ui_panels.RD_PT_image)
    for cls in (ui_ops.RD_OT_init, ui_ops.RD_OT_play, ui_ops.RD_OT_pause,
                ui_ops.RD_OT_step, ui_ops.RD_OT_reset, ui_ops.RD_OT_bake,
                ui_ops.RD_OT_cancel_bake, ui_ops.RD_OT_brush,
                ui_ops.RD_OT_preset_load, ui_ops.RD_OT_update_display,
                ui_ops.RD_OT_import_pattern,
                ui_ops.RD_OT_mesh_prep, ui_ops.RD_OT_mesh_triangulate_copy,
                ui_ops.RD_OT_material_from_rd,
                ui_ops.RD_OT_add_displacement_gn,
                ui_ops.RD_OT_apply_vertex_displacement,
                ui_ops.RD_OT_subdivide_copy,
                ui_ops.RD_OT_remesh_copy,
                ui_ops.RD_OT_pattern_map_pick,
                ui_ops.RD_OT_import_preset_json,
                ui_ops.RD_OT_paste_preset_json,
                ui_ops.RD_OT_open_rdtool_web,
                ui_ops.RD_OT_grow3d_pipeline):
        _safe_unregister(cls)
    if hasattr(bpy.types.Scene, "ready_settings"):
        del bpy.types.Scene.ready_settings
    _safe_unregister(ui_props.ReadySettings)


if __name__ == "__main__":
    register()
