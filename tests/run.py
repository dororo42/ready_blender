# -*- coding: utf-8 -*-
"""纯 Python 测试运行器(不依赖 pytest)。"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ops import laplacian_5, graph_laplacian
from core.rule import GrayScottRule
from core.field import RegularGridField, MeshField, build_face_adjacency
from core.initial import uniform_noise
import numpy as np

tests = []

def test(name):
    def d(fn):
        tests.append((name, fn))
        return fn
    return d

@test("laplacian 5-point: constant field → zero")
def t1():
    u = np.ones((16, 16), dtype=np.float32)
    lap = laplacian_5(u, wrap=False)
    assert np.allclose(lap, 0.0, atol=1e-6)

@test("laplacian 5-point: linear field → zero (interior)")
def t2():
    x = np.arange(16, dtype=np.float32)[None, :] * np.ones((16, 1), dtype=np.float32)
    lap = laplacian_5(x, wrap=False)
    assert np.allclose(lap[2:-2, 2:-2], 0.0, atol=1e-5)

@test("laplacian 5-point: peak value correct")
def t3():
    u = np.zeros((16, 16), dtype=np.float32)
    u[8, 8] = 4.0
    lap = laplacian_5(u)
    assert abs(lap[8, 8] + 16.0) < 1e-6
    assert abs(lap[7, 8] - 4.0) < 1e-6

@test("laplacian wrap vs clamp differ")
def t4():
    u = np.zeros((16, 16), dtype=np.float32)
    u[0, 8] = 1.0
    assert not np.allclose(laplacian_5(u, False), laplacian_5(u, True))

@test("adjacency vertex: construction, weight normalization, self-loop filling")
def t5():
    faces = np.array([[0, 1, 4], [0, 4, 3], [1, 2, 5], [1, 5, 4]], dtype=np.int32)
    idx, w, max_k, avg_k = build_face_adjacency(faces, "vertex")
    for i in range(len(faces)):
        assert abs(w[i].sum() - 1.0) < 1e-5
        for t in range(max_k):
            if w[i, t] == 0.0:
                assert idx[i, t] == i

@test("adjacency edge: 2 triangles sharing edge are neighbors")
def t6():
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    idx, w, max_k, avg_k = build_face_adjacency(faces, "edge")
    assert max_k == 1, f"expected max_k=1, got {max_k}"
    assert avg_k == 1.0, f"expected avg_k=1.0, got {avg_k}"
    assert 1 in set(idx[0, :max_k].tolist())
    assert 0 in set(idx[1, :max_k].tolist())

@test("graph laplacian: constant field → zero")
def t7():
    faces = np.array([[0, 1, 4], [0, 4, 3], [1, 2, 5], [1, 5, 4]], dtype=np.int32)
    idx, w, _, _ = build_face_adjacency(faces)
    u = np.ones(len(faces), dtype=np.float32)
    lap = graph_laplacian(u, idx, w)
    assert np.allclose(lap, 0.0, atol=1e-6)

@test("Gray-Scott grid: runs 500 steps, no NaN, pattern emerges")
def t8():
    rng = np.random.default_rng(42)
    a = np.ones((128, 128), dtype=np.float32)
    b = np.zeros((128, 128), dtype=np.float32)
    b[56:72, 56:72] = rng.uniform(0, 1, (16, 16)).astype(np.float32)
    p = {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0, "wrap": False}
    rule = GrayScottRule()
    for _ in range(500):
        rule.update([a, b], p, 1.0, "grid")
    assert np.isfinite(a).all() and np.isfinite(b).all()
    assert b.std() > 0.01  # pattern formed

@test("Gray-Scott mesh: runs 300 steps, no NaN, pattern emerges")
def t9():
    rng = np.random.default_rng(7)
    n = 12
    faces = []
    for j in range(n-1):
        for i in range(n-1):
            p = j*n+i
            faces.append([p, p+1, p+n+1])
            faces.append([p, p+n+1, p+n])
    faces = np.array(faces, dtype=np.int32)
    mf = MeshField(faces)
    a = np.ones(mf.data.shape[0], dtype=np.float32)
    b = np.zeros(mf.data.shape[0], dtype=np.float32)
    sel = rng.random(len(a)) < 0.05
    b[sel] = rng.uniform(0, 1, sel.sum()).astype(np.float32)
    p = {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0}
    rule = GrayScottRule()
    for _ in range(300):
        rule.update([a, b], p, 1.0, "mesh", nbr=(mf.nbr_idx, mf.nbr_w))
    assert np.isfinite(a).all() and np.isfinite(b).all()
    assert b.std() > 0.01

@test("Gray-Scott mass bounds: values stay in reasonable range")
def t10():
    a = np.ones((64, 64), dtype=np.float32)
    b = np.zeros((64, 64), dtype=np.float32)
    b[28:36, 28:36] = 0.5
    p = {"Du": 0.16, "Dv": 0.08, "F": 0.05, "k": 0.063, "dt": 1.0, "wrap": False}
    rule = GrayScottRule()
    for _ in range(200):
        rule.update([a, b], p, 1.0, "grid")
    assert (a >= 0).all() and (b >= 0).all()
    assert a.max() <= 1.5 and b.max() <= 2.0

if __name__ == "__main__":
    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {len(tests)}")
    sys.exit(1 if failed else 0)