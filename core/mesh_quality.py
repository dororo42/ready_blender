# -*- coding: utf-8 -*-
"""网格预处理与质量评估(纯 Python+numpy,零 bpy,可本地测试)。净室实现。

质量指标(目标模式定义):
  - 三角形占比 / 顶点数 / 面数
  - 边长统计(最小/最大/极差/均值)——边长极差衡量均匀性
  - 狭长三角形占比(最小角 < 20° 的三角形,Sliver 检测)
  - 面积变异系数 CV(面密度均匀性)
  - 网格数量评估:按物体尺度(包围盒对角线)与目标面密度估算"是否足够"
"""
from __future__ import annotations
import numpy as np


def mesh_quality_report(verts: np.ndarray, faces: np.ndarray,
                        min_angle_deg: float = 20.0,
                        cv_threshold: float = 0.5,
                        target_face_density: float = 12.0):
    """对三角网格做质量评估。

    参数:
      verts: (N,3) float32 顶点
      faces: (F,3) int32 三角面索引
      min_angle_deg: 狭长三角形判定最小角(度)
      cv_threshold: 面积 CV 均匀性阈值
      target_face_density: 数量评估目标密度 = 面数 / 包围盒对角线长(1D,随细分度增长),
                           默认 12.0(约等于 20x20 规则网格的一半,低于此判定数量不足)
    返回 dict:全部指标 + 判定结论。
    """
    verts = np.asarray(verts, dtype=np.float32)
    faces = np.asarray(faces, dtype=np.int32)
    report = {"n_verts": int(len(verts)), "n_faces": int(len(faces))}
    if len(faces) == 0:
        report.update({"verdict": "empty", "issues": ["网格没有面"]})
        return report

    tris = verts[faces]  # (F,3,3)
    a = tris[:, 1] - tris[:, 0]
    b = tris[:, 2] - tris[:, 0]
    c = tris[:, 2] - tris[:, 1]
    edge_lens = np.concatenate([
        np.linalg.norm(a, axis=1),
        np.linalg.norm(b, axis=1),
        np.linalg.norm(c, axis=1)])
    report["edge_min"] = float(edge_lens.min())
    report["edge_max"] = float(edge_lens.max())
    report["edge_mean"] = float(edge_lens.mean())
    report["edge_ratio"] = float(edge_lens.max() / max(edge_lens.min(), 1e-12))

    # 面积
    cross = np.cross(a, b)
    areas = np.linalg.norm(cross, axis=1) * 0.5
    report["area_mean"] = float(areas.mean())
    report["area_cv"] = float(areas.std() / max(areas.mean(), 1e-12))

    # 狭长三角形(最小角)
    la = np.linalg.norm(a, axis=1)
    lb = np.linalg.norm(b, axis=1)
    lc = np.linalg.norm(c, axis=1)
    # 用余弦定理求每面最小角(弧度)
    cosA = np.clip((la ** 2 + lb ** 2 - lc ** 2) / np.maximum(2 * la * lb, 1e-12), -1, 1)
    cosB = np.clip((lb ** 2 + lc ** 2 - la ** 2) / np.maximum(2 * lb * lc, 1e-12), -1, 1)
    cosC = np.clip((lc ** 2 + la ** 2 - lb ** 2) / np.maximum(2 * lc * la, 1e-12), -1, 1)
    min_angle = np.minimum.reduce([np.arccos(cosA), np.arccos(cosB), np.arccos(cosC)])
    min_angle_deg_arr = np.degrees(min_angle)
    sliver_mask = min_angle_deg_arr < min_angle_deg
    report["sliver_ratio"] = float(sliver_mask.mean())
    report["min_angle_min"] = float(min_angle_deg_arr.min())
    report["min_angle_mean"] = float(min_angle_deg_arr.mean())

    # 数量评估(按尺度):面密度 = 面数 / 包围盒对角线长(1D,随细分度增长)
    bb = verts.max(axis=0) - verts.min(axis=0)
    diag = float(np.linalg.norm(bb))
    report["bbox_diag"] = diag
    density = len(faces) / max(diag, 1e-12)
    report["face_density"] = float(density)

    issues = []
    if report["sliver_ratio"] > 0.2:
        issues.append(f"狭长三角形占比 {report['sliver_ratio']*100:.1f}% 过高(>20%)")
    if report["area_cv"] > cv_threshold:
        issues.append(f"面积变异系数 {report['area_cv']:.2f} 过大(> {cv_threshold}),密度不均")
    if report["edge_ratio"] > 10.0:
        issues.append(f"边长极差 {report['edge_ratio']:.1f} 过大(>10)")
    if density < target_face_density:
        issues.append(f"网格数量可能不足:面密度 {density:.1f}(目标 ≥ {target_face_density:.0f}),"
                      f"建议细分/重网格化")
    if len(issues) == 0:
        report["verdict"] = "ok"
    else:
        report["verdict"] = "needs_prep"
    report["issues"] = issues
    report["uniform_ok"] = (report["area_cv"] <= cv_threshold
                            and report["sliver_ratio"] <= 0.2
                            and report["edge_ratio"] <= 10.0)
    report["quantity_ok"] = density >= target_face_density
    return report


def triangulate(verts: np.ndarray, faces: np.ndarray):
    """n-gon → 三角扇拆分(纯 Python 版,供测试;Blender 侧用 bmesh.ops.triangulate)。

    仅支持凸多边形;faces 中每行变长时用 object dtype。
    """
    tris = []
    for f in faces:
        for k in range(1, len(f) - 1):
            tris.append([f[0], f[k], f[k + 1]])
    return np.asarray(tris, dtype=np.int32) if tris else np.zeros((0, 3), dtype=np.int32)
