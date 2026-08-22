# -*- coding: utf-8 -*-
"""Field 抽象:规则网格与非规则网格(mesh)。净室实现。"""
from __future__ import annotations
import numpy as np
from collections import defaultdict


class RegularGridField:
    """2D 规则网格标量场(单化学)。3D 体素为二期。"""

    def __init__(self, shape=(256, 256), wrap=False, dtype=np.float32):
        self.shape = tuple(shape)
        self.wrap = wrap
        self.dtype = dtype
        self.data = np.zeros(shape, dtype=dtype)

    def copy(self):
        f = RegularGridField(self.shape, self.wrap, self.dtype)
        f.data = self.data.copy()
        return f


def build_face_adjacency(faces: np.ndarray, kind: str = "vertex"):
    """从三角面片构建面级邻接表(稠密 K 列平铺)。

    faces: (F, 3) int32 顶点索引
    kind: "vertex" 共享顶点的面互为邻居(VERTEX_NEIGHBORS 语义);
          "edge"   共享边的面互为邻居
    返回 (nbr_idx (F,K) int32, nbr_w (F,K) float32, max_k, avg_k)
    - 权重 1/度按行归一化(Σw=1)
    - 不足 K 的槽位填 (自身索引, 权重 0),防 NaN
    净室说明:邻接语义来自图论标准定义,无 Ready 代码依赖。
    """
    F = faces.shape[0]
    if F == 0:
        # 审查修复:空 mesh 守卫,返回空邻接表
        return (np.empty((0, 1), dtype=np.int32),
                np.zeros((0, 1), dtype=np.float32), 1, 0.0)
    v2f = defaultdict(list)
    for i in range(F):
        for v in faces[i]:
            v2f[int(v)].append(i)
    # 收集每面的邻居(去重,排除自身)
    neighbors: list[set] = [set() for _ in range(F)]
    if kind == "vertex":
        for i in range(F):
            s = neighbors[i]
            for v in faces[i]:
                for j in v2f[int(v)]:
                    if j != i:
                        s.add(j)
    elif kind == "edge":
        def edge_key(a, b):
            return (a, b) if a < b else (b, a)
        e2f = defaultdict(list)
        for i in range(F):
            f = faces[i]
            for k in range(3):
                e2f[edge_key(int(f[k]), int(f[(k + 1) % 3]))].append(i)
        for e, fl in e2f.items():
            for i in fl:
                for j in fl:
                    if j != i:
                        neighbors[i].add(j)
    else:
        raise ValueError("kind must be 'vertex' or 'edge'")
    max_k = max((len(s) for s in neighbors), default=1)
    nbr_idx = np.empty((F, max_k), dtype=np.int32)
    nbr_w = np.zeros((F, max_k), dtype=np.float32)
    k_sum = 0
    for i in range(F):
        s = sorted(neighbors[i])
        k_sum += len(s)
        for t, j in enumerate(s):
            nbr_idx[i, t] = j
        w = 1.0 / max(len(s), 1e-5)
        for t in range(len(s)):
            nbr_w[i, t] = w
        for t in range(len(s), max_k):   # 填充槽位:自环零权重
            nbr_idx[i, t] = i
            nbr_w[i, t] = 0.0
    return nbr_idx, nbr_w, max_k, (k_sum / F)


class MeshField:
    """非规则网格(三角面片)标量场,状态在面(cell)域。"""

    def __init__(self, faces: np.ndarray, kind: str = "vertex", dtype=np.float32):
        self.faces = np.ascontiguousarray(faces, dtype=np.int32)
        self.kind = kind
        self.dtype = dtype
        self.nbr_idx, self.nbr_w, self.max_k, self.avg_k = build_face_adjacency(self.faces, kind)
        self.data = np.zeros(self.faces.shape[0], dtype=dtype)

    def copy(self):
        f = MeshField.__new__(MeshField)
        f.faces = self.faces
        f.kind = self.kind
        f.dtype = self.dtype
        f.nbr_idx, f.nbr_w, f.max_k, f.avg_k = self.nbr_idx, self.nbr_w, self.max_k, self.avg_k
        f.data = self.data.copy()
        return f
