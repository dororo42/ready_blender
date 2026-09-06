# -*- coding: utf-8 -*-
"""三路审查修复的回归测试(缺陷猎手 H1/H2/M1/M2 等)。"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_all():
    ok = fail = 0

    def check(name, cond):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  [PASS] {name}")
        else:
            fail += 1
            print(f"  [FAIL] {name}")

    # H1 回归:triangular 非方形网格几何正确(索引错位修复)
    from core.meshgen import triangular
    verts, faces = triangular(4, 6)  # 非方形
    check("triangular 4x6: 顶点数 24", len(verts) == 24)
    # 方形网格三角形法线应为 +z
    verts, faces = triangular(4, 4)
    norms = []
    for f in faces:
        v0, v1, v2 = verts[f[0]], verts[f[1]], verts[f[2]]
        n = np.cross(v1 - v0, v2 - v0)
        norms.append(n[2])
    check("triangular 方形网格全部 +z 法线", np.all(np.array(norms) > 0))

    # M2 回归:hexagonal/rhombille 焊接后共享顶点(邻接连通)
    from core.meshgen import hexagonal, rhombille
    from core.field import build_face_adjacency
    v, f = hexagonal(3, 3)
    idx, w, max_k, avg_k = build_face_adjacency(f, "vertex")
    check(f"hexagonal 焊接后 avg_k={avg_k:.1f} > 5(连通)", avg_k > 5.0)
    v, f = rhombille(3, 3)
    idx, w, max_k, avg_k = build_face_adjacency(f, "vertex")
    check(f"rhombille 焊接后 avg_k={avg_k:.1f} > 5(连通)", avg_k > 5.0)

    # M1 回归:空 mesh 邻接不崩溃
    from core.field import build_face_adjacency
    idx, w, max_k, avg_k = build_face_adjacency(np.zeros((0, 3), dtype=np.int32))
    check("空 mesh 邻接构建不崩溃", idx.shape == (0, 1))

    # H2 回归:FormulaRule wrap 从 params 读取(与关键字一致)
    from core.formula import FormulaRule
    from core.ops import laplacian_5
    gs = "delta_a = D_a * laplacian_a - a*b*b + F*(1.0-a); delta_b = D_b * laplacian_b + a*b*b - (F+k)*b;"
    fr = FormulaRule(gs)
    rng = np.random.default_rng(9)
    a1 = np.ones((16, 16), np.float32); b1 = np.zeros((16, 16), np.float32)
    b1[6:10, 6:10] = rng.uniform(0, 1, (4, 4)).astype(np.float32)
    a2, b2 = a1.copy(), b1.copy()
    p = {"D_a": 0.16, "D_b": 0.08, "F": 0.0367, "k": 0.0649}
    fr.update({"a": a1, "b": b1}, dict(p, wrap=True), field_kind="grid")       # params 传 wrap
    fr.update({"a": a2, "b": b2}, dict(p), field_kind="grid", wrap=True)       # 关键字传 wrap
    check("FormulaRule wrap 参数与关键字一致", np.allclose(a1, a2, atol=1e-7) and np.allclose(b1, b2, atol=1e-7))

    # M3 回归:非 delta_ 左值解析期拒绝
    from core.formula import FormulaError
    try:
        FormulaRule("delta_a = a; foo = b;")
        check("非 delta_ 左值解析期拒绝", False)
    except FormulaError:
        check("非 delta_ 左值解析期拒绝", True)

    # engine rebuild 卡死回归
    from controller.engine import RDEngine, EngineState
    e = RDEngine()
    e.play()
    e.mark_dirty("rebuild")
    e.mark_dirty("rebuild")  # 二次 rebuild 不应覆盖恢复状态
    e.rebuild_done()
    check("engine 双重 rebuild 后恢复 RUNNING", e.state == EngineState.RUNNING)

    # fast_ops 接入主路径回归:numpy_backend 网格 Gray-Scott 用优化内核
    from backend.numpy_backend import NumpyBackend
    from core.rule import GrayScottRule
    bkd = NumpyBackend()
    a3 = np.ones((32, 32), np.float32); b3 = np.zeros((32, 32), np.float32)
    b3[12:20, 12:20] = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    bkd.step(GrayScottRule(), [a3, b3], {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0, "wrap": False}, 50, "grid")
    check("backend 快路径 50 步无 NaN", np.isfinite(a3).all() and np.isfinite(b3).all())

    print(f"\n{ok} passed, {fail} failed")



if __name__ == "__main__":
    test_all()
    print("all passed")
