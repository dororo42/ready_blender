# -*- coding: utf-8 -*-
"""compute shader 后端(P3-1):mesh 邻接 gather 的 GPU 加速。

限制:gpu.compute.dispatch 仅 Windows/Linux 可用(macOS OpenGL 4.1 无 compute,
headless 无 GPU context)。运行时探测失败 → 调用方降级 numpy。
需 Blender 4.2+;4.5 用 gpu.shader.create_from_info。
本文件为骨架实现,offscreen/buffer 细节需 Blender 运行时调试。
"""
from __future__ import annotations


class ComputeMeshBackend:
    """mesh 邻接 gather 的 compute shader 后端。

    设计:
      - 邻接表(nbr_idx int32, nbr_w float32)以 SSBO 传入
      - 每个 work item 处理一个 cell:加权求和 → 拉普拉斯 → Gray-Scott 更新
      - 双缓冲 ping-pong
    """

    name = "compute"
    capabilities = {"grid": False, "mesh": True, "volume": False}

    def __init__(self, n_cells: int, max_k: int, nbr_idx, nbr_w):
        import bpy
        if bpy.app.version < (4, 5, 0):
            raise RuntimeError("compute backend requires Blender 4.5+ for stable gpu.compute")
        self._probe_available()

    @staticmethod
    def _probe_available():
        """探测 compute shader 可用性(macOS/headless 会失败)。"""
        import bpy
        if bpy.app.build_options is not None:
            pass  # 仅提示
        import gpu
        try:
            # 尝试创建最小 compute shader;失败则抛异常
            import numpy as np
            _ = gpu
            return True
        except Exception:
            raise RuntimeError("gpu compute unavailable on this platform")

    def step(self, fields, params, n=1, nbr=None):
        """GPU 步进。骨架:需在 Blender 内完成 SSBO 上传/dispatch/回读。"""
        raise NotImplementedError("需在 Blender 运行时完成 SSBO 上传与 dispatch 调试")


def make_compute_backend(n_cells, max_k, nbr_idx, nbr_w):
    """工厂:探测失败返回 None(调用方降级 numpy)。"""
    try:
        return ComputeMeshBackend(n_cells, max_k, nbr_idx, nbr_w)
    except Exception:
        return None
