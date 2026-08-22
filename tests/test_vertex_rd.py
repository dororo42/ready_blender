# -*- coding: utf-8 -*-
"""顶点域 RD 求解器回归测试(纯 Python)。"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.vertex_rd import (faces_to_edges, build_edge_graph, find_boundary_verts,
                            sparse_seeds, rd_step_vertex, run_vertex_rd)

ok = fail = 0

def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail += 1
        print(f"  [FAIL] {name}")

# 20x20 三角化平面
n = 20
faces = []
for j in range(n - 1):
    for i in range(n - 1):
        p = j * n + i
        faces.append([p, p + 1, p + n + 1])
        faces.append([p, p + n + 1, p + n])
faces = np.array(faces, dtype=np.int32)
n_verts = n * n

edges = faces_to_edges(faces)
check("唯一边数 > 0", len(edges) > 0)
v1, v2, degrees = build_edge_graph(n_verts, edges)
check("度数均值 ≈6(内部点)", abs(degrees.mean() - 6.0) < 0.5)
check("无零度(防除零)", (degrees >= 1).all())

boundary = find_boundary_verts(n_verts, faces)
check("边界顶点数 = 4n-4", int(boundary.sum()) == 4 * n - 4)

seeds = sparse_seeds(n_verts, 0.05, boundary)
check("种子只在内部", not seeds[boundary].any())
check("种子密度 ≈5%", abs(seeds.sum() / n_verts - 0.05) < 0.02)

# 300 步运行(边界保持)
U, V, b2, d2 = run_vertex_rd(n_verts, edges, faces, iterations=300,
                             preserve_boundary=True, seed_ratio=0.05)
check("300 步无 NaN", np.isfinite(U).all() and np.isfinite(V).all())
check("边界保持 U=1/V=0", (U[boundary] > 0.999).all() and (V[boundary] < 1e-6).all())
check("内部图案形成(std>0.01)", V[~boundary].std() > 0.01)
print(f"    (内部 V: min={V[~boundary].min():.3f} max={V[~boundary].max():.3f} std={V[~boundary].std():.4f})")

# 不保持边界对照
U2, V2, _, _ = run_vertex_rd(n_verts, edges, faces, iterations=300,
                             preserve_boundary=False, seed_ratio=0.05)
check("无边界保持也稳定", np.isfinite(U2).all() and np.isfinite(V2).all())

# 空网格守卫
check("空网格不崩溃", run_vertex_rd(0, np.zeros((0, 2), np.int32),
                                    np.zeros((0, 3), np.int32))[2].size == 0)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
