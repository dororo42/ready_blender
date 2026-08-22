# -*- coding: utf-8 -*-
"""W1 扩展参数回归测试:Orientation(各向异性扩散)/ Flow(平流) 在核心与 backend 的应用。

背景:修复过 3 处同类缺陷——各向异性 5 点拉普拉斯主对角线系数少乘 2
(应为 -2(wx+wy)·u,而非 -(wx+wy)·u),导致 wx=wy=1 不还原标准 5 点拉普拉斯、
并使任意 Orientation 把图案压平为均匀场上。
本测试锁定:等向还原 / 图案保形 / 平流确实改变场 / 前后端一致 / 无 NaN。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from core.ops import laplacian_5, laplacian_aniso_5, orientation_maps
from core.fast_ops import laplacian_5_fast, _laplacian_aniso_5_fast
from core.flow_field import velocity_field
from core.ops import advect_semi_lagrangian
from core.rule import GrayScottRule
from backend.numpy_backend import NumpyBackend


def _fresh(n=48, seed=0):
    rng = np.random.default_rng(seed)
    a = np.ones((n, n), np.float32) + (rng.random((n, n)).astype(np.float32) - 0.5) * 0.01
    b = np.zeros((n, n), np.float32)
    c = n // 2
    b[c - 2:c + 2, c - 2:c + 2] = 1.0
    return a, b


def test_aniso_reduces_to_iso():
    # wx=wy=1 → 各向异性 5 点拉普拉斯逐位等于标准 5 点拉普拉斯
    n = 48
    rng = np.random.default_rng(0)
    u = rng.random((n, n)).astype(np.float32)
    iso = laplacian_5(u, True)
    aniso = laplacian_aniso_5(u, 1.0, 1.0, True)
    assert np.allclose(aniso, iso, atol=1e-6), "wx=wy=1 未还原标准拉普拉斯"


def test_aniso_fast_matches_ops():
    n = 48
    rng = np.random.default_rng(1)
    u = rng.random((n, n)).astype(np.float32)
    for kind, s in [("linear", 0.5), ("radial", 0.3), ("bubble", 0.4)]:
        wx, wy = orientation_maps((n, n), kind, s)
        a = _laplacian_aniso_5_fast(u, wx, wy, True, out=np.empty_like(u))
        b = laplacian_aniso_5(u, wx, wy, True)
        assert np.allclose(a, b, atol=1e-5), f"fast 与 ops 不一致: {kind}"


def test_orientation_does_not_collapse_pattern():
    # Orientation 只会改变图案走向/形态,不应把活跃图案抹平为均匀场
    be = NumpyBackend()
    p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0, wrap=True)
    base = _fresh()
    be.step(GrayScottRule(), base, dict(p), n=800, field_kind="grid")
    for kind in ["linear", "horizontal", "radial", "circles", "swirl", "bubble"]:
        x = _fresh()
        be.step(GrayScottRule(), x, dict(p, orientation_kind=kind, orientation_strength=0.3),
                n=800, field_kind="grid")
        std_b = float(x[1].std())
        assert np.isfinite(x[0]).all() and np.isfinite(x[1]).all()
        assert std_b > 0.5 * float(base[1].std()), f"{kind} 把图案压平: std={std_b:.4f}"


def test_flow_genuinely_alters_field():
    # 平流只改分布不改方差,故用逐点差异判定确已应用
    be = NumpyBackend()
    p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0, wrap=True)
    base = _fresh()
    be.step(GrayScottRule(), base, dict(p), n=800, field_kind="grid")
    fl = _fresh()
    be.step(GrayScottRule(), fl, dict(p, flow_kind="swirl", flow_strength=0.6),
            n=800, field_kind="grid")
    assert np.isfinite(fl[0]).all() and np.isfinite(fl[1]).all()
    diff = float(np.abs(fl[1] - base[1]).max())
    assert diff > 1e-3, f"Flow 未生效: max|b-base|={diff:.2e}"


def test_both_combined_finite():
    be = NumpyBackend()
    p = dict(Du=0.16, Dv=0.08, F=0.0545, k=0.062, dt=1.0, wrap=True)
    x = _fresh()
    be.step(GrayScottRule(), x, dict(p, orientation_kind="radial", orientation_strength=0.3,
            flow_kind="vortex", flow_strength=0.5), n=800, field_kind="grid")
    assert np.isfinite(x[0]).all() and np.isfinite(x[1]).all()
    assert float(x[1].std()) > 0.05


def test_flow_velocity_bounded_and_advects():
    vx, vy = velocity_field((64, 64), "swirl", 0.5)
    assert np.isfinite(vx).all() and np.abs(vx).max() < 1.0
    u = np.zeros((64, 64), np.float32)
    u[30:34, 30:34] = 1.0
    u2 = u.copy()
    for _ in range(300):
        u2 = advect_semi_lagrangian(u2, vx, vy, 1.0, True)
    assert float(np.abs(u2 - u).max()) > 1e-3, "平流 300 步未移动任何图案"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("w1_extensions: all passed")