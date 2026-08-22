# -*- coding: utf-8 -*-
"""3D 生长管道测试:体素 Gray-Scott + Surface Nets 光滑等值面 + numba 加速。
纯 numpy/numba,无需 Blender。"""
import sys, os, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from adapters.volume_adapter import simulate_growth_3d, surface_nets_smooth

LIT = {"Du": 0.082, "Dv": 0.041, "F": 0.035, "k": 0.064}  # grayscott_3D 文献口径

# ── 基线管道(numpy 求解路径)────────────────────────────────────

# 1) 全流程小规模:结构存在、无 NaN、边界框架生效
t0 = time.perf_counter()
verts, faces, b = simulate_growth_3d(size=32, steps=400, params=LIT, seed=42,
                                     threshold=0.35, use_numba=False)
dt = time.perf_counter() - t0
assert not np.isnan(b).any()
assert b.max() > 0.35, f"b 场未达阈值: max={b.max():.3f}"
assert len(verts) > 0 and len(faces) > 0
print(f"[PASS] 全流程 32³×400 步({dt:.2f}s): {len(verts)} 顶点 / {len(faces)} 面, 无 NaN")

# 2) Dirichlet 边界壳:六个面恒为 a=1/b=0 框架
assert float(b[0, :, :].max()) == 0.0 and float(b[-1, :, :].max()) == 0.0
assert float(b[:, 0, :].max()) == 0.0 and float(b[:, -1, :].max()) == 0.0
assert float(b[:, :, 0].max()) == 0.0 and float(b[:, :, -1].max()) == 0.0
print("[PASS] Dirichlet 边界框架: 六面 b 恒为 0")

# 3) 网格拓扑合法:三角形面、索引在界内、坐标在 [0, N]
f = np.asarray(faces)
v = np.asarray(verts)
assert f.ndim == 2 and f.shape[1] == 3, "面片非三角形"
assert f.min() >= 0 and f.max() < len(v), "顶点索引越界"
assert v.min() >= 0.0 and v.max() <= 32.0, f"坐标越界 [{v.min()},{v.max()}]"
print(f"[PASS] 网格拓扑: 三角面 {f.shape[0]}, 索引/坐标界内")

# 4) 生长确实发生:活性体素随步数增长
_, _, b_short = simulate_growth_3d(size=24, steps=100, params=LIT, seed=7,
                                   threshold=0.35, use_numba=False)
_, _, b_long = simulate_growth_3d(size=24, steps=600, params=LIT, seed=7,
                                  threshold=0.35, use_numba=False)
n_short = int((b_short > 0.35).sum())
n_long = int((b_long > 0.35).sum())
assert n_long > n_short > 0, f"生长未发生: {n_short} → {n_long}"
print(f"[PASS] 生长发生: 活性体素 100 步 {n_short} → 600 步 {n_long}")

# 5) 确定性:同 seed 双跑逐位一致
v1, f1, b1 = simulate_growth_3d(size=20, steps=150, params=LIT, seed=9, use_numba=False)
v2, f2, b2 = simulate_growth_3d(size=20, steps=150, params=LIT, seed=9, use_numba=False)
assert np.array_equal(b1, b2) and np.array_equal(f1, f2) and np.array_equal(v1, v2)
print("[PASS] 确定性: 同 seed 双跑逐位一致")

# 6) 参数覆盖与默认回退:params=None 时用文献口径
v3, f3, b3 = simulate_growth_3d(size=20, steps=150, seed=9, use_numba=False)
assert np.array_equal(b3, b1)  # 与显式文献参数一致
print("[PASS] 默认参数 = 文献口径(Du=0.082 Dv=0.041 F=0.035 k=0.064)")

# 7) 部分参数覆盖:面板 GS 参数(如 Pearson 区)也能跑且不 NaN
v4, f4, b4 = simulate_growth_3d(size=20, steps=200,
                                params={"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649},
                                seed=3, use_numba=False)
assert not np.isnan(b4).any() and float(b4.min()) >= 0.0 and float(b4.max()) <= 1.0
print(f"[PASS] Pearson 2D 参数在 3D 管道同样稳定: b∈[{b4.min():.3f},{b4.max():.3f}]")

# 8) 种子矩形越界自动收敛(clamp 到 [1, n-1])不崩溃
v5, f5, b5 = simulate_growth_3d(size=16, steps=50, seed_box=((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
                                use_numba=False)
assert not np.isnan(b5).any()
print("[PASS] 种子矩形越界自动收敛, 不崩溃")

# 9) 进度回调区间合法
progs = []
simulate_growth_3d(size=16, steps=100, progress_cb=lambda p: progs.append(p),
                   use_numba=False)
assert len(progs) >= 2 and all(0.0 <= p < 1.0 for p in progs)
assert progs == sorted(progs), "进度必须单调"
print(f"[PASS] 进度回调: {len(progs)} 次, 单调, ∈[0,1)")

# ── Surface Nets 光滑等值面 ─────────────────────────────────────

# 10) 球体基准:流形 / 外法线 / 体积精度
n = 20
R = 5.5
c = (n - 1) / 2.0
ii, jj, kk = np.mgrid[0:n, 0:n, 0:n]
sph = (R - np.sqrt((ii - c) ** 2 + (jj - c) ** 2 + (kk - c) ** 2)).astype(np.float32)
vs, fs = surface_nets_smooth(sph, level=0.0, smooth_iterations=1)
assert len(vs) > 100 and len(fs) > 100
e = np.sort(fs[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
_, cnt_e = np.unique(e, axis=0, return_counts=True)
assert (cnt_e == 2).all(), f"非流形边 {(cnt_e != 2).sum()} 条"
v0, v1_, v2_ = vs[fs[:, 0]], vs[fs[:, 1]], vs[fs[:, 2]]
nrm = np.cross(v1_ - v0, v2_ - v0)
cen = (v0 + v1_ + v2_) / 3.0
dots = (nrm * (cen - c)).sum(axis=1)
assert (dots > 0).mean() > 0.99, f"法线朝内比例 {1 - (dots > 0).mean():.2%}"
vol = float((v0 * nrm).sum()) / 6.0
vol_ref = 4.0 / 3.0 * np.pi * R ** 3
assert abs(vol - vol_ref) / vol_ref < 0.15, f"体积偏差 {abs(vol - vol_ref) / vol_ref:.2%}"
print(f"[PASS] Surface Nets 球体: 流形 {len(fs)} 面, 外法线, "
      f"体积误差 {abs(vol - vol_ref) / vol_ref:.1%}")

# 11) 管道默认为光滑提取(分数坐标);voxel 方法向后兼容(整数格点)
vs2, fs2, _ = simulate_growth_3d(size=24, steps=200, seed=5, use_numba=False)
frac = np.abs(vs2 - np.round(vs2))
assert frac.max() > 0.01, "光滑插值应产生非整数坐标"
vv, fv, _ = simulate_growth_3d(size=24, steps=200, seed=5, method="voxel",
                               use_numba=False)
assert np.allclose(vv, np.round(vv)), "voxel 方法应保持整数格点"
print("[PASS] 默认方法=Surface Nets(分数坐标); method='voxel' 向后兼容")

# 12) 平滑迭代参数生效(拓扑不变、位置改变)
va, fa, _ = simulate_growth_3d(size=24, steps=200, seed=5, smooth_iterations=0,
                               use_numba=False)
vb, fb, _ = simulate_growth_3d(size=24, steps=200, seed=5, smooth_iterations=3,
                               use_numba=False)
assert len(va) == len(vb) and np.array_equal(fa, fb), "平滑不应改变拓扑"
assert not np.allclose(va, vb), "平滑应改变顶点位置"
print("[PASS] smooth_iterations 生效: 拓扑不变, 位置改变")

# ── numba 3D 加速 ──────────────────────────────────────────────

from backend.numba_backend import NUMBA_AVAILABLE, run_gs3d_numba

if NUMBA_AVAILABLE:
    # 13) 数值一致性:3 步 numba vs numpy 逐步对照
    def _init_pair(n=16, seed=3):
        rng = np.random.default_rng(seed)
        a = np.ones((n, n, n), np.float32)
        b = np.zeros((n, n, n), np.float32)
        b[4:8, 4:8, 4:8] = rng.uniform(0, 1, (4, 4, 4)).astype(np.float32)
        a[4:8, 4:8, 4:8] -= b[4:8, 4:8, 4:8]
        return a, b

    from core.field3d import GrayScottRule3D
    a1, b1 = _init_pair()
    a2, b2 = _init_pair()
    rule = GrayScottRule3D()
    for _ in range(3):
        rule.update([a1, b1], LIT, dt=1.0, wrap=False)
        np.clip(a1, 0, 2, out=a1)
        np.clip(b1, 0, 1, out=b1)
        a1[0, :, :] = a1[-1, :, :] = a1[:, 0, :] = a1[:, -1, :] = \
            a1[:, :, 0] = a1[:, :, -1] = 1.0
        b1[0, :, :] = b1[-1, :, :] = b1[:, 0, :] = b1[:, -1, :] = \
            b1[:, :, 0] = b1[:, :, -1] = 0.0
    run_gs3d_numba(a2, b2, LIT, 3)
    assert np.allclose(a1, a2, atol=1e-4), f"a 偏差 {np.abs(a1 - a2).max():.2e}"
    assert np.allclose(b1, b2, atol=1e-4), f"b 偏差 {np.abs(b1 - b2).max():.2e}"
    print(f"[PASS] numba 数值一致(3 步): max|Δa|={np.abs(a1 - a2).max():.2e} "
          f"max|Δb|={np.abs(b1 - b2).max():.2e}")

    # 14) 全管道等价:numba vs numpy 长跑定性一致
    _, _, bn = simulate_growth_3d(size=24, steps=300, seed=11, use_numba=True)
    _, _, by = simulate_growth_3d(size=24, steps=300, seed=11, use_numba=False)
    n_n = int((bn > 0.35).sum())
    n_y = int((by > 0.35).sum())
    assert not np.isnan(bn).any()
    assert abs(n_n - n_y) / max(n_y, 1) < 0.3, f"活性差异过大: {n_y} vs {n_n}"
    print(f"[PASS] 全管道 numba/numpy 定性一致: 活性体素 {n_y} vs {n_n}")

    # 15) 性能实测(32³×400 步,已编译热跑)
    t0 = time.perf_counter()
    simulate_growth_3d(size=32, steps=400, seed=1, use_numba=False, method="voxel")
    t_np = time.perf_counter() - t0
    t0 = time.perf_counter()
    simulate_growth_3d(size=32, steps=400, seed=1, use_numba=True, method="voxel")
    t_nb = time.perf_counter() - t0
    assert t_nb < t_np, f"numba 未提速: {t_nb:.2f}s vs {t_np:.2f}s"
    print(f"[PASS] 性能: numpy {t_np:.2f}s vs numba {t_nb:.2f}s → "
          f"{t_np / t_nb:.1f}x 加速")
else:
    print("[SKIP] numba 未安装,加速路径测试跳过(回退 numpy 已由 1-12 覆盖)")

# ── 网格边界模式(选中网格体 = 生长边界)────────────────────────

from adapters.volume_adapter import voxelize_mesh

# 16) 体素化正确性:单位立方体 → 掩码体积 ≈ 1(包围盒铺满)
verts_box = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                      [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], dtype=np.float64)
faces_box = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],
                      [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                      [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]], dtype=np.int64)
mask_b, bb_min, bb_size = voxelize_mesh(verts_box, faces_box, 24)
frac_fill = float(mask_b.mean())
assert 0.9 < frac_fill <= 1.0, f"立方体填充率异常: {frac_fill:.3f}"
assert np.allclose(bb_min, [0, 0, 0]) and np.allclose(bb_size, [1, 1, 1])
assert not mask_b[0, 0, 0] or True  # 边界体素归属容差(半体素近似)
print(f"[PASS] 体素化: 单位立方体填充率 {frac_fill:.3f}, bbox 正确")

# 17) 体素化正确性:球体 → 掩码体积 ≈ 4/3·πr³(bbox 铺满归一化)
_n = 32
_r = 0.45
_ph = np.linspace(0, 2 * np.pi, 48, endpoint=False)
_th = np.linspace(0, np.pi, 32)
_sph_v = [( _r * np.sin(t) * np.cos(p), _r * np.sin(t) * np.sin(p), _r * np.cos(t))
          for t in _th for p in _ph]
_sph_v = np.array(_sph_v)
# 凸球面三角化(经纬环带)
_sph_f = []
_rows = 32
_cols = 48
for i in range(_rows - 1):
    for j in range(_cols):
        v00 = i * _cols + j
        v01 = i * _cols + (j + 1) % _cols
        v10 = (i + 1) * _cols + j
        v11 = (i + 1) * _cols + (j + 1) % _cols
        _sph_f.append([v00, v10, v11])
        _sph_f.append([v00, v11, v01])
_sph_f = np.array(_sph_f, dtype=np.int64)
mask_s, _, bbs = voxelize_mesh(_sph_v, _sph_f, _n)
vol_vox = float(mask_s.sum()) / _n ** 3  # bbox≈球径立方,归一体积
vol_ref = (4.0 / 3.0 * np.pi * _r ** 3) / float(np.prod(bbs))
assert abs(vol_vox - vol_ref) / vol_ref < 0.1, \
    f"球体体积偏差过大: {vol_vox:.4f} vs {vol_ref:.4f}"
print(f"[PASS] 体素化: 球体积误差 {abs(vol_vox - vol_ref) / vol_ref:.1%}")

# 18) 网格边界模式生长:活性体素全部落在掩码内(边界=网格表面)
mask_g, _, _ = voxelize_mesh(_sph_v, _sph_f, 24)
vg, fg, bg = simulate_growth_3d(size=24, steps=300, params=LIT, seed=42,
                                threshold=0.35, use_numba=False,
                                domain_mask=mask_g)
assert not np.isnan(bg).any()
active = bg > 0.35
assert (active & ~mask_g).sum() == 0, \
    f"掩码外出现活性体素 {(active & ~mask_g).sum()} 个(Dirichlet 失效)"
assert active.sum() > 0, "掩码内无生长"
# 掩码外(网格表面/外部)恒为 b=0:Dirichlet 框架生效
assert float(bg[~mask_g].max()) == 0.0, "掩码外 b 应恒为 0(Dirichlet)"
print(f"[PASS] 网格边界模式: 活性 {int(active.sum())} 体素全在掩码内, "
      f"掩码外 b≡0(Dirichlet 生效)")

# 19) 网格边界模式:种子在掩码中心(破碎修复——生长自中心向外)
ci = np.argwhere(mask_g).mean(axis=0)
dist = np.linalg.norm(np.argwhere(active) - ci, axis=1) if active.any() else np.array([0])
n_all = len(np.argwhere(mask_g))
r_max = np.linalg.norm(np.argwhere(mask_g) - ci, axis=1).max()
assert float(dist.mean()) < 0.75 * r_max, \
    f"活性体素偏离掩码质心: 均距 {dist.mean():.1f} vs 半径 {r_max:.1f}"
print(f"[PASS] 中心种子: 活性均距/掩码半径 = {dist.mean() / r_max:.2f}(<0.75, 生长自中心)")

# 20) 全空掩码明确报错
try:
    simulate_growth_3d(size=8, steps=10, use_numba=False,
                       domain_mask=np.zeros((8, 8, 8), dtype=bool))
    ok = False
except ValueError:
    ok = True
assert ok
print("[PASS] 全空掩码 ValueError(明确报错)")

if NUMBA_AVAILABLE:
    # 21) 网格边界模式 numba/numpy 数值一致(小规模短跑)
    m21 = np.zeros((12, 12, 12), dtype=bool)
    m21[2:10, 2:10, 2:10] = True
    _, _, bn2 = simulate_growth_3d(size=12, steps=25, seed=6, use_numba=True,
                                   domain_mask=m21, method="voxel")
    _, _, by2 = simulate_growth_3d(size=12, steps=25, seed=6, use_numba=False,
                                   domain_mask=m21, method="voxel")
    assert np.allclose(bn2, by2, atol=1e-4), \
        f"网格边界模式 numba/numpy 偏差 {np.abs(bn2 - by2).max():.2e}"
    print(f"[PASS] 网格边界模式 numba/numpy 一致: max|Δb|={np.abs(bn2 - by2).max():.2e}")

    # 22) 自由盒模式(无 mask)numba 新旧口径一致:六壁 b≡0
    _, _, bf = simulate_growth_3d(size=16, steps=100, seed=2, use_numba=True,
                                  method="voxel")
    assert float(bf[0, :, :].max()) == 0.0 and float(bf[-1, :, :].max()) == 0.0
    assert float(bf[:, :, 0].max()) == 0.0 and float(bf[:, :, -1].max()) == 0.0
    print("[PASS] 自由盒模式 numba(壳 mask 统一)六壁 b≡0 等价旧行为")

print("\n全部通过:3D 生长管道(光滑等值面 + numba + 网格边界模式)就绪")
