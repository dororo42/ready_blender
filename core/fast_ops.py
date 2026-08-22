# -*- coding: utf-8 -*-
"""性能优化内核(P3-4):numpy 微优化 + FFT 拉普拉斯 + SmoothLife FFT 版。净室实现。"""
from __future__ import annotations
import numpy as np


# ---------------------------------------------------------------------------
# 微优化版 Gray-Scott 步进(减少临时数组分配,复用缓冲区)
# ---------------------------------------------------------------------------

def laplacian_5_fast(u: np.ndarray, wrap: bool = False, out: np.ndarray | None = None) -> np.ndarray:
    """5 点拉普拉斯,支持 out 复用。"""
    if out is None:
        out = np.empty_like(u)
    np.multiply(u, -4.0, out=out)
    if wrap:
        out += np.roll(u, 1, axis=0) + np.roll(u, -1, axis=0)
        out += np.roll(u, 1, axis=1) + np.roll(u, -1, axis=1)
    else:
        out[1:, :] += u[:-1, :]
        out[:-1, :] += u[1:, :]
        out[:, 1:] += u[:, :-1]
        out[:, :-1] += u[:, 1:]
        out[0, :] += u[0, :]
        out[-1, :] += u[-1, :]
        out[:, 0] += u[:, 0]
        out[:, -1] += u[:, -1]
    return out


def gray_scott_step_opt(a, b, Du, Dv, F, k, dt, wrap=False,
                        lap_a=None, lap_b=None, abb=None):
    """微优化 Gray-Scott:复用 laplacian/abb 缓冲区,减少分配。

    数学与 GrayScottRule 完全一致(已验证等价),仅改变内存布局策略。
    审查修复:检查缓冲区与输入数组别名,防止自毁。
    """
    if lap_a is None:
        lap_a = np.empty_like(a)
    if lap_b is None:
        lap_b = np.empty_like(b)
    if abb is None:
        abb = np.empty_like(a)
    for buf, src in ((lap_a, a), (lap_b, b), (abb, a), (abb, b)):
        if buf is src:
            raise ValueError("gray_scott_step_opt 缓冲区不得与输入数组共享内存")
    laplacian_5_fast(a, wrap, out=lap_a)
    laplacian_5_fast(b, wrap, out=lap_b)
    np.multiply(lap_a, Du * dt, out=lap_a)
    np.multiply(lap_b, Dv * dt, out=lap_b)
    np.multiply(a, b, out=abb)
    abb *= b
    abb *= -dt
    # a += lap_a - abb + F*dt*(1-a)
    a *= (1.0 - F * dt)
    a += F * dt
    a += lap_a
    a += abb
    # b += lap_b + abb - (F+k)*dt*b  (abb = -abb_raw*dt)
    b *= (1.0 - (F + k) * dt)
    b += lap_b
    b -= abb
    # 数值防护:与 GrayScottRule 同口径的浓度裁剪(防瞬态溢出→NaN)
    np.clip(a, 0.0, 2.0, out=a)
    np.clip(b, 0.0, 1.0, out=b)
    return a, b


def _weights_are_iso(wx, wy):
    """wx/wy 是否为等向(标量 1,1)。仅标量判断;图(空间取向)视为各向异性。"""
    if wx is None or wy is None:
        return True
    if not np.isscalar(wx) or not np.isscalar(wy):
        return False
    return float(wx) == 1.0 and float(wy) == 1.0


def gray_scott_step_aniso_opt(a, b, Du, Dv, F, k, dt, wx, wy, wrap=False,
                              vx=None, vy=None,
                              lap_a=None, lap_b=None, abb=None):
    """各向异性 + 平流版 Gray-Scott(一模内部核)。

    在 gray_scott_step_opt 基础上:
      - 扩散用各向异性 5 点核(wx/wy 可为标量或同形 2D 图;标量 1,1 或 None → 等向);
      - 反应步后对 a/b 各做一次半拉格朗日平流(vx/vy 速度场,dt 采样)。
    稳定性:等向分支保证 wx+wy≡2 → 谱半径不变,dt·Du≤0.25 稳定域不变;
    平流为显式纯对流,速度积分 ∥v∥·dt 应 < 1 格(网页默认强度满足)。
    """
    if lap_a is None:
        lap_a = np.empty_like(a)
    if lap_b is None:
        lap_b = np.empty_like(b)
    if abb is None:
        abb = np.empty_like(a)
    if _weights_are_iso(wx, wy):
        laplacian_5_fast(a, wrap, out=lap_a)
        laplacian_5_fast(b, wrap, out=lap_b)
    else:
        _laplacian_aniso_5_fast(a, wx, wy, wrap, out=lap_a)
        _laplacian_aniso_5_fast(b, wx, wy, wrap, out=lap_b)
    np.multiply(lap_a, Du * dt, out=lap_a)
    np.multiply(lap_b, Dv * dt, out=lap_b)
    np.multiply(a, b, out=abb)
    abb *= b
    abb *= -dt
    a *= (1.0 - F * dt)
    a += F * dt
    a += lap_a
    a += abb
    b *= (1.0 - (F + k) * dt)
    b += lap_b
    b -= abb
    np.clip(a, 0.0, 2.0, out=a)
    np.clip(b, 0.0, 1.0, out=b)
    if vx is not None and vy is not None:
        _advect_inplace(a, vx, vy, dt, wrap)
        _advect_inplace(b, vx, vy, dt, wrap)
    return a, b


def _laplacian_aniso_5_fast(u, wx, wy, wrap, out=None):
    """各向异性 5 点拉普拉斯(wx/wy 标量或同形 2D 图),out 复用。"""
    if out is None:
        out = np.empty_like(u)
    out[:] = -2.0 * (wx + wy) * u
    if wrap:
        out += wx * (np.roll(u, 1, axis=0) + np.roll(u, -1, axis=0))
        out += wy * (np.roll(u, 1, axis=1) + np.roll(u, -1, axis=1))
    else:
        up = np.pad(u, 1, mode="edge")
        out += wx * (up[:-2, 1:-1] + up[2:, 1:-1])
        out += wy * (up[1:-1, :-2] + up[1:-1, 2:])
    return out


def _advect_inplace(u, vx, vy, dt, wrap):
    """就地半拉格朗日平流(委派 ops.advect_semi_lagrangian 的纯 numpy 实现)。"""
    from .ops import advect_semi_lagrangian
    u[:] = advect_semi_lagrangian(u, vx, vy, dt, wrap=wrap)


# ---------------------------------------------------------------------------
# FFT 拉普拉斯(周期边界,大网格加速)
# ---------------------------------------------------------------------------

def make_fft_kernel(shape):
    """预计算谱域拉普拉斯核 (kx²+ky²) 的负值,rfft2 形状。"""
    ky, kx = np.meshgrid(
        np.fft.fftfreq(shape[0]) * 2 * np.pi,
        np.fft.rfftfreq(shape[1]) * 2 * np.pi,
        indexing="ij")
    return -(kx * kx + ky * ky)


def laplacian_fft(u: np.ndarray, kernel: np.ndarray):
    """FFT 谱域拉普拉斯(周期边界)。u float32;内部 float64 FFT 保证精度。"""
    f = np.fft.rfft2(u.astype(np.float64))
    f *= kernel
    return np.fft.irfft2(f, s=u.shape).astype(u.dtype)


def gray_scott_step_fft(a, b, Du, Dv, F, k, dt, kernel):
    """FFT 版 Gray-Scott 步进(仅 wrap 网格)。"""
    lap_a = laplacian_fft(a, kernel)
    lap_b = laplacian_fft(b, kernel)
    abb = a * b * b
    a += (Du * lap_a - abb + F * (1.0 - a)) * dt
    b += (Dv * lap_b + abb - (F + k) * b) * dt
    return a, b


# ---------------------------------------------------------------------------
# SmoothLife FFT 完整版(Rafler 2011 的 FFT 卷积实现)
# ---------------------------------------------------------------------------

def smoothlife_step_fft(u, kernel_ring, kernel_inner, alpha_n, alpha_m, b1, b2, d1, d2, dt=0.05):
    """SmoothLife 一步(FFT 卷积版)。

    思路(Rafler 2011 公开论文):M = 外环均值,N = 内盘均值,
    出生 = σ(M,b1,b2)·σ(N,b2,b1) 双门控,死亡 = σ(M,d1,d2)。
    审查修复:内盘均值 N 此前算完即弃,现在真正参与出生项门控。
    """
    F = np.fft.rfft2(u.astype(np.float64))
    m = np.fft.irfft2(F * kernel_ring, s=u.shape)
    n = np.fft.irfft2(F * kernel_inner, s=u.shape)
    alive_m = sigmoid(m, b1, alpha_m) * (1.0 - sigmoid(m, b2, alpha_m))
    alive_n = sigmoid(n, b1, alpha_n) * (1.0 - sigmoid(n, b2, alpha_n))
    dead_m = sigmoid(m, d1, alpha_m) * (1.0 - sigmoid(m, d2, alpha_m))
    alive = alive_m * alive_n
    u += (alive * (1.0 - u) - dead_m * u) * dt
    np.clip(u, 0, 1, out=u)
    return u


def sigmoid(x, center, alpha):
    return 1.0 / (1.0 + np.exp(-alpha * (x - center)))


def make_smoothlife_kernels(shape, radius_outer=10, radius_inner=3):
    """构造外环/内盘卷积核(rfft 形状)。外环 = 大高斯 − 内高斯。"""
    ky, kx = np.meshgrid(
        np.fft.fftfreq(shape[0]) * shape[0],
        np.fft.rfftfreq(shape[1]) * shape[1],
        indexing="ij")
    r2 = kx * kx + ky * ky
    ring = np.exp(-np.pi ** 2 * r2 * radius_outer ** -2) - np.exp(-np.pi ** 2 * r2 * radius_inner ** -2)
    inner = np.exp(-np.pi ** 2 * r2 * radius_inner ** -2)
    return ring.astype(np.complex128), inner.astype(np.complex128)
