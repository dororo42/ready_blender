# -*- coding: utf-8 -*-
"""M0 单元测试(core 数值内核)。双轨运行:python -m pytest tests/ -q 或 python tests/run.py"""
import numpy as np

try:
    import pytest
except ImportError:
    pytest = None
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ops import laplacian_5, graph_laplacian
from core.rule import GrayScottRule
from core.field import RegularGridField, MeshField, build_face_adjacency
from core.initial import uniform_noise


def test_laplacian_constant_zero():
    u = np.ones((16, 16), dtype=np.float32)
    lap = laplacian_5(u, wrap=False)
    assert np.allclose(lap, 0.0, atol=1e-6)


def test_laplacian_linear_zero():
    x = np.arange(16, dtype=np.float32)[None, :] * np.ones((16, 1), dtype=np.float32)
    assert np.allclose(laplacian_5(x, wrap=False)[2:-2, 2:-2], 0.0, atol=1e-5)


def test_laplacian_peak():
    u = np.zeros((16, 16), dtype=np.float32)
    u[8, 8] = 4.0
    lap = laplacian_5(u)
    assert lap[8, 8] == -16.0
    assert lap[7, 8] == 4.0
    assert lap[8, 9] == 4.0


def test_wrap_vs_clamp_differ():
    u = np.zeros((16, 16), dtype=np.float32)
    u[0, 8] = 1.0
    lap_c = laplacian_5(u, wrap=False)
    lap_w = laplacian_5(u, wrap=True)
    assert not np.allclose(lap_c, lap_w)


def test_adjacency_vertex_triangle_grid():
    # 2x2 顶点三角化平面(8 个三角面),共享顶点邻接
    verts = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)]
    faces = np.array([[0, 1, 4], [0, 4, 3], [1, 2, 5], [1, 5, 4]], dtype=np.int32)
    idx, w, max_k, avg_k = build_face_adjacency(faces, kind="vertex")
    assert idx.shape[1] == max_k
    assert avg_k > 0
    for i in range(len(faces)):
        row = idx[i]
        # 活跃邻居(权重>0)不应含自身;自身仅允许出现在零权重填充槽位(见下)
        act = {row[t] for t in range(len(row)) if w[i, t] != 0.0}
        assert i not in act
        assert abs(w[i].sum() - 1.0) < 1e-5
        for t in range(len(row)):
            if w[i, t] == 0.0:
                assert idx[i, t] == i  # 填充槽位是自环零权重


def test_adjacency_edge_sharing():
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    idx, w, max_k, avg_k = build_face_adjacency(faces, kind="edge")
    assert set(idx[0].tolist()) == {1}
    assert set(idx[1].tolist()) == {0}


def test_graph_laplacian_constant_zero():
    faces = np.array([[0, 1, 4], [0, 4, 3], [1, 2, 5], [1, 5, 4]], dtype=np.int32)
    idx, w, max_k, avg_k = build_face_adjacency(faces)
    u = np.ones(len(faces), dtype=np.float32)
    lap = graph_laplacian(u, idx, w)
    assert np.allclose(lap, 0.0, atol=1e-6)


def test_gray_scott_grid_runs_no_nan():
    rng = np.random.default_rng(42)
    shape = (128, 128)
    a = np.ones(shape, dtype=np.float32)
    b = np.zeros(shape, dtype=np.float32)
    b[56:72, 56:72] = rng.uniform(0, 1, (16, 16)).astype(np.float32)
    params = {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0, "wrap": False}
    rule = GrayScottRule()
    for _ in range(500):
        rule.update([a, b], params, 1.0, "grid")
    assert np.isfinite(a).all() and np.isfinite(b).all()
    assert b.std() > 0.01  # 斑图已形成(结构增长)


def test_gray_scott_mesh_runs_no_nan():
    rng = np.random.default_rng(7)
    # 10x10 顶点三角化平面
    n = 12
    verts = [(i, j) for j in range(n) for i in range(n)]
    faces = []
    for j in range(n - 1):
        for i in range(n - 1):
            p = j * n + i
            faces.append([p, p + 1, p + n + 1])
            faces.append([p, p + n + 1, p + n])
    faces = np.array(faces, dtype=np.int32)
    mf = MeshField(faces)
    a = np.ones(mf.data.shape, dtype=np.float32)
    b = np.zeros(mf.data.shape, dtype=np.float32)
    sel = rng.random(mf.data.shape[0]) < 0.05
    b[sel] = rng.uniform(0, 1, sel.sum()).astype(np.float32)
    params = {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0}
    rule = GrayScottRule()
    for _ in range(300):
        rule.update([a, b], params, 1.0, "mesh", nbr=(mf.nbr_idx, mf.nbr_w))
    assert np.isfinite(a).all() and np.isfinite(b).all()


def test_mass_bounds():
    shape = (64, 64)
    a = np.ones(shape, dtype=np.float32)
    b = np.zeros(shape, dtype=np.float32)
    b[28:36, 28:36] = 0.5
    params = {"Du": 0.16, "Dv": 0.08, "F": 0.05, "k": 0.063, "dt": 1.0, "wrap": False}
    rule = GrayScottRule()
    for _ in range(200):
        rule.update([a, b], params, 1.0, "grid")
    assert (a >= 0).all() and (b >= 0).all()
    assert a.max() <= 1.5 and b.max() <= 2.0
