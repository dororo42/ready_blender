# -*- coding: utf-8 -*-
"""向量化算子:stencil 拉普拉斯与邻接 gather。净室实现,基于公开数值方法。"""
import numpy as np


def laplacian_5(u: np.ndarray, wrap: bool = False) -> np.ndarray:
    """5 点(von Neumann)离散拉普拉斯,(Σ邻居 − 4·自身),与 u 同型新数组。

    边界:wrap=True 周期边界;否则 clamp(零通量近似,边界外值取边界值)。
    净室说明:这是方形网格标准离散拉普拉斯,见任何数值 PDE 教材。
    """
    lap = -4.0 * u
    if wrap:
        lap += np.roll(u, 1, axis=0) + np.roll(u, -1, axis=0)
        lap += np.roll(u, 1, axis=1) + np.roll(u, -1, axis=1)
    else:
        lap[1:, :] += u[:-1, :]
        lap[:-1, :] += u[1:, :]
        lap[:, 1:] += u[:, :-1]
        lap[:, :-1] += u[:, 1:]
        # clamp(零通量近似):缺失方向以自身值补足
        lap[0, :] += u[0, :]
        lap[-1, :] += u[-1, :]
        lap[:, 0] += u[:, 0]
        lap[:, -1] += u[:, -1]
    return lap


def laplacian_9(u: np.ndarray, wrap: bool = False) -> np.ndarray:
    """9 点离散拉普拉斯(含对角),权重:4 邻各 1.0,对角各 0.5,中心 −6。"""
    lap = -6.0 * u
    if wrap:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                w = 1.0 if dx == 0 or dy == 0 else 0.5
                lap += w * np.roll(np.roll(u, dx, axis=0), dy, axis=1)
        return lap
    return _laplacian_9_pad(u)


def _laplacian_9_pad(u: np.ndarray) -> np.ndarray:
    up = np.pad(u, 1, mode="edge")  # clamp 边界
    lap = -6.0 * u
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            w = 1.0 if dx == 0 or dy == 0 else 0.5
            lap += w * up[1 + dx: 1 + dx + u.shape[0], 1 + dy: 1 + dy + u.shape[1]]
    return lap


def graph_laplacian(u: np.ndarray, nbr_idx: np.ndarray, nbr_w: np.ndarray) -> np.ndarray:
    """图拉普拉斯:(Σ_j w_ij·u_j) − u_i,权重按行归一化(Σ w_ij = 1)。

    nbr_idx: (F, K) int 邻居索引(不足 K 的行填自身索引)
    nbr_w:   (F, K) float 权重(填充槽位权重为 0 → 求和不受影响)
    K 列稠密平铺 + fancy-index gather,内存 O(F·K),避免稠密 F×F 矩阵。
    净室说明:归一化图拉普拉斯(权重 1/度)是谱图论标准定义,见公开教材。
    """
    gathered = u[nbr_idx]          # (F, K)
    return (gathered * nbr_w).sum(axis=1) - u


def laplacian_aniso_5(u: np.ndarray, wx: float, wy: float, wrap: bool = False) -> np.ndarray:
    """各向异性 5 点(von Neumann)拉普拉斯(Orientation)。

    数学:沿主方向(x)用权重 wx、垂直方向(y)用权重 wy,
      ∇²u ≈ wx·(u[i−1,j]+u[i+1,j]−2u) + wy·(u[i,j−1]+u[i,j+1]−2u)
    要求 wx+wy=2(等向情形 wx=wy=1 退化为标准 5 点拉普拉斯,逐位一致),
    则谱半径仍为 2(wx+wy)=4 → 显式欧拉稳定域 dt·Du≤0.25 不随 Orientation 改变。
    边界:wrap=True 周期;否则 clamp(零通量近似,缺失方向以自身补足)。
    净室说明:各向异性扩散系数矩阵 D=diag(wx,wy)(张量扩散),公开数值 PDE 标准构造。
    """
    lap = -2.0 * (wx + wy) * u
    if wrap:
        lap += wx * (np.roll(u, 1, axis=0) + np.roll(u, -1, axis=0))
        lap += wy * (np.roll(u, 1, axis=1) + np.roll(u, -1, axis=1))
    else:
        up = np.pad(u, 1, mode="edge")  # clamp 边界
        lap += wx * (up[:-2, 1:-1] + up[2:, 1:-1])
        lap += wy * (up[1:-1, :-2] + up[1:-1, 2:])
    return lap


def orientation_weights(angle_deg: float, strength: float) -> tuple[float, float]:
    """Orientation 参数 → 各向异性权重轴 wx/wy。

    wx 为主扩散方向(沿 angle 轴放大),wy 垂直方向。
      α ∈ [0,1) 代表各向异性强度;α=0 → wx=wy=1(等向)。
      权重:wx = 1+α, wy = 1−α → wx+wy≡2(保谱半径,稳定域不变)。
    净室说明:由旋转矩阵 R(θ) 作用于张量 diag(1+α, 1−α) 的自然构造,
    θ=0 时即为主轴对齐情形(无需旋转)。
    """
    import math
    alpha = float(np.clip(strength, 0.0, 0.95))
    if alpha <= 0.0:
        return 1.0, 1.0
    theta = math.radians(float(angle_deg) % 180.0)
    w1 = 1.0 + alpha   # 主轴
    w2 = 1.0 - alpha   # 副轴
    ct, st = math.cos(theta), math.sin(theta)
    wx = w1 * ct * ct + w2 * st * st
    wy = w1 * st * st + w2 * ct * ct
    return wx, wy


def orientation_angle_map(shape, kind, angle_deg=90.0):
    """Orientation 类型 → 逐像素方向场(度),与参考 rdtool 的 5 种空间模式对齐。

    返回与 shape 同形的 float64 数组(像素处扩散主轴角度,0~180 折叠)。
    kind(不区分大小写):
      none / linear / vert / vertical : 均匀方向 = angle_deg(默认 90°=竖直)
      horizontal : 均匀 0°(=水平)
      radial   : 指向圆心方向(atan2(dy,dx))
      circles  : 绕圆心切线方向(radial+90°)
      swirl    : radial 与切线各半(~45°偏转)
      bubble   : 内部 outward、越过半径后反向(参考 rdtool 的 bubble)
    净室说明:方向随空间变化的取向扩散,见公开文献各向异性反应扩散。
    """
    kind = str(kind or "none").strip().lower()
    n0, n1 = int(shape[0]), int(shape[1])
    if kind in ("none", ""):
        return np.zeros((n0, n1), dtype=np.float64)
    if kind in ("linear", "vert", "vertical"):
        return np.full((n0, n1), float(angle_deg) % 180.0, dtype=np.float64)
    if kind == "horizontal":
        return np.zeros((n0, n1), dtype=np.float64)
    g = np.mgrid[0:n0, 0:n1]
    dx = (g[0].astype(np.float64) - (n0 - 1) / 2.0)
    dy = (g[1].astype(np.float64) - (n1 - 1) / 2.0)
    ang = np.arctan2(dy, dx)  # radial base ∈ (−π, π]
    if kind == "radial":
        pass
    elif kind == "circles":
        ang = ang + np.pi / 2.0
    elif kind == "swirl":
        ang = ang + np.pi / 4.0
    elif kind == "bubble":
        rad = np.sqrt(dx * dx + dy * dy)
        half = 0.5 * np.sqrt(n0 * n0 + n1 * n1)
        u = rad / max(half, 1e-12)
        # 内部 outward,越过内半径翻转(~切线);参考 rdtool bubble 的锯齿取向
        ang = ang + np.where(u < 0.5, 0.0, np.pi) * 0.5
    else:
        raise ValueError(f"unknown orientation kind: {kind}")
    return np.degrees(ang) % 180.0


def orientation_weight_maps(angle_map, strength):
    """方向场(度) + 强度 → 逐像素各向异性权重 wx/wy(wx+wy≡2)。"""
    alpha = float(np.clip(strength, 0.0, 0.95))
    a = np.asarray(angle_map, dtype=np.float64)
    th = np.radians(a % 180.0)
    w1 = 1.0 + alpha
    w2 = 1.0 - alpha
    ct = np.cos(th)
    st = np.sin(th)
    wx = w1 * ct * ct + w2 * st * st
    wy = w1 * st * st + w2 * ct * ct
    return wx, wy


_ORIENT_UNIFORM = ("none", "linear", "vert", "vertical", "horizontal")


def orientation_maps(shape, kind, strength, angle_deg=90.0):
    """Orientation(kind,strength) → wx/wy。空间模式返回 2D 图,均匀模式返回标量。

    返回 (wx, wy);strength=0 或 kind=none 返回 (None, None)(=等向)。
    """
    strength = float(strength or 0.0)
    kind = str(kind or "none").strip().lower()
    if strength <= 0.0 or kind in ("", "none"):
        return None, None
    if kind in _ORIENT_UNIFORM:
        ang = float(angle_deg) if kind in ("linear", "vert", "vertical") else 0.0
        w = orientation_weights(ang, strength)
        return float(w[0]), float(w[1])
    amap = orientation_angle_map(shape, kind, angle_deg)
    wx, wy = orientation_weight_maps(amap, strength)
    return wx.astype(np.float64), wy.astype(np.float64)


def advect_semi_lagrangian(u: np.ndarray, vx: np.ndarray, vy: np.ndarray,
                           dt: float, wrap: bool = False) -> np.ndarray:
    """半拉格朗日平流(Flow):u(t+dt, x) = u(t, x − v(x)·dt)。

    回溯脚点 y = x − v·dt 做双线性插值采样;常数场恒等;质量近似守恒
    (双线性不严格保质量,足够慢速度下漂移很小)。
    边界:wrap=True 周期采样;否则 clamp(越界取边界值)。
    净室说明:半拉格朗日平流是气象/图形常用对流格式(见公开教材 Stam 1999),
    双线性插值采样为标准实现。
    """
    dt = float(dt)
    n0, n1 = u.shape
    # 回溯坐标(网格格点坐标除以 1 即为体素索引;越界按 wrap/clamp)
    xf = np.empty_like(u, dtype=np.float64)
    yf = np.empty_like(u, dtype=np.float64)
    g = np.mgrid[0:n0, 0:n1]
    X = g[0].astype(np.float64)
    Y = g[1].astype(np.float64)
    xf = X - np.asarray(vx, dtype=np.float64) * dt
    yf = Y - np.asarray(vy, dtype=np.float64) * dt
    if wrap:
        xf = np.mod(xf, n0)
        yf = np.mod(yf, n1)
    else:
        np.clip(xf, 0, n0 - 1, out=xf)
        np.clip(yf, 0, n1 - 1, out=yf)
    x0 = np.floor(xf).astype(np.int64)
    y0 = np.floor(yf).astype(np.int64)
    x1 = np.minimum(x0 + 1, n0 - 1)
    y1 = np.minimum(y0 + 1, n1 - 1)
    tx = (xf - x0).astype(np.float64)
    ty = (yf - y0).astype(np.float64)
    # 双线性插值
    c00 = u[x0, y0]
    c01 = u[x0, y1]
    c10 = u[x1, y0]
    c11 = u[x1, y1]
    c0 = c00 * (1 - ty) + c01 * ty
    c1 = c10 * (1 - ty) + c11 * ty
    return (c0 * (1 - tx) + c1 * tx).astype(u.dtype)
