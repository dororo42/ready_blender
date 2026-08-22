# -*- coding: utf-8 -*-
"""模拟引擎:五状态状态机 + 模块级单例。净室实现。"""
from __future__ import annotations
import numpy as np
from enum import Enum


class EngineState(Enum):
    IDLE = 0
    RUNNING = 1
    PAUSED = 2
    NEEDS_REBUILD = 3
    STEPPING = 4  # 瞬时


class RDEngine:
    """模拟引擎(模块级单例,不挂 Scene 避免 undo 副作用)。

    状态机:
      IDLE →(play)→ RUNNING →(pause)→ PAUSED →(play)→ RUNNING
      任意 →(param rebuild)→ NEEDS_REBUILD → 重建后回原状态
      任意 →(reset)→ IDLE
      STEPPING:瞬时,step(n) 后回 PAUSED/IDLE
    """
    def __init__(self):
        self.state = EngineState.IDLE
        self._prev_state = EngineState.IDLE  # rebuild 后恢复
        self.rule = None
        self.fields = []       # list[np.ndarray]
        self.params = {}
        self.field_kind = "grid"  # "grid" | "mesh"
        self.nbr = None         # (nbr_idx, nbr_w) for mesh
        self.mesh_info = None   # dict with faces, n_cells, max_k, avg_k
        self.last_error = None  # B2:拓扑变更提示(面板展示)
        self.measured_speed = 0.0  # 预览实测步/秒(面板展示)
        self.display_hook = None  # F11:由 ui 注册的显示回调(解耦 controller→ui)
        self.rebuild_hook = None  # F11:由 ui 注册的重建回调(load_post 用)
        self.steps_done = 0
        self.tick_steps = 10    # 预览每 tick 步数
        self.tick_interval = 0.05  # 秒
        self.dirty_params = False
        self.dirty_kind = None  # "hot" | "rebuild" | None
        self.undo_stack = []    # list of (field_snapshot,)
        self._bake_cancel = False

    # ---- 状态机操作 ----
    def play(self):
        if self.state in (EngineState.IDLE, EngineState.PAUSED):
            self.state = EngineState.RUNNING

    def pause(self):
        if self.state == EngineState.RUNNING:
            self.state = EngineState.PAUSED

    def step(self, n=1):
        """同步跑 n 步(阻塞),完成后回 PAUSED/IDLE。"""
        if self.state not in (EngineState.PAUSED, EngineState.IDLE):
            return
        self._prev_state = self.state
        self.state = EngineState.STEPPING
        self._do_steps(n)
        self.state = self._prev_state

    def reset(self):
        self.state = EngineState.IDLE
        self.steps_done = 0
        self.undo_stack.clear()

    def mark_dirty(self, kind):
        """参数变更标记。kind='hot' 热更新 / 'rebuild' 需重建。"""
        self.dirty_params = True
        if kind == "rebuild":
            # B12/F8 修复:已处于 NEEDS_REBUILD 时直接返回,不污染状态
            if self.state == EngineState.NEEDS_REBUILD:
                return
            self._prev_state = self.state
            self.state = EngineState.NEEDS_REBUILD
        else:
            self.dirty_kind = kind

    def rebuild_done(self):
        self.state = self._prev_state

    # ---- 执行 ----
    def _do_steps(self, n):
        if self.rule is None or not self.fields:
            return
        if self.dirty_params and self.dirty_kind == "hot":
            # 热更新:参数已更新,下一 tick 自动生效
            self.dirty_params = False
            self.dirty_kind = None
        _backend.step(self.rule, self.fields, self.params, n,
                      field_kind=self.field_kind, nbr=self.nbr)
        self.steps_done += n

    def tick(self):
        """预览 tick:跑 tick_steps 步。返回 True 表示继续,False 停止。"""
        if self.state != EngineState.RUNNING:
            return False
        self._do_steps(self.tick_steps)
        return True

    # ---- 快照 undo(仅画笔) ----
    def save_snapshot(self):
        if self.fields:
            self.undo_stack.append(tuple(f.copy() for f in self.fields))
            if len(self.undo_stack) > 20:
                self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            snap = self.undo_stack.pop()
            for i, f in enumerate(snap):
                if i < len(self.fields):
                    self.fields[i][:] = f

    # ---- 烘焙 ----
    def bake(self, n_steps, progress_callback=None):
        """烘焙模式:跑 n_steps 步,带进度回调。"""
        self._bake_cancel = False
        chunk = max(1, n_steps // 100)  # 1% 增量
        done = 0
        while done < n_steps:
            if self._bake_cancel:
                break
            n = min(chunk, n_steps - done)
            self._do_steps(n)
            done += n
            if progress_callback:
                progress_callback(done / n_steps)
        return done

    def bake_cancel(self):
        self._bake_cancel = True


# 模块级单例
_engine_instance = None

# 后端单例(避免每 tick 重建)
try:
    from ..backend.numpy_backend import NumpyBackend as _NumpyBackend
except ImportError:
    from backend.numpy_backend import NumpyBackend as _NumpyBackend
_backend = _NumpyBackend()

def get_engine() -> RDEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = RDEngine()
    return _engine_instance

def reset_engine():
    """unregister 时调用。"""
    global _engine_instance
    _engine_instance = None
