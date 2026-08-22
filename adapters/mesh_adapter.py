# -*- coding: utf-8 -*-
"""mesh_adapter:numpy 场 ↔ Blender mesh 属性桥接。净室实现。"""
from __future__ import annotations
import numpy as np


def build_face_adjacency_bmesh(obj, kind="vertex"):
    """从 Blender mesh 对象构建面级邻接表(纯 Python,无 bpy 依赖的等价实现)。

    参数:
      obj: bpy.types.Object(mesh 对象)或 dict(有 'data' 键)
      kind: 'vertex' 共享顶点邻接 / 'edge' 共享边邻接
    返回:
      faces: (F,3) int32 数组(三角化后)
      nbr_idx: (F,K) int32 稠密 K 列平铺
      nbr_w: (F,K) float32 权重(1/度归一化)
      max_k, avg_k
    """
    import bpy
    mesh = obj.data if hasattr(obj, "data") else obj
    # 三角化(复制一份,不改原网格)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    # 获取三角面(原始面可能是 n-gon,用 tessellation)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.faces.index_update()  # B5 修复
    faces = np.array([[loop.vert.index for loop in face.loops] for face in bm.faces], dtype=np.int32)
    n_verts = len(bm.verts)
    bm.free()
    # 复用 core 的邻接构建(净室:与 bpy 无关)
    try:
        from ..core.field import build_face_adjacency
    except ImportError:
        from core.field import build_face_adjacency
    nbr_idx, nbr_w, max_k, avg_k = build_face_adjacency(faces, kind)
    return faces, nbr_idx, nbr_w, max_k, avg_k, n_verts


def mesh_to_field(obj, values=None, kind="vertex"):
    """从 Blender mesh 构建 MeshField(面域标量场)。

    values: 可选,长度 = 面数的初始值数组;默认零。
    """
    try:
        from ..core.field import MeshField
    except ImportError:
        from core.field import MeshField
    faces, nbr_idx, nbr_w, max_k, avg_k, n_verts = build_face_adjacency_bmesh(obj, kind)
    mf = MeshField(faces, kind)
    mf.nbr_idx = nbr_idx
    mf.nbr_w = nbr_w
    mf.max_k = max_k
    mf.avg_k = avg_k
    if values is not None:
        mf.data[:] = values
    return mf


def write_vertex_color(obj, face_values, color_layer_name="RD_value", vmin=None, vmax=None):
    """面域标量 → 顶点色(面积加权平均)。

    face_values: (F,) 面域标量
    顶点值 = Σ(相邻面值 × 面面积) / Σ(相邻面面积)
    """
    import bpy
    mesh = obj.data
    if color_layer_name not in mesh.color_attributes:
        mesh.color_attributes.new(name=color_layer_name, type="FLOAT_COLOR", domain="POINT")
    layer = mesh.color_attributes[color_layer_name]
    # F9+F16 修复:面域→顶点域收敛到公共函数,外层不再建 bmesh(每帧仅一次)
    vals = _face_to_vertex_values(obj, face_values)
    if vmin is None:
        vmin = float(vals.min())
    if vmax is None:
        vmax = float(vals.max())
    rng = max(vmax - vmin, 1e-9)
    norm = np.clip((vals - vmin) / rng, 0, 1)
    for v in mesh.vertices:
        c = norm[v.index]
        layer.data[v.index].color = (c, c * 0.6, 1.0 - c, 1.0)
    return vals


def write_named_attribute(obj, face_values, attr_name="RD_value", domain="FACE"):
    """面域标量 → 命名属性(GN 可读)。

    修复说明(鹰眼审查):
    - FACE 域:face_values 按三角化面索引给出,但 mesh 的 FACE 属性长度 = 原始多边形数;
      必须把三角化子面映射回原始多边形(按中心点所属),不能直接按索引截断。
    - 属性已存在时复用,不删除重建(避免破坏 GN 引用与每 tick 属性重建开销)。
    - POINT 域:面积加权平均直接写入,不再建临时顶点色层。
    """
    import bpy
    import bmesh
    mesh = obj.data
    if domain == "FACE":
        # 三角化面 → 原始多边形映射
        # 审查修复:三角化后新面的 face.index ≠ 原始多边形索引,
        # 必须用 bmesh.ops.triangulate 返回的 face_map(新面→原面)做映射。
        bm = bmesh.new()
        bm.from_mesh(mesh)
        ret = bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.faces.index_update()  # B5 修复:拓扑修改后重算索引
        face_map = ret.get("face_map", {})
        # NaN/inf 防护(与 _face_to_vertex_values 同口径):坏数据不再进入属性
        tri_values = np.nan_to_num(np.asarray(face_values, dtype=np.float32),
                                   nan=0.0, posinf=1e30, neginf=-1e30)
        n_polys = len(mesh.polygons)
        accum = np.zeros(n_polys, dtype=np.float64)
        counts = np.zeros(n_polys, dtype=np.int32)
        for fi, tri_face in enumerate(bm.faces):
            orig_face = face_map.get(tri_face, tri_face)
            pi = orig_face.index
            if fi < len(tri_values) and 0 <= pi < n_polys:
                accum[pi] += tri_values[fi]
                counts[pi] += 1
        vals = np.zeros(n_polys, dtype=np.float32)
        np.divide(accum, np.maximum(counts, 1), out=vals)
        bm.free()
    elif domain == "POINT":
        vals = _face_to_vertex_values(obj, face_values)
    else:
        raise ValueError(f"unsupported domain {domain}")
    # 复用或创建属性(不重建)
    if attr_name not in mesh.attributes:
        mesh.attributes.new(name=attr_name, type="FLOAT", domain=domain)
    attr = mesh.attributes[attr_name]
    for i in range(min(len(attr.data), len(vals))):
        attr.data[i].value = float(vals[i])
    return attr


def _face_to_vertex_values(obj, face_values):
    """面域标量 → 顶点域(面积加权平均),纯计算,返回 numpy 数组。

    NaN/inf 防护:场数据含 NaN/inf 时(规则 bug 或手工编辑)清为有限值,
    防止 NaN 写入顶点色(视口全黑)或 RD_disp(GN 位移把顶点推到无穷远,
    物体消失)。
    """
    import bmesh
    face_values = np.nan_to_num(np.asarray(face_values, dtype=np.float64),
                                nan=0.0, posinf=1e30, neginf=-1e30)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    face_areas = np.array([f.calc_area() for f in bm.faces], dtype=np.float64)
    vert_accum = {}
    for i, face in enumerate(bm.faces):
        if i >= len(face_values):
            break
        for loop in face.loops:
            v = loop.vert.index
            if v not in vert_accum:
                vert_accum[v] = [0.0, 0.0]
            vert_accum[v][0] += float(face_values[i]) * float(face_areas[i])
            vert_accum[v][1] += float(face_areas[i])
    n_verts = len(bm.verts)
    vals = np.zeros(n_verts, dtype=np.float32)
    for v, (ws, w) in vert_accum.items():
        vals[v] = ws / max(w, 1e-9)
    bm.free()
    return vals


def write_displacement(obj, face_values, attr_name="RD_disp", strength=0.1):
    """面域标量 → 顶点位移(沿法线方向)。返回顶点偏移量数组。F9:收敛到公共函数。"""
    import bpy
    mesh = obj.data
    # 面域→顶点域面积加权平均(公共函数,去内联循环)
    vals = _face_to_vertex_values(obj, face_values)
    # 写命名属性(GN 用),不直接改顶点(可逆);A4 修复:复用不重建
    if attr_name in mesh.attributes:
        attr = mesh.attributes[attr_name]
        if attr.domain != "POINT" or attr.data_type != "FLOAT":
            mesh.attributes.remove(attr)
            attr = mesh.attributes.new(name=attr_name, type="FLOAT", domain="POINT")
    else:
        attr = mesh.attributes.new(name=attr_name, type="FLOAT", domain="POINT")
    # N7/F9 修复:固定值域归一化(避免每帧 min/max 漂移)
    fixed = np.clip(vals, 0.0, 0.5) / 0.5
    for i in range(min(len(attr.data), len(fixed))):
        attr.data[i].value = float(fixed[i] * strength)
    return fixed * strength


def check_density(obj, cv_threshold=0.5):
    """密度检测:面面积变异系数。返回 (cv, uniform_ok, areas)。"""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    areas = np.array([f.calc_area() for f in bm.faces], dtype=np.float32)
    bm.free()
    if len(areas) == 0 or areas.mean() <= 1e-12:
        return 0.0, True, areas
    cv = float(areas.std() / areas.mean())
    return cv, cv <= cv_threshold, areas


def suggest_remesh(obj, cv_threshold=0.5):
    """密度检测:返回是否需要重网格化及建议。"""
    cv, ok, areas = check_density(obj, cv_threshold)
    if ok:
        return False, None
    msg = (f"网格密度不均(CV={cv:.2f} > {cv_threshold})。"
           f"建议先执行 Voxel Remesh 获得均匀网格,再运行反应扩散。")
    return True, msg


# A5 修复:密度检测结果缓存(面板每次 draw 不重建 bmesh)
_density_cache = {}


def suggest_remesh_cached(obj, cv_threshold=0.5, force=False):
    """带缓存的密度检测。缓存键 = 对象名 + 顶点数 + 面数 + 阈值(网格改动后失效)。"""
    mesh = getattr(obj, "data", None)
    if mesh is None:
        return False, None
    key = (obj.name, len(mesh.vertices), len(mesh.polygons), cv_threshold)
    if not force and key in _density_cache:
        return _density_cache[key]
    result = suggest_remesh(obj, cv_threshold)
    _density_cache[key] = result
    return result


def clear_density_cache():
    """unregister 时清空缓存(F13)。"""
    _density_cache.clear()
