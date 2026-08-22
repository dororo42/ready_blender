# -*- coding: utf-8 -*-
"""1d Scale 测试:纯函数 + 数值(子步/稳定性/零回归)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from core.parameter import scale_params
from core.fast_ops import gray_scott_step_opt
from backend.numpy_backend import NumpyBackend
from core.rule import GrayScottRule


def test_scale_identity():
    # s=1 → 原样返回,零回归
    Du, Dv, dt, n = scale_params(0.16, 0.08, 1.0, 1.0)
    assert (Du, Dv, dt, n) == (0.16, 0.08, 1.0, 1)


def test_scale_small_no_substep():
    # s=0.5 → D 缩小,无需子步
    Du, Dv, dt, n = scale_params(0.16, 0.08, 1.0, 0.5)
    assert abs(Du - 0.04) < 1e-12 and n == 1


def test_scale_large_substep():
    Du, Dv, dt, n = scale_params(0.16, 0.08, 1.0, 2.5)
    # 0.16*6.25=1.0 → n = ceil(1.0/0.20)=5
    assert n == 5 and abs(dt - 0.2) < 1e-12
    assert abs(Du - 1.0) < 1e-12
    assert dt * Du <= 0.2 + 1e-12


def test_scale_s1_bitwise_identical():
    # s=1 时 fast 路径输出与不加 _n_sub 完全一致(零回归)
    rng = np.random.default_rng(0)
    a = rng.random((64, 64)).astype(np.float32)
    b = rng.random((64, 64)).astype(np.float32) * 0.3
    p1 = dict(Du=0.16, Dv=0.08, F=0.0367, k=0.0649, dt=1.0, wrap=True)
    p2 = dict(Du=0.16, Dv=0.08, F=0.0367, k=0.0649, dt=1.0, wrap=True, _n_sub=1)
    be = NumpyBackend()
    f1 = [a.copy(), b.copy()]
    f2 = [a.copy(), b.copy()]
    be.step(GrayScottRule(), f1, p1, n=50, field_kind="grid")
    be.step(GrayScottRule(), f2, p2, n=50, field_kind="grid")
    assert np.array_equal(f1[0], f2[0]) and np.array_equal(f1[1], f2[1])


def test_scale_no_nan():
    # s=0.5 与 s=2.5(子步)各 2000 步无 NaN,且 s=2.5 特征尺度更大
    def run(s, steps=2000):
        rng = np.random.default_rng(1)
        a = np.ones((128, 128), dtype=np.float32)
        b = np.zeros((128, 128), dtype=np.float32)
        b[62:66, 62:66] = 1.0
        a += (rng.random((128, 128)).astype(np.float32) - 0.5) * 1e-2
        Du, Dv, dt, n = scale_params(0.16, 0.08, 1.0, s)
        p = dict(Du=Du, Dv=Dv, F=0.0367, k=0.0649, dt=dt, wrap=True, _n_sub=n)
        be = NumpyBackend()
        f = [a, b]
        be.step(GrayScottRule(), f, p, n=steps, field_kind="grid")
        return f[1]

    b_small = run(0.5)
    b_large = run(2.5)
    assert np.isfinite(b_small).all() and np.isfinite(b_large).all()
    # 特征尺度:自相关衰减到 0.5 的距离(更大图案 → 更远)
    def corr_len(v):
        # 中心行自相关
        row = v[64] - v.mean()
        ac = np.correlate(row, row, mode="full")[len(row) - 1:]
        ac = ac / ac[0]
        i = np.argmax(ac < 0.5)
        return max(i, 1)
    assert corr_len(b_large) > corr_len(b_small) * 1.5


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("scale: all passed")