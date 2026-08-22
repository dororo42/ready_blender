# -*- coding: utf-8 -*-
"""顶点域反应扩散求解器(净室实现,本地可测)。

与面域(MeshRD)并列的第二种求解域:状态在网格顶点上,邻接为边图。
lap = Σ邻居 − degree·U(度加权图拉普拉斯,与外部插件同口径);
支持开放面边界 Dirichlet 保持(U=1, V=0)与稀疏均匀种子初始化。
"""
from __future__ import annotations
import numpy as np


def faces_to_edges(faces: np.ndarray):
    """三角面 → 唯一边集合。返回 (E,2) int32。"""
    edges = set()
    for f in faces:
        for k in range(3):
            a, b = int(f[k]), int(f[(k + 1) % 3])
            edges.add((a, b) if a < b else (b, a))
    return np.array(sorted(edges), dtype=np.int32)


def build_edge_graph(n_verts: int, edges: np.ndarray):
    """边图:返回 (v1, v2, degrees)。孤立点 degree 归 1 防除零。"""
    v1 = edges[:, 0].astype(np.int32)
    v2 = edges[:, 1].astype(np.int32)
    degrees = np.zeros(n_verts, dtype=np.float32)
    np.add.at(degrees, v1, 1)
    np.add.at(degrees, v2, 1)
    degrees = np.maximum(degrees, 1.0)
    return v1, v2, degrees


def find_boundary_verts(n_verts: int, faces: np.ndarray):
    """开放面边界顶点:只被一个面引用的边的两端。返回 bool 数组。"""
    edge_count = {}
    for f in faces:
        for k in range(3):
            a, b = int(f[k]), int(f[(k + 1) % 3])
            key = (a, b) if a < b else (b, a)
            edge_count[key] = edge_count.get(key, 0) + 1
    boundary = np.zeros(n_verts, dtype=bool)
    for (a, b), c in edge_count.items():
        if c <= 1:
            boundary[a] = True
            boundary[b] = True
    return boundary


def sparse_seeds(n_verts: int, ratio=0.05, boundary=None, rng=None):
    """稀疏均匀种子:约 ratio 比例顶点 V=1(边界顶点不选)。"""
    rng = rng or np.random.default_rng()
    if boundary is not None and boundary.any():
        idx = np.where(~boundary)[0]
    else:
        idx = np.arange(n_verts)
    n = max(1, int(len(idx) * ratio))
    sel = rng.choice(idx, size=min(n, len(idx)), replace=False)
    seeds = np.zeros(n_verts, dtype=np.float32)
    seeds[sel] = 1.0
    return seeds


def rd_step_vertex(U, V, v1, v2, degrees, boundary, du, dv, f, k, dt):
    """顶点域 Gray-Scott 一步(就地)。边界 Dirichlet:U=1/V=0 固定。"""
    sumU = np.zeros_like(U)
    sumV = np.zeros_like(V)
    np.add.at(sumU, v1, U[v2])
    np.add.at(sumU, v2, U[v1])
    np.add.at(sumV, v1, V[v2])
    np.add.at(sumV, v2, V[v1])
    lapU = sumU - degrees * U
    lapV = sumV - degrees * V
    reaction = U * V * V
    U += (du * lapU - reaction + f * (1.0 - U)) * dt
    V += (dv * lapV + reaction - (f + k) * V) * dt
    np.clip(U, 0.0, 1.0, out=U)
    np.clip(V, 0.0, 1.0, out=V)
    if boundary is not None and boundary.any():
        U[boundary] = 1.0
        V[boundary] = 0.0
    return U, V


def run_vertex_rd(n_verts, edges, faces, iterations=500, du=0.16, dv=0.08,
                  f=0.0545, k=0.062, dt=1.0, preserve_boundary=True,
                  seed_ratio=0.05, rng=None):
    """完整顶点域 RD:初始化 → 迭代 → 返回 (U, V, boundary, degrees)。"""
    rng = rng or np.random.default_rng()
    v1, v2, degrees = build_edge_graph(n_verts, edges)
    boundary = find_boundary_verts(n_verts, faces)
    U = np.ones(n_verts, dtype=np.float32)
    V = sparse_seeds(n_verts, seed_ratio, boundary if preserve_boundary else None, rng)
    for _ in range(iterations):
        rd_step_vertex(U, V, v1, v2, degrees,
                       boundary if preserve_boundary else None,
                       du, dv, f, k, dt)
    return U, V, boundary, degrees
