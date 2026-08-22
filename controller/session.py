# -*- coding: utf-8 -*-
"""会话管理:load_post 重建 + 序列化。净室实现。"""
from __future__ import annotations


class SessionManager:
    """管理 .blend 文件加载后的引擎重建。"""

    @staticmethod
    def on_load_post(dummy=None):
        """注册为 bpy.app.handlers.load_post handler。

        .blend 重开时,Scene.ready_settings 的 PropertyGroup 由 Blender 自动恢复;
        这里用恢复的参数重建引擎,避免"UI 有参数、引擎没反应"的僵尸状态。
        """
        import bpy
        try:
            from .engine import get_engine, EngineState
        except ImportError:
            from controller.engine import get_engine, EngineState
        settings = bpy.context.scene.ready_settings
        if not settings or not settings.rule_name:
            return
        # F11 修复:经 engine.rebuild_hook 调用,消除 controller→ui 反向依赖
        engine = get_engine()
        if engine.rebuild_hook is not None:
            try:
                engine.rebuild_hook(bpy.context)
                return
            except RuntimeError:
                pass
        engine.reset()
        engine.state = EngineState.IDLE


def register_handlers():
    import bpy
    bpy.app.handlers.load_post.append(SessionManager.on_load_post)

def unregister_handlers():
    import bpy
    try:
        bpy.app.handlers.load_post.remove(SessionManager.on_load_post)
    except Exception:
        pass
