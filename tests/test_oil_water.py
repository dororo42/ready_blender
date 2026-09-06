# -*- coding: utf-8 -*-
"""Oil-Water 相分离(Agmon 2014)净室实现测试。"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.rule import OilWaterRule, _bias

# 1) bias 边界与对称性


def test_all():
    assert abs(float(_bias(np.array([0.0]))[0]) - 1.0) < 1e-12
    assert float(_bias(np.array([1000.0]))[0]) == 1000.0      # 大正无溢出
    assert float(_bias(np.array([-1000.0]))[0]) == 0.0        # 大负无溢出
    assert np.isnan(_bias(np.array([0.0, 1e3, -1e3]))).any() == False
    b1 = float(_bias(np.array([1.0]))[0])
    bm1 = float(_bias(np.array([-1.0]))[0])
    assert abs(b1 - 0.5819767 - 1.0) < 1e-6 and abs(bm1 - 0.5819767) < 1e-6  # 解析值
    print("[PASS] bias 边界: d=0→1, ±1000 无溢出, ±1 解析值正确")

    # 2) 质量守恒(逐对交换对称 → 总量不变)
    rng = np.random.default_rng(42)
    a = rng.uniform(0, 1, (64, 64)).astype(np.float32)
    b = rng.uniform(0, 1, (64, 64)).astype(np.float32)
    sa0, sb0 = float(a.sum()), float(b.sum())
    rule = OilWaterRule()
    params = {"repulsion": 0.7, "dt": 0.05, "wrap": True}
    for _ in range(200):
        rule.update([a, b], params, 0.05, "grid")
    assert abs(float(a.sum()) - sa0) < 0.05 and abs(float(b.sum()) - sb0) < 0.05
    print(f"[PASS] 质量守恒(200 步): Δa={abs(float(a.sum())-sa0):.5f} Δb={abs(float(b.sum())-sb0):.5f}")

    # 3) 相分离出现:块均值极差显著增大(初始 ~0.09 → 演化后 >0.25)
    def block_range(x, bs=16):
        n = x.shape[0] // bs
        bl = x[:n*bs, :n*bs].reshape(n, bs, n, bs).mean(axis=(1, 3))
        return float(bl.max() - bl.min())
    rng = np.random.default_rng(7)
    a2 = rng.uniform(0, 1, (128, 128)).astype(np.float32)
    b2 = rng.uniform(0, 1, (128, 128)).astype(np.float32)
    r0 = block_range(a2)
    for _ in range(600):
        rule.update([a2, b2], params, 0.05, "grid")
    r1 = block_range(a2)
    assert r1 > r0 * 2.5, f"相分离不足: {r0:.3f} → {r1:.3f}"
    print(f"[PASS] 相分离出现: 块均值极差 {r0:.3f} → {r1:.3f} ({r1/r0:.1f}x)")

    # 4) 无 NaN、值域合理(白噪声 [0,1] 演化,富集可超 1 但有界)
    assert not (np.isnan(a2).any() or np.isnan(b2).any())
    assert a2.max() < 5.0 and a2.min() >= -1e-6
    print(f"[PASS] 无 NaN,值域合理: a[{a2.min():.3f},{a2.max():.3f}] b[{b2.min():.3f},{b2.max():.3f}]")

    # 5) mesh 模式(3D 网格图邻域):质量守恒 + 相分离 + 无 NaN
    def _build_grid_adjacency(gn=16):
        """gn×gn 顶点平面网格的顶点邻接(4 邻域),构造 (idx, w) 稠密平铺。
        测试用途:与 build_face_adjacency 同构(填充槽位 idx==自身, w=0)。"""
        n = gn * gn
        max_k = 4
        idx = np.tile(np.arange(n)[:, None], (1, max_k)).astype(np.int32)
        w = np.zeros((n, max_k), dtype=np.float32)
        nbrs = []
        for v_id in range(n):
            r, c = divmod(v_id, gn)
            cand = []
            if r > 0: cand.append(v_id - gn)
            if r < gn - 1: cand.append(v_id + gn)
            if c > 0: cand.append(v_id - 1)
            if c < gn - 1: cand.append(v_id + 1)
            nbrs.append(cand)
        for v_id, cand in enumerate(nbrs):
            for t, nb in enumerate(cand):
                idx[v_id, t] = nb
                w[v_id, t] = 1.0 / max(1, len(cand))
        return idx, w, nbrs

    gidx, gw, _nbrs = _build_grid_adjacency(32)
    rng = np.random.default_rng(42)
    am = rng.uniform(0, 1, len(gidx)).astype(np.float32)
    bm = rng.uniform(0, 1, len(gidx)).astype(np.float32)
    sam0, sbm0 = float(am.sum()), float(bm.sum())
    def _block_range_1d(x, gn=32, bs=8):
        n = gn // bs
        bl = x[:n * bs * gn].reshape(n, bs * gn).mean(axis=1)
        return float(bl.max() - bl.min())
    r_m0 = _block_range_1d(am)
    for _ in range(300):
        rule.update([am, bm], params, 0.05, "mesh", nbr=(gidx, gw))
    assert not (np.isnan(am).any() or np.isnan(bm).any())
    assert abs(float(am.sum()) - sam0) < 0.05, f"mesh 质量不守恒: Δa={abs(float(am.sum())-sam0):.4f}"
    assert abs(float(bm.sum()) - sbm0) < 0.05, f"mesh 质量不守恒: Δb={abs(float(bm.sum())-sbm0):.4f}"
    r_m1 = _block_range_1d(am)
    assert r_m1 > r_m0 * 2.0, f"mesh 相分离不足: {r_m0:.3f} → {r_m1:.3f}"
    print(f"[PASS] mesh 模式(图邻域): 守恒 Δa={abs(float(am.sum())-sam0):.5f}, "
          f"相分离 {r_m0:.3f} → {r_m1:.3f} ({r_m1/r_m0:.1f}x), 无 NaN")

    # 5b) mesh 模式:nbr 缺失时明确报错
    try:
        rule.update([am, bm], params, 0.05, "mesh", nbr=None)
        ok = False
    except ValueError:
        ok = True
    assert ok
    print("[PASS] mesh 模式缺 nbr 时 ValueError")

    # 6) 确定性:同 seed 同结果
    rng = np.random.default_rng(99)
    x1 = rng.uniform(0, 1, (32, 32)).astype(np.float32)
    y1 = rng.uniform(0, 1, (32, 32)).astype(np.float32)
    rng = np.random.default_rng(99)
    x2 = rng.uniform(0, 1, (32, 32)).astype(np.float32)
    y2 = rng.uniform(0, 1, (32, 32)).astype(np.float32)
    for _ in range(50):
        rule.update([x1, y1], params, 0.05, "grid")
        rule.update([x2, y2], params, 0.05, "grid")
    assert np.allclose(x1, x2) and np.allclose(y1, y2)
    print("[PASS] 确定性: 同 seed 双跑一致")

    # 7) presets 注册完整性(第 6 系统)
    from presets.presets import get_system, SYSTEMS
    ow = get_system("oil_water")
    assert ow is not None and ow["kind"] == "oil_water"
    assert ow["params"] == {"repulsion": 0.7, "dt": 0.05}
    assert len(SYSTEMS) == 6
    print(f"[PASS] SYSTEMS 注册 6 系统,oil_water 参数文献值: {ow['params']}")

    # 8) backend 通用路径走通(签名 dt = params['dt'],无双乘)
    from backend.numpy_backend import NumpyBackend
    rng = np.random.default_rng(11)
    a3 = rng.uniform(0, 1, (32, 32)).astype(np.float32)
    b3 = rng.uniform(0, 1, (32, 32)).astype(np.float32)
    sa3 = float(a3.sum())
    nb = NumpyBackend()
    nb.step(rule, [a3, b3], params, n=20, field_kind="grid")
    assert not np.isnan(a3).any() and abs(float(a3.sum()) - sa3) < 0.05
    print("[PASS] backend 通用路径 20 步: 守恒且无 NaN(时间步无双乘)")

    # 9) 回归:细分立方体 mesh 模式稳定性(用户场景:默认立方体细分 4 次 + oil_water)
    #    修复前:顶点邻接 K=12(增益≈2D 的 2 倍)→ ~85 步值穿 0 振荡发散到 1e6
    #    → inf/NaN → 视口突然全黑;RD_disp=NaN 经 GN 位移把顶点推到无穷远,物体消失。
    #    修复后:每步正性投影(非负 + 保质量 ⇒ 有界)。
    def _build_subdiv_cube(s=16):
        """单位立方体每面 s×s 四边形网格 → 三角化,焊接重复顶点(无 bpy 依赖)。"""
        verts = {}
        faces = []

        def vid(x, y, z):
            key = (round(x, 6), round(y, 6), round(z, 6))
            if key not in verts:
                verts[key] = len(verts)
            return verts[key]

        axes = [((1, 0, 0), (0, 1, 0), (0, 0, 0)), ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                ((0, 0, 1), (0, 1, 0), (0, 0, 0)), ((0, 0, 1), (0, 1, 0), (1, 0, 0)),
                ((1, 0, 0), (0, 0, 1), (0, 0, 0)), ((1, 0, 0), (0, 0, 1), (0, 1, 0))]
        for ua, va, o in axes:
            ua = np.array(ua, dtype=np.float64)
            va = np.array(va, dtype=np.float64)
            o = np.array(o, dtype=np.float64)
            grid = [[vid(*(o + ua * (i / s) + va * (j / s))) for j in range(s + 1)]
                    for i in range(s + 1)]
            for i in range(s):
                for j in range(s):
                    p0, p1 = grid[i][j], grid[i + 1][j]
                    p2, p3 = grid[i + 1][j + 1], grid[i][j + 1]
                    faces.append([p0, p1, p2])
                    faces.append([p0, p2, p3])
        return np.array(faces, dtype=np.int32)

    from core.field import build_face_adjacency
    _f_cube = _build_subdiv_cube(16)
    _idx_cube, _w_cube, _maxk, _avgk = build_face_adjacency(_f_cube, "vertex")
    assert _maxk == 12, f"细分立方体顶点邻接 K 预期 12, 实际 {_maxk}"
    _rng = np.random.default_rng(42)
    _ac = _rng.uniform(0, 1, len(_f_cube)).astype(np.float32)
    _bc = _rng.uniform(0, 1, len(_f_cube)).astype(np.float32)
    _sa_c, _sb_c = float(_ac.sum()), float(_bc.sum())
    _r_c0 = float(_ac[:len(_f_cube) // 4].mean() - _ac[len(_f_cube) // 2:].mean())
    for _ in range(400):
        rule.update([_ac, _bc], params, 0.05, "mesh", nbr=(_idx_cube, _w_cube))
    assert not (np.isnan(_ac).any() or np.isnan(_bc).any()), "细分立方体 mesh 模式出现 NaN"
    assert float(_ac.min()) >= 0.0 and float(_bc.min()) >= 0.0, "正性投影失效:出现负值"
    assert float(_ac.max()) < 5.0 and float(_bc.max()) < 5.0, \
        f"场发散: a_max={_ac.max():.2f} b_max={_bc.max():.2f}"
    assert abs(float(_ac.sum()) - _sa_c) < 0.05 and abs(float(_bc.sum()) - _sb_c) < 0.05
    _r_c1 = float(_ac[:len(_f_cube) // 4].mean() - _ac[len(_f_cube) // 2:].mean())
    assert abs(_r_c1) > abs(_r_c0) * 2.0, \
        f"细分立方体相分离不足: {_r_c0:.4f} → {_r_c1:.4f}"
    print(f"[PASS] 细分立方体(3072 面, K=12)400 步: 无 NaN, 非负, 有界 "
          f"a∈[0,{_ac.max():.2f}] b∈[0,{_bc.max():.2f}], 守恒, 相分离 "
          f"{abs(_r_c0):.4f} → {abs(_r_c1):.4f}")

    # 10) 极端参数稳定性(投影的硬保证):repulsion/dt 均取 UI 上限。
    #     该组合超出 Agmon 稳定域,纹理退化为尖峰;投影保证的不变量是
    #     无 NaN + 非负 + 守恒 ⇒ 任一场有界于总质量(修复前直接发散 NaN)。
    _rng = np.random.default_rng(7)
    _ae = _rng.uniform(0, 1, (48, 48)).astype(np.float32)
    _be = _rng.uniform(0, 1, (48, 48)).astype(np.float32)
    _sae = float(_ae.sum())
    _extreme = {"repulsion": 2.0, "dt": 0.2}
    for _ in range(100):
        rule.update([_ae, _be], _extreme, 0.2, "grid")
    assert not (np.isnan(_ae).any() or np.isnan(_be).any()), "极端参数出现 NaN"
    assert float(_ae.min()) >= 0.0 and float(_be.min()) >= 0.0, "极端参数出现负值"
    assert float(_ae.max()) <= _sae, f"超出质量上界: a_max={_ae.max():.2f} > 总质量 {_sae:.2f}"
    # 极端区尖峰(值 ~10²,通量 ~10⁷)下 float32 加减有灾难性消去,
    # 精确守恒不可达;断言相对漂移 < 2%(默认参数区实测 Δ≤1e-4,见测试 2/9)
    _drift = abs(float(_ae.sum()) - _sae) / _sae
    assert _drift < 0.02, f"极端参数质量相对漂移过大: {_drift:.4f}"
    print(f"[PASS] 极端参数(c=2.0, dt=0.2)100 步: 无 NaN, 非负, 有界于总质量 "
          f"(a_max={_ae.max():.1f} ≤ {_sae:.0f}), 相对漂移 {_drift:.4f}")

    print("\n全部通过:Oil-Water 相分离系统就绪")



if __name__ == "__main__":
    test_all()
    print("all passed")
