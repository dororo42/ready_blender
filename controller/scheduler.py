# -*- coding: utf-8 -*-
"""调度器:预览 tick(bpy.app.timers)+ 烘焙进度。净室实现。"""
from __future__ import annotations
from .engine import get_engine, EngineState


class PreviewScheduler:
    """管理 bpy.app.timers 注册/注销。"""

    def __init__(self):
        self._registered = False
        self._last_display = 0.0

    def start(self):
        import bpy
        # 幂等修复:先停再启,即使上次 timer 异常死亡也能恢复(症状:暂停后无法再运行)
        self.stop()
        self._registered = True
        bpy.app.timers.register(self._tick, first_interval=0.0)

    def stop(self):
        import bpy
        if not self._registered:
            return
        self._registered = False
        try:
            bpy.app.timers.unregister(self._tick)
        except Exception:
            pass

    def _tick(self):
        engine = get_engine()
        if engine.state != EngineState.RUNNING:
            self._registered = False
            return None  # 停止 timer
        try:
            import time as _time
            _t0 = _time.monotonic()
            engine.tick()
            _elapsed = max(_time.monotonic() - _t0, 1e-6)
            engine.measured_speed = engine.tick_steps / _elapsed
            # 审查修复:播放期间必须写显示数据,否则画面冻结;
            # 节流:显示更新至少间隔 0.1s,避免大网格 bmesh 重建卡 UI
            # F11 修复:经 engine.display_hook 调用,消除 controller→ui 反向依赖
            now = _time.monotonic()
            if now - self._last_display >= 0.1:
                self._last_display = now
                if engine.display_hook is not None:
                    try:
                        engine.display_hook()
                    except Exception:
                        pass
        except Exception:
            # 异常自愈:停止 timer 并暂停,避免卡死 RUNNING 状态(症状:再点运行无反应)
            self._registered = False
            engine.pause()
            return None
        return engine.tick_interval  # 下次间隔


def _tag_redraw_all():
    """遍历所有窗口的 area,对 VIEW_3D 和 IMAGE_EDITOR 打 tag_redraw。"""
    import bpy
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in ("VIEW_3D", "IMAGE_EDITOR"):
                for region in area.regions:
                    region.tag_redraw()


# 模块级单例
_preview = None

def get_preview() -> PreviewScheduler:
    global _preview
    if _preview is None:
        _preview = PreviewScheduler()
    return _preview
