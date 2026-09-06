# -*- coding: utf-8 -*-
"""网格预处理质量模块回归测试(纯 Python 可测部分)。"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.mesh_quality import mesh_quality_report, triangulate


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

    # 1. 均匀三角网格(规则平面)→ 质量合格
    n = 20
    xs = np.arange(n, dtype=np.float32)
    xv, yv = np.meshgrid(xs, xs, indexing="xy")
    verts = np.stack([xv, yv, np.zeros_like(xv)], axis=-1).reshape(-1, 3)
    faces = []
    for j in range(n - 1):
        for i in range(n - 1):
            p = j * n + i
            faces.append([p, p + 1, p + n + 1])
            faces.append([p, p + n + 1, p + n])
    faces = np.array(faces, dtype=np.int32)
    r = mesh_quality_report(verts, faces)
    check("均匀网格 verdict=ok", r["verdict"] == "ok")
    check("均匀网格 sliver 接近 0", r["sliver_ratio"] < 0.05)
    check("均匀网格 edge_ratio ≈ 1.4", abs(r["edge_ratio"] - np.sqrt(2)) < 0.05)
    check("均匀网格 uniform_ok=True", r["uniform_ok"] is True)
    print(f"    (n_verts={r['n_verts']} n_faces={r['n_faces']} cv={r['area_cv']:.3f} sliver={r['sliver_ratio']:.3f} edge_ratio={r['edge_ratio']:.2f} density={r['face_density']:.1f} quantity_ok={r['quantity_ok']})")

    # 2. 狭长三角形网格 → 检出
    verts2 = np.array([[0,0,0],[10,0,0],[5,0.2,0],[5,5,0]], dtype=np.float32)
    faces2 = np.array([[0,1,2],[0,2,3],[1,3,2]], dtype=np.int32)
    r2 = mesh_quality_report(verts2, faces2)
    check("狭长网格检出 sliver_ratio>0.2", r2["sliver_ratio"] > 0.2)
    check("狭长网格 verdict=needs_prep", r2["verdict"] == "needs_prep")
    print(f"    (sliver={r2['sliver_ratio']:.2f} edge_ratio={r2['edge_ratio']:.1f} issues={r2['issues']})")

    # 3. 数量不足检出(大尺寸少面)
    verts3 = np.array([[0,0,0],[100,0,0],[0,100,0],[100,100,0]], dtype=np.float32)
    faces3 = np.array([[0,1,2],[1,3,2]], dtype=np.int32)
    r3 = mesh_quality_report(verts3, faces3)
    check("数量不足检出 quantity_ok=False", r3["quantity_ok"] is False)
    check("数量不足进入 issues", any("数量" in s for s in r3["issues"]))
    print(f"    (diag={r3['bbox_diag']:.1f} density={r3['face_density']:.3f} issues={r3['issues']})")

    # 4. n-gon 三角扇拆分
    quads = np.array([[0,1,2,3],[3,2,5,4]], dtype=object)
    tris = triangulate(None, quads)
    check("n-gon 拆分:2 四边形 → 4 三角形", len(tris) == 4)
    check("拆分三角形索引合法", tris.max() <= 5)

    # 5. 空网格守卫
    r4 = mesh_quality_report(np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int32))
    check("空网格 verdict=empty 不崩溃", r4["verdict"] == "empty")

    print(f"\n{ok} passed, {fail} failed")



if __name__ == "__main__":
    test_all()
    print("all passed")
