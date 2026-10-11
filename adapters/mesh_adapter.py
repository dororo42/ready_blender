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
      max_k, avg_k, n_verts
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
    # 注入预计算邻接:MeshField 默认会再构建一遍(大网格初始化时间 ×2)
    mf = MeshField(faces, kind, adjacency=(nbr_idx, nbr_w, max_k, avg_k))
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
    # foreach_set 批量写(逐顶点 .color 赋值是 RD 预览的主要 CPU 瓶颈之一)
    rgba = np.empty((len(norm), 4), dtype=np.float32)
    rgba[:, 0] = norm
    rgba[:, 1] = norm * 0.6
    rgba[:, 2] = 1.0 - norm
    rgba[:, 3] = 1.0
    n = min(len(layer.data), len(rgba))
    layer.data.foreach_set("color", rgba[:n].ravel())
    return vals


def write_named_attribute(obj, face_values, attr_name="RD_value", domain="FACE"):
    """面域标量 → 命名属性(GN 可读)。

    修复说明(鹰眼审查):
    - FACE 域:face_values 按三角化面索引给出,但 mesh 的 FACE 属性长度 = 原始多边形数;
      必须把三角化子面映射回原始多边形(按中心点所属),不能直接按索引截断。
    - 属性已存在时复用,不删除重建(避免破坏 GN 引用与每 tick 属性重建开销)。
    - POINT 域:面积加权平均直接写入,不再建临时顶点色层。
    - 拓扑映射经 _tri_topo 缓存 + numpy 散射(原 bmesh+双层 Python 循环每帧重建)。
    """
    import bpy
    mesh = obj.data
    if domain == "FACE":
        loops_v, tri2poly, n_verts = _tri_topo(obj)
        # NaN/inf 防护(与 _face_to_vertex_values 同口径):坏数据不再进入属性
        tri_values = np.nan_to_num(np.asarray(face_values, dtype=np.float64),
                                   nan=0.0, posinf=1e30, neginf=-1e30)
        n_polys = len(mesh.polygons)
        t = min(len(tri_values), len(tri2poly))
        accum = np.zeros(n_polys, dtype=np.float64)
        counts = np.zeros(n_polys, dtype=np.int32)
        np.add.at(accum, tri2poly[:t], tri_values[:t])
        np.add.at(counts, tri2poly[:t], 1)
        vals = np.zeros(n_polys, dtype=np.float32)
        np.divide(accum, np.maximum(counts, 1), out=vals)
    elif domain == "POINT":
        vals = _face_to_vertex_values(obj, face_values)
    else:
        raise ValueError(f"unsupported domain {domain}")
    # 复用或创建属性(不重建)
    if attr_name not in mesh.attributes:
        mesh.attributes.new(name=attr_name, type="FLOAT", domain=domain)
    attr = mesh.attributes[attr_name]
    n = min(len(attr.data), len(vals))
    attr.data.foreach_set("value", vals[:n].astype(np.float32))
    return attr


# 拓扑快照缓存(纯拓扑量与场数据无关,按 (mesh 名, 顶点数, 多边形数) 失效;
# 面积不缓存——由顶点坐标现算,顶点移动(雕塑)后权重自动跟随)
_topo_snap_cache = {}


def _tri_topo(obj):
    """三角化拓扑快照(带缓存):返回 (loops_v (T,3) int32, tri2poly (T,) int32, n_verts)。

    tri2poly 把三角化子面映射回原始多边形索引。注意:必须在 bmesh.faces.index_update()
    之前取 face_map 的原面索引——index_update 会按三角化后的顺序重编所有活面索引,
    混合多边形网格(含四边/n-gon)下原 index 会被覆盖,导致映射错位。
    """
    import bmesh
    mesh = obj.data
    key = (mesh.name, len(mesh.vertices), len(mesh.polygons))
    hit = _topo_snap_cache.get(key)
    if hit is not None:
        return hit
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.index_update()
    ret = bmesh.ops.triangulate(bm, faces=bm.faces[:])
    face_map = ret.get("face_map", {})
    tri2poly = np.empty(len(bm.faces), dtype=np.int32)
    loops = []
    for fi, f in enumerate(bm.faces):
        orig = face_map.get(f)
        tri2poly[fi] = orig.index if orig is not None else f.index
        for loop in f.loops:
            loops.append(loop.vert.index)
    n_verts = len(bm.verts)
    bm.free()
    snap = (np.array(loops, dtype=np.int32).reshape(-1, 3), tri2poly, n_verts)
    _topo_snap_cache[key] = snap
    return snap


def clear_topo_cache():
    """清空拓扑快照缓存(unregister / 网格对象删除时调用)。"""
    _topo_snap_cache.clear()


def _tri_areas(mesh, loops_v):
    """三角面积(由顶点坐标现算,不建 bmesh;顶点移动后自动更新)。"""
    co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    v0 = co[loops_v[:, 0]]
    v1 = co[loops_v[:, 1]]
    v2 = co[loops_v[:, 2]]
    return 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1).astype(np.float64)


def _face_to_vertex_values(obj, face_values):
    """面域标量 → 顶点域(面积加权平均),纯计算,返回 numpy 数组。

    NaN/inf 防护:场数据含 NaN/inf 时(规则 bug 或手工编辑)清为有限值,
    防止 NaN 写入顶点色(视口全黑)或 RD_disp(GN 位移把顶点推到无穷远,
    物体消失)。
    """
    mesh = obj.data
    loops_v, _tri2poly, n_verts = _tri_topo(obj)
    face_values = np.nan_to_num(np.asarray(face_values, dtype=np.float64),
                                nan=0.0, posinf=1e30, neginf=-1e30)
    t = min(len(face_values), loops_v.shape[0])
    tri_areas = _tri_areas(mesh, loops_v[:t])
    w = face_values[:t] * tri_areas                       # (T,) 值×面积
    flat_v = loops_v[:t].reshape(-1)                      # 3T 顶点索引
    vert_vals = np.zeros(n_verts, dtype=np.float64)
    vert_ws = np.zeros(n_verts, dtype=np.float64)
    np.add.at(vert_vals, flat_v, np.repeat(w, 3))
    np.add.at(vert_ws, flat_v, np.repeat(tri_areas, 3))
    vals = vert_vals / np.maximum(vert_ws, 1e-9)
    return vals.astype(np.float32)


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
    n = min(len(attr.data), len(fixed))
    attr.data.foreach_set("value", (fixed[:n] * strength).astype(np.float32))
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
