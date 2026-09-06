# -*- coding: utf-8 -*-
"""3D 网格扩展测试:Orientation/Flow 纯函数 + rule mesh 路径生效 + 零回归。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from core.vertex_rd import (orientation_vectors_3d, velocity_field_3d,
                            aniso_edge_weights, advect_mesh,
                            faces_to_edges, build_edge_graph)
from core.rule import GrayScottRule


def make_plane(nx=8, ny=8):
    """平面网格:顶点 (nx*ny,3),三角面,边图 + 稠密 K 列 nbr(均匀权重 1/度)。"""
    xs, ys = np.meshgrid(np.arange(nx), np.arange(ny))
    verts = np.stack([xs.ravel(), ys.ravel(), np.zeros(nx * ny)], axis=1).astype(np.float32)
    faces = []
    for y in range(ny - 1):
        for x in range(nx - 1):
            a = y * nx + x
            faces.append([a, a + 1, a + nx])
            faces.append([a + 1, a + nx + 1, a + nx])
    faces = np.array(faces, dtype=np.int32)
    edges = faces_to_edges(faces)
    v1, v2, degrees = build_edge_graph(len(verts), edges)
    n = len(verts)
    degs = np.zeros(n, dtype=np.int32)
    for a, b in zip(v1, v2):
        degs[a] += 1
        degs[b] += 1
    K = int(degs.max())
    nbr_idx = np.full((n, K), -1, dtype=np.int32)
    nbr_w = np.zeros((n, K), dtype=np.float32)
    cnt = np.zeros(n, dtype=np.int32)
    for a, b in zip(v1, v2):
        nbr_idx[a, cnt[a]] = b
        nbr_w[a, cnt[a]] = 1.0 / degs[a]
        cnt[a] += 1
        nbr_idx[b, cnt[b]] = a
        nbr_w[b, cnt[b]] = 1.0 / degs[b]
        cnt[b] += 1
    # 填充槽:自身索引 + 0 权重
    for i in range(n):
        for k in range(cnt[i], K):
            nbr_idx[i, k] = i
            nbr_w[i, k] = 0.0
    return verts, (nbr_idx, nbr_w), degrees


def test_orientation_vectors():
    verts, _, _ = make_plane()
    for kind in ("linear", "horizontal", "radial", "circles", "swirl", "bubble"):
        d = orientation_vectors_3d(verts, kind)
        assert d.shape == (len(verts), 3)
        assert np.allclose(np.linalg.norm(d, axis=1), 1.0, atol=1e-5), kind
    d = orientation_vectors_3d(verts, "linear")
    assert np.allclose(d, [0, 1, 0])
    d = orientation_vectors_3d(verts, "horizontal")
    assert np.allclose(d, [1, 0, 0])


def test_velocity_field_bounded():
    verts, _, _ = make_plane()
    for kind in ("vertical", "radial", "rotate", "swirl", "bubble", "ring", "vortex"):
        v = velocity_field_3d(verts, kind, 0.5)
        assert v.shape == (len(verts), 3)
        assert np.isfinite(v).all(), kind
        assert np.abs(v).max() < 1.0, kind


def test_aniso_weights_normalized():
    verts, (idx, w0), _ = make_plane()
    # α=0 → 与原权重一致
    d = orientation_vectors_3d(verts, "radial")
    w0a = aniso_edge_weights(idx, w0, verts, d, 0.0)
    assert np.allclose(w0a, w0, atol=1e-6)
    # α>0 → 权重改变且行和=1(有效邻居),填充槽=0
    w1 = aniso_edge_weights(idx, w0, verts, d, 0.8)
    assert not np.allclose(w1, w0)
    n = len(verts)
    self_mask = idx == np.arange(n)[:, None]
    assert np.allclose(w1[self_mask], 0.0)
    assert np.allclose(w1.sum(axis=1), 1.0, atol=1e-4)


def test_advect_constant_identity():
    verts, (idx, _), _ = make_plane()
    u = np.ones(len(verts), np.float32)
    v = velocity_field_3d(verts, "rotate", 0.5)
    advect_mesh(u, verts, v, 1.0, idx)
    assert np.allclose(u, 1.0)


def test_advect_moves_pattern():
    verts, (idx, _), _ = make_plane()
    u = np.zeros(len(verts), np.float32)
    u[5 * 8 + 4] = 1.0  # 中心一点
    v = velocity_field_3d(verts, "vertical", 0.9)  # 向上
    advect_mesh(u, verts, v, 1.0, idx)
    assert u[5 * 8 + 4] == 0.0  # 原点被移走(回溯向下取到下方邻居)
    assert float(u.sum()) == 1.0  # 质量保持(最近邻交换)


def test_rule_mesh_orientation_changes_output():
    verts, nbr, _ = make_plane()
    r = GrayScottRule()
    rng = np.random.default_rng(3)
    def fresh():
        a = np.ones(len(verts), np.float32)
        b = np.zeros(len(verts), np.float32)
        b[rng.integers(0, len(verts), 8)] = 1.0
        return [a, b]
    p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0,
             mesh_centers=verts, wrap=False)
    base = fresh()
    for _ in range(150):
        r.update(base, p, 1.0, field_kind="mesh", nbr=nbr)
    o = fresh()
    po = dict(p, orientation_kind="radial", orientation_strength=0.8)
    for _ in range(150):
        r.update(o, po, 1.0, field_kind="mesh", nbr=nbr)
    diff = float(np.abs(o[1] - base[1]).max())
    assert diff > 1e-4, f"Orientation 未生效: {diff:.2e}"
    assert np.isfinite(o[0]).all() and np.isfinite(o[1]).all()


def test_rule_mesh_flow_changes_output():
    verts, nbr, _ = make_plane()
    r = GrayScottRule()
    rng = np.random.default_rng(4)
    def fresh():
        a = np.ones(len(verts), np.float32)
        b = np.zeros(len(verts), np.float32)
        b[rng.integers(0, len(verts), 8)] = 1.0
        return [a, b]
    p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0,
             mesh_centers=verts, wrap=False)
    base = fresh()
    for _ in range(120):
        r.update(base, p, 1.0, field_kind="mesh", nbr=nbr)
    f = fresh()
    pf = dict(p, flow_kind="vortex", flow_strength=0.6)
    for _ in range(120):
        r.update(f, pf, 1.0, field_kind="mesh", nbr=nbr)
    diff = float(np.abs(f[1] - base[1]).max())
    assert diff > 1e-4, f"Flow 未生效: {diff:.2e}"
    assert np.isfinite(f[0]).all() and np.isfinite(f[1]).all()


def test_rule_mesh_noext_bitwise_identical():
    """无扩展参数时与旧行为逐位一致(零回归)。"""
    verts, nbr, _ = make_plane()
    rng = np.random.default_rng(5)
    seeds = rng.integers(0, len(verts), 8)
    a = np.ones(len(verts), np.float32)
    b = np.zeros(len(verts), np.float32)
    b[seeds] = 1.0
    p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0,
             mesh_centers=verts, wrap=False,
             orientation_kind="none", orientation_strength=0.0,
             flow_kind="none", flow_strength=0.0)
    r = GrayScottRule()
    for _ in range(100):
        r.update([a, b], p, 1.0, field_kind="mesh", nbr=nbr)
    # 与显式旧路径(graph_laplacian 原权重)对照
    from core.ops import graph_laplacian
    a2 = np.ones(len(verts), np.float32)
    b2 = np.zeros(len(verts), np.float32)
    b2[seeds] = 1.0
    for _ in range(100):
        la = graph_laplacian(a2, nbr[0], nbr[1])
        lb = graph_laplacian(b2, nbr[0], nbr[1])
        abb = a2 * b2 * b2
        a2 += (0.16 * la - abb + 0.0545 * (1.0 - a2)) * 1.0
        b2 += (0.08 * lb + abb - (0.0545 + 0.062) * b2) * 1.0
        np.clip(a2, 0.0, 2.0, out=a2)
        np.clip(b2, 0.0, 1.0, out=b2)
    assert np.array_equal(a, a2) and np.array_equal(b, b2)


def test_rule_mesh_face_domain_adjacency():
    """回归(真机发现的 P1):引擎 mesh 路径状态与 nbr 都在面域,
    扩展函数必须用面中心 (F,3) 而非顶点坐标——F≠N 的网格上旧实现
    用面索引取顶点数组会越界(或静默错位)。"""
    from core.meshgen import triangular
    from core.field import build_face_adjacency
    verts, faces = triangular(24, 24)
    centers = verts[faces].mean(axis=1).astype(np.float32)
    nbr_idx, nbr_w, _, _ = build_face_adjacency(faces, "vertex")
    assert len(centers) != len(verts)  # F≠N:正是旧实现踩中的域错配
    r = GrayScottRule()
    rng = np.random.default_rng(9)
    a = np.ones(len(centers), np.float32)
    b = np.zeros(len(centers), np.float32)
    b[rng.integers(0, len(centers), 20)] = 1.0
    p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0,
             mesh_centers=centers, wrap=False,
             orientation_kind="radial", orientation_strength=0.8,
             flow_kind="vortex", flow_strength=0.5)
    for _ in range(60):
        r.update([a, b], p, 1.0, field_kind="mesh", nbr=(nbr_idx, nbr_w))
    assert np.isfinite(a).all() and np.isfinite(b).all()
    assert np.allclose(nbr_w.sum(axis=1), 1.0, atol=1e-4)  # 原邻接语义未被破坏


def test_rule_mesh_ext_cache_survives_hot_update():
    """缓存放入 params:热更新(update 只改部分键)后仍命中,拓扑重建(新 params)失效。"""
    verts, nbr, _ = make_plane()
    r = GrayScottRule()
    p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0,
             mesh_centers=verts, wrap=False,
             orientation_kind="radial", orientation_strength=0.8)
    fields = [np.ones(len(verts), np.float32), np.zeros(len(verts), np.float32)]
    for _ in range(3):
        r.update(fields, p, 1.0, field_kind="mesh", nbr=nbr)
    assert "_mesh_ext_cache" in p and "o" in p["_mesh_ext_cache"]
    w_cached = p["_mesh_ext_cache"]["o"][1]
    # 模拟面板滑块热更:仅 update 部分键,缓存键仍有效 → 权重对象复用
    p.update({"F": 0.05})
    r.update(fields, p, 1.0, field_kind="mesh", nbr=nbr)
    assert p["_mesh_ext_cache"]["o"][1] is w_cached


def test_aniso_rowsum_all_alpha_random_cloud():
    """性质:任意点云 × α∈[0,0.95],各向异性权重行和恒为 1、非负、填充槽为 0。"""
    rng = np.random.default_rng(11)
    n, k = 60, 5
    idx = np.tile(np.arange(n)[:, None], (1, k))
    for j in range(n):
        idx[j, :k - 1] = rng.permutation(n)[:k - 1]  # 混入邻居,末槽留自身填充
    nbr_w = np.full((n, k), 1.0 / k, np.float32)
    pts = rng.standard_normal((n, 3)).astype(np.float32) * 2.0
    for kind in ("linear", "radial", "swirl"):
        d = orientation_vectors_3d(pts, kind)
        for alpha in (0.0, 0.3, 0.8, 0.95):
            w = aniso_edge_weights(idx, nbr_w, pts, d, alpha)
            assert np.isfinite(w).all()
            assert (w >= 0).all()
            assert np.allclose(w.sum(axis=1), 1.0, atol=1e-4), (kind, alpha)
            self_mask = idx == np.arange(n)[:, None]
            assert np.allclose(w[self_mask], 0.0)


def test_velocity_bounded_random_cloud():
    """性质:任意点云上 7 种速度场均有限且模长有界(≤|strength|·1.5 容差)。"""
    rng = np.random.default_rng(12)
    pts = rng.standard_normal((200, 3)).astype(np.float32) * 5.0
    for kind in ("vertical", "radial", "rotate", "swirl", "bubble", "ring", "vortex"):
        v = velocity_field_3d(pts, kind, 1.0)
        assert np.isfinite(v).all(), kind
        assert np.abs(v).max() <= 1.5, (kind, float(np.abs(v).max()))


def test_stability_alpha095_dt1():
    """稳定性:α=0.95(枚举上限)+ dt=1.0,面域 300 步无 NaN/溢出(行归一化保谱)。"""
    from core.meshgen import triangular
    from core.field import build_face_adjacency
    verts, faces = triangular(20, 20)
    centers = verts[faces].mean(axis=1).astype(np.float32)
    nbr_idx, nbr_w, _, _ = build_face_adjacency(faces, "vertex")
    r = GrayScottRule()
    rng = np.random.default_rng(13)
    a = np.ones(len(centers), np.float32)
    b = np.zeros(len(centers), np.float32)
    b[rng.integers(0, len(centers), 30)] = 1.0
    p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0,
             mesh_centers=centers, wrap=False,
             orientation_kind="linear", orientation_strength=0.95,
             flow_kind="vortex", flow_strength=1.0)
    for _ in range(300):
        r.update([a, b], p, 1.0, field_kind="mesh", nbr=(nbr_idx, nbr_w))
    assert np.isfinite(a).all() and np.isfinite(b).all()
    assert float(np.abs(a).max()) < 10.0 and float(np.abs(b).max()) < 10.0


def test_advect_large_dt_stays_finite():
    """稳定性:极端 dt 的最近邻回溯不产生越界/NaN(采样域恒为 {自身}∪{邻居})。"""
    verts, (idx, _), _ = make_plane()
    u = np.random.default_rng(14).random(len(verts)).astype(np.float32)
    v = velocity_field_3d(verts, "swirl", 1.0)
    for dt in (0.0, 1.0, 50.0, 1e4):
        u2 = u.copy()
        advect_mesh(u2, verts, v, dt, idx)
        assert np.isfinite(u2).all(), dt
        assert set(np.unique(u2)).issubset(set(np.unique(u).tolist())), dt


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("mesh_ext: all passed")