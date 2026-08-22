# -*- coding: utf-8 -*-
"""Flow(平流)速度场生成器。净室实现,rdtool 的 7 种流控件同构(公式自建)。

每种场返回 (vx, vy) 与网格同形 float32,语义:每单位时间位移量(格)。
强度 strength 控制速度幅度;应用时位移 = v·dt,须 ∥v∥·dt < 1 格保稳定。
"""
import numpy as np


_FLOW_KINDS = ("none", "vertical", "radial", "rotate", "swirl",
               "bubble", "ring", "vortex")


def velocity_field(shape, kind="none", strength=0.0, center=None):
    """构造 (vx, vy) 速度场(行/列坐标)。

    kind ∈ none/vertical/radial/rotate/swirl/bubble/ring/vortex。
    strength 缩放速度幅度(正值);center 为径向场中心,(row, col),默认网格中心。
    """
    n0, n1 = shape
    strength = float(strength)
    if kind == "none" or strength == 0.0:
        return np.zeros(shape, dtype=np.float32), np.zeros(shape, dtype=np.float32)
    g = np.mgrid[0:n0, 0:n1]
    R = g[0].astype(np.float64)
    C = g[1].astype(np.float64)
    if center is None:
        cr, cc = (n0 - 1) / 2.0, (n1 - 1) / 2.0
    else:
        cr, cc = float(center[0]), float(center[1])
    dx = R - cr          # 到中心的行偏移
    dy = C - cc          # 到中心的列偏移
    rad = np.sqrt(dx * dx + dy * dy)
    safe_rad = np.maximum(rad, 1e-12)
    half_diag = 0.5 * np.sqrt(n0 * n0 + n1 * n1)
    u_rad = rad / half_diag          # radial 距离占比 0~2

    vx = np.zeros_like(R)
    vy = np.zeros_like(C)

    if kind == "vertical":
        vx = np.full(R.shape, strength)          # 向下(行+)
    elif kind == "radial":
        vx = strength * (dx / safe_rad)          # 向外
        vy = strength * (dy / safe_rad)
    elif kind == "rotate":
        vx = -strength * (dy / safe_rad)         # 切向(逆时针)
        vy = strength * (dx / safe_rad)
    elif kind == "swirl":
        vx = -strength * u_rad * (dy / safe_rad)  # 切向,强度随半径增大
        vy = strength * u_rad * (dx / safe_rad)
    elif kind == "bubble":
        # 中心向外喷涌,受高斯衰减 → 中心强、边缘弱
        env = np.exp(-u_rad * u_rad)
        vx = strength * env * (dx / safe_rad)
        vy = strength * env * (dy / safe_rad)
    elif kind == "ring":
        # 环形涌出(约半径一半处最强),切向旋转
        peak = 0.5
        env = np.exp(-((u_rad - peak) / (0.15 * 2.0)) ** 2)
        vx = -strength * env * (dy / safe_rad)
        vy = strength * env * (dx / safe_rad)
    elif kind == "vortex":
        u_rad = rad / half_diag
        env = 1.0 - u_rad                       # 中心强,向外弱
        vx = -strength * env * (dy / safe_rad)
        vy = strength * env * (dx / safe_rad)
    else:
        raise ValueError(kind)

    # 每个速度分量按半对角归一化,保证 ∥v∥max ≈ strength(格/单位时间)
    if half_diag > 0:
        vx = (vx / half_diag).astype(np.float32)
        vy = (vy / half_diag).astype(np.float32)
    return vx, vy