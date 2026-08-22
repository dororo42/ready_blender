# -*- coding: utf-8 -*-
"""UV 烘焙管线核心(纯 Python 可测部分):UV 栅格化 + 回贴。净室实现。

流程(混合工作流"网格直跑→烘焙到 UV"):
  1. 取网格 UV 坐标(每三角形顶点 UV)
  2. 栅格化:把每个三角形按 UV 面积覆盖到 2D 栅格,记录每个像素对应的面索引
  3. 在栅格上跑 2D RD(或直接把面域浓度采样到像素)
  4. 输出纹理(像素值 = 其对应面的浓度,或 RD 演化后的值)
"""
from __future__ import annotations
import numpy as np


def rasterize_uv(uvs: np.ndarray, faces: np.ndarray, res: int = 512):
    """把三角形 UV 栅格化到 res×res 网格。

    参数:
      uvs: (N,2) float UV 坐标(0..1)
      faces: (F,3) int 面索引
    返回:
      face_map: (res,res) int32 像素→面索引(-1 = 空,未覆盖)
      coverage: (res,res) float32 像素被面覆盖的次数(用于归一化/诊断)
    """
    face_map = np.full((res, res), -1, dtype=np.int32)
    coverage = np.zeros((res, res), dtype=np.float32)
    for fi in range(len(faces)):
        tri = uvs[faces[fi]] * res  # (3,2) 像素坐标
        # 三角形包围盒
        x0 = max(0, int(np.floor(tri[:, 0].min())))
        x1 = min(res, int(np.ceil(tri[:, 0].max())) + 1)
        y0 = max(0, int(np.floor(tri[:, 1].min())))
        y1 = min(res, int(np.ceil(tri[:, 1].max())) + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        # 重心坐标判断
        p0, p1, p2 = tri
        d = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])
        if abs(d) < 1e-12:
            continue  # 退化三角形
        xs = np.arange(x0, x1, dtype=np.float32) + 0.5
        ys = np.arange(y0, y1, dtype=np.float32) + 0.5
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        w0 = ((p1[1] - p2[1]) * (gx - p2[0]) + (p2[0] - p1[0]) * (gy - p2[1])) / d
        w1 = ((p2[1] - p0[1]) * (gx - p2[0]) + (p0[0] - p2[0]) * (gy - p2[1])) / d
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        face_map[x0:x1, y0:y1][inside] = fi
        coverage[x0:x1, y0:y1][inside] += 1.0
    return face_map, coverage


def bake_face_values(face_map: np.ndarray, face_values: np.ndarray):
    """把面域浓度采样到纹理像素。返回 (res,res) float 数组,空像素 = NaN。"""
    out = np.full(face_map.shape, np.nan, dtype=np.float32)
    valid = face_map >= 0
    out[valid] = face_values[face_map[valid]]
    return out


def uv_stats(face_map: np.ndarray):
    """UV 覆盖统计:覆盖率、空洞比例(用于密度/展开质量诊断)。"""
    total = face_map.size
    covered = int((face_map >= 0).sum())
    return {"coverage_ratio": covered / total, "uncovered_ratio": 1 - covered / total}
