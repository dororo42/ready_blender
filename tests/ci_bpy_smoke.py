# -*- coding: utf-8 -*-
"""CI 无头冒烟:在真实 Blender Python 环境(bpy wheel)中验证核心可用。

覆盖:
1. import bpy(真实 Blender 运行时);
2. ready_blender 整包可导入(包内相对导入网络完好);
3. Gray-Scott 面域仿真:三角网格 → 面邻接 → 带取向/平流扩展步进,有限且出图;
4. preset_io 导入/导出往返。
"""
import importlib.util
import os
import sys

import bpy  # noqa: F401  真实 Blender 运行时
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 仓库根目录名未必等于包名(任意克隆目录),按路径显式加载包
_spec = importlib.util.spec_from_file_location(
    "ready_blender", os.path.join(REPO, "__init__.py"),
    submodule_search_locations=[REPO])
ready_blender = importlib.util.module_from_spec(_spec)
sys.modules["ready_blender"] = ready_blender
_spec.loader.exec_module(ready_blender)

from ready_blender.core.rule import GrayScottRule  # noqa: E402
from ready_blender.core.meshgen import triangular  # noqa: E402
from ready_blender.core.field import build_face_adjacency  # noqa: E402

assert ready_blender.bl_info["name"] == "Ready: Reaction-Diffusion"

verts, faces = triangular(24, 24)
centers = verts[faces].mean(axis=1).astype(np.float32)
nbr_idx, nbr_w, _, _ = build_face_adjacency(faces, "vertex")
r = GrayScottRule()
rng = np.random.default_rng(42)
a = np.ones(len(centers), np.float32)
b = np.zeros(len(centers), np.float32)
b[rng.integers(0, len(centers), 24)] = 1.0
p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0,
         mesh_centers=centers, wrap=False,
         orientation_kind="radial", orientation_strength=0.6,
         flow_kind="vortex", flow_strength=0.4)
for _ in range(200):
    r.update([a, b], p, 1.0, field_kind="mesh", nbr=(nbr_idx, nbr_w))
assert np.isfinite(a).all() and np.isfinite(b).all(), "仿真出现 NaN/Inf"
assert (b > 0.01).any(), "200 步后无图案"

from ready_blender.fileio.preset_io import (export_preset_dict,  # noqa: E402
                                            import_preset_dict)

d = export_preset_dict({"Du": 0.16, "Dv": 0.08, "F": 0.034, "k": 0.0618, "dt": 1.0},
                       "ci 往返", preset_id="ci_1")
assert import_preset_dict(d)["params"]["F"] == 0.034

print(f"[CI-SMOKE] OK  blender={bpy.app.version_string}  cells={len(centers)}  "
      f"b_max={float(b.max()):.3f}")
