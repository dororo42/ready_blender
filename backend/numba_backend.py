# -*- coding: utf-8 -*-
"""Numba 可选后端:顶点域 RD 标量内核(与 core/vertex_rd 同源逻辑)。

分发与兼容策略(v1.4 报告 2.3 路线):
- 插件不捆绑 numba;用户在偏好设置里自助安装(镜像源可选);
- 运行时探测:未安装/不可用 → 自动回退 numpy 路径(结果逐位一致,可作回归基线);
- 安装后做 import numba 自检(而非仅依赖 pip 返回码)。
"""
from __future__ import annotations
import numpy as np

try:
    from numba import njit, prange
    import numba
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):
        def deco(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return deco

    def prange(n):
        return range(n)


@njit(cache=True)
def _rd_step_numba(U, V, v1, v2, degrees, boundary, du, dv, f, k, dt, n_verts):
    """顶点域一步(边界 Dirichlet 可选)。与 core/vertex_rd.rd_step_vertex 数值同源。"""
    sum_U = np.zeros(n_verts, dtype=np.float32)
    sum_V = np.zeros(n_verts, dtype=np.float32)
    n_edges = len(v1)
    for i in range(n_edges):
        a = v1[i]
        b = v2[i]
        sum_U[a] += U[b]
        sum_U[b] += U[a]
        sum_V[a] += V[b]
        sum_V[b] += V[a]
    has_boundary = boundary is not None and boundary.any()
    for i in range(n_verts):
        if has_boundary and boundary[i]:
            continue
        lap_U = sum_U[i] - degrees[i] * U[i]
        lap_V = sum_V[i] - degrees[i] * V[i]
        reaction = U[i] * V[i] * V[i]
        dU = (du * lap_U - reaction + f * (1.0 - U[i])) * dt
        dV = (dv * lap_V + reaction - (f + k) * V[i]) * dt
        U[i] += dU
        V[i] += dV
        if U[i] < 0.0:
            U[i] = 0.0
        elif U[i] > 1.0:
            U[i] = 1.0
        if V[i] < 0.0:
            V[i] = 0.0
        elif V[i] > 1.0:
            V[i] = 1.0
    if has_boundary:
        for i in range(n_verts):
            if boundary[i]:
                U[i] = 1.0
                V[i] = 0.0


def run_vertex_rd_numba(U, V, v1, v2, degrees, boundary, du, dv, f, k, dt, iterations):
    """numba 顶点域 RD。boundary 可为 None。"""
    n_verts = len(U)
    b = boundary.astype(np.bool_) if boundary is not None else None
    for _ in range(iterations):
        _rd_step_numba(U, V, v1, v2, degrees, b, du, dv, f, k, dt, n_verts)
    return U, V


def numba_status():
    """自检:numba 版本与可用性。返回 (available, message)。"""
    if not NUMBA_AVAILABLE:
        return False, "Numba 未安装(使用 numpy 回退)"
    try:
        return True, f"Numba 已就绪 (v{numba.__version__})"
    except Exception as e:
        return False, f"Numba 导入异常: {e}"


# ── 3D 体素 Gray-Scott(生长管道加速)────────────────────────────

@njit(cache=True, parallel=True)
def _gs3d_kernel(a, b, ta, tb, mask, du, dv, f, k, dt, steps):
    """3D Gray-Scott 连跑 steps 步(乒乓缓冲)。

    与 numpy 管道(core.field3d.GrayScottRule3D + simulate_growth_3d)同口径:
    7 点 clamp 拉普拉斯(越界邻居用自身补足)→ 欧拉步 → clip(a[0,2]/b[0,1])
    → Dirichlet 边界(a=1/b=0)。中间量 float64,回写 float32。

    mask 语义:True=活跃体素(求解),False=Dirichlet 框架(固定 a=1/b=0)。
    网格边界模式:mask=选中网格的内部体素(外壳即网格表面);
    自由盒模式:mask=全 True 且六壁 False(等价旧盒壁边界)。
    """
    n0, n1, n2 = a.shape
    aa = a
    bb = b
    for _ in range(steps):
        for i in prange(n0):
            for j in range(n1):
                for q in range(n2):
                    if not mask[i, j, q]:
                        ta[i, j, q] = 1.0
                        tb[i, j, q] = 0.0
                        continue
                    ua = aa[i, j, q]
                    ub = bb[i, j, q]
                    la = -6.0 * ua
                    lb = -6.0 * ub
                    if i > 0:
                        la += aa[i - 1, j, q]; lb += bb[i - 1, j, q]
                    else:
                        la += ua; lb += ub
                    if i < n0 - 1:
                        la += aa[i + 1, j, q]; lb += bb[i + 1, j, q]
                    else:
                        la += ua; lb += ub
                    if j > 0:
                        la += aa[i, j - 1, q]; lb += bb[i, j - 1, q]
                    else:
                        la += ua; lb += ub
                    if j < n1 - 1:
                        la += aa[i, j + 1, q]; lb += bb[i, j + 1, q]
                    else:
                        la += ua; lb += ub
                    if q > 0:
                        la += aa[i, j, q - 1]; lb += bb[i, j, q - 1]
                    else:
                        la += ua; lb += ub
                    if q < n2 - 1:
                        la += aa[i, j, q + 1]; lb += bb[i, j, q + 1]
                    else:
                        la += ua; lb += ub
                    abb = ua * ub * ub
                    na = ua + (du * la - abb + f * (1.0 - ua)) * dt
                    nb = ub + (dv * lb + abb - (f + k) * ub) * dt
                    if na < 0.0:
                        na = 0.0
                    elif na > 2.0:
                        na = 2.0
                    if nb < 0.0:
                        nb = 0.0
                    elif nb > 1.0:
                        nb = 1.0
                    ta[i, j, q] = na
                    tb[i, j, q] = nb
        aa, ta = ta, aa
        bb, tb = tb, bb
    # 结果回写调用方数组(奇数步时最新数据在临时缓冲)
    for i in range(n0):
        for j in range(n1):
            for q in range(n2):
                a[i, j, q] = aa[i, j, q]
                b[i, j, q] = bb[i, j, q]


def run_gs3d_numba(a, b, params, steps, domain_mask=None):
    """numba 3D Gray-Scott(clip + Dirichlet 框架),就地更新 a/b。

    与 numpy 路径数值同口径(float64 中间量,微小舍入差)。
    domain_mask:可选 (N,N,N) bool 网格内部掩码;None=自由盒(盒壁框架)。
    """
    if not NUMBA_AVAILABLE:
        raise RuntimeError("numba 不可用(应先探测 NUMBA_AVAILABLE)")
    if steps <= 0:
        return a, b
    if domain_mask is not None:
        mask = np.ascontiguousarray(np.asarray(domain_mask, dtype=np.bool_))
    else:
        # 自由盒:全 True + 六壁 False(等价旧盒壁 Dirichlet)
        mask = np.ones(a.shape, dtype=np.bool_)
        mask[0, :, :] = False; mask[-1, :, :] = False
        mask[:, 0, :] = False; mask[:, -1, :] = False
        mask[:, :, 0] = False; mask[:, :, -1] = False
    ta = np.empty_like(a)
    tb = np.empty_like(b)
    _gs3d_kernel(a, b, ta, tb, mask,
                 float(params["Du"]), float(params["Dv"]),
                 float(params["F"]), float(params["k"]),
                 float(params.get("dt", 1.0)), int(steps))
    return a, b
