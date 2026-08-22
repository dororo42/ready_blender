# -*- coding: utf-8 -*-
"""Numba 后端验证:回退语义 + 数值同源(与 core.vertex_rd 一致)。"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.vertex_rd import faces_to_edges, build_edge_graph, find_boundary_verts, sparse_seeds, rd_step_vertex
from backend.numba_backend import run_vertex_rd_numba, NUMBA_AVAILABLE, numba_status

# 20x20 三角化平面
n = 20
faces = []
for j in range(n - 1):
    for i in range(n - 1):
        p = j * n + i
        faces.append([p, p + 1, p + n + 1])
        faces.append([p, p + n + 1, p + n])
faces = np.array(faces, np.int32)
nv = n * n
edges = faces_to_edges(faces)
v1, v2, deg = build_edge_graph(nv, edges)
bd = find_boundary_verts(nv, faces)

print(f"[INFO] NUMBA_AVAILABLE={NUMBA_AVAILABLE} | {numba_status()[1]}")

# 双路径数值一致性(50 步)
rng1 = np.random.default_rng(7)
U1 = np.ones(nv, np.float32); V1 = sparse_seeds(nv, 0.05, bd, rng1)
for _ in range(50):
    rd_step_vertex(U1, V1, v1, v2, deg, bd, 0.16, 0.08, 0.0367, 0.0649, 1.0)

rng2 = np.random.default_rng(7)
U2 = np.ones(nv, np.float32); V2 = sparse_seeds(nv, 0.05, bd, rng2)
run_vertex_rd_numba(U2, V2, v1, v2, deg, bd, 0.16, 0.08, 0.0367, 0.0649, 1.0, 50)

same = np.allclose(U1, U2, atol=1e-6) and np.allclose(V1, V2, atol=1e-6)
print(f"[{'PASS' if same else 'FAIL'}] numpy 路径与 numba_backend 50 步数值一致 (max|dU|={np.abs(U1-U2).max():.2e}, max|dV|={np.abs(V1-V2).max():.2e})")
bd_ok = (U2[bd] > 0.999).all() and (V2[bd] < 1e-6).all()
print(f"[{'PASS' if bd_ok else 'FAIL'}] numba_backend 边界 Dirichlet 保持")
finite = np.isfinite(U2).all() and np.isfinite(V2).all()
print(f"[{'PASS' if finite else 'FAIL'}] numba_backend 无 NaN")
sys.exit(0 if (same and bd_ok and finite) else 1)
