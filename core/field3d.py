# -*- coding: utf-8 -*-
"""3D 体素规则网格 + 7 点拉普拉斯。净室实现。"""
from __future__ import annotations
import numpy as np


class RegularGridField3D:
    """3D 规则网格标量场。"""

    def __init__(self, shape=(64, 64, 64), wrap=False, dtype=np.float32):
        self.shape = tuple(shape)
        self.wrap = wrap
        self.dtype = dtype
        self.data = np.zeros(shape, dtype=dtype)

    def copy(self):
        f = RegularGridField3D(self.shape, self.wrap, self.dtype)
        f.data = self.data.copy()
        return f


def laplacian_7(u: np.ndarray, wrap: bool = False) -> np.ndarray:
    """7 点离散拉普拉斯(3D 六邻居)。"""
    lap = -6.0 * u
    if wrap:
        for ax in range(3):
            lap += np.roll(u, 1, axis=ax) + np.roll(u, -1, axis=ax)
    else:
        for ax in range(3):
            s1 = [slice(None)] * 3
            s2 = [slice(None)] * 3
            s3 = [slice(None)] * 3
            s1[ax] = slice(1, None)
            s2[ax] = slice(None, -1)
            lap[tuple(s1)] += u[tuple(s2)]
            s3[ax] = slice(None, -1)
            lap[tuple(s3)] += u[tuple(s1)]
        # clamp 边界补足
        for ax in range(3):
            b1 = [slice(None)] * 3
            b2 = [slice(None)] * 3
            b1[ax] = 0
            lap[tuple(b1)] += u[tuple(b1)]
            b2[ax] = -1
            lap[tuple(b2)] += u[tuple(b2)]
    return lap


class GrayScottRule3D:
    """Gray-Scott 3D 版(7 点拉普拉斯)。公式同 2D,源公开文献。"""
    name = "Gray-Scott-3D"
    n_chemicals = 2

    def update(self, fields, params, dt=1.0, field_kind="grid3d", nbr=None, wrap=False):
        a, b = fields[0], fields[1]
        Du, Dv = params["Du"], params["Dv"]
        F, k = params["F"], params["k"]
        lap_a = laplacian_7(a, wrap)
        lap_b = laplacian_7(b, wrap)
        abb = a * b * b
        a += (Du * lap_a - abb + F * (1.0 - a)) * dt
        b += (Dv * lap_b + abb - (F + k) * b) * dt
        return fields

    def describe_parameters(self):
        return [("Du", 0.16, 0, 1), ("Dv", 0.08, 0, 1), ("F", 0.0367, 0, 0.2), ("k", 0.0649, 0, 0.2), ("dt", 1.0, 0.05, 2)]


def extract_slice(field3d, axis=2, index=None):
    """取切片(返回 2D 视图)。"""
    idx = index if index is not None else field3d.shape[axis] // 2
    sl = [slice(None)] * 3
    sl[axis] = idx
    return field3d[tuple(sl)].copy()
