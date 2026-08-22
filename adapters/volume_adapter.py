# -*- coding: utf-8 -*-
"""Volume 输出适配(P3-2):3D 体素场 → Blender Volume / 点云 / 等值面。

OpenVDB 评估结论(2026-08 核验):
  - PyPI 存在 openvdb wheel,但仅限特定平台/ABI(win/manylinux/macOS x86_64),
    Blender 内置 Python 3.11 的 cp311 标签覆盖不全;
  - extensions.blender.org ToS 3.6 禁原生 wheels → 平台分发受阻;
  - 结论:第一版不依赖 OpenVDB,采用自研稀疏体素存储 + 点云/切片输出;
    OpenVDB 支持作为自托管分发的可选增强。
"""
from __future__ import annotations
import numpy as np


class SparseVolume:
    """稀疏体素存储:仅存活性 voxel(浓度超阈值)。净室实现。"""

    def __init__(self, shape, threshold=0.1):
        self.shape = tuple(shape)
        self.threshold = threshold

    def from_field(self, field3d):
        """从稠密场提取活性 voxel。返回 (indices (N,3) int32, values (N,) float32)。"""
        mask = field3d > self.threshold
        idx = np.argwhere(mask).astype(np.int32)
        vals = field3d[mask].astype(np.float32)
        return idx, vals

    def to_points(self, field3d, origin=(0, 0, 0), spacing=(1, 1, 1)):
        """活性 voxel → 点坐标(可写 Blender 点云)。"""
        idx, vals = self.from_field(field3d)
        pts = origin + idx * np.array(spacing, dtype=np.float32)
        return pts, vals


def marching_cubes_naive(field3d, level=0.5):
    """朴素等值面抽取(教学级实现,小网格用)。

    说明:完整 Marching Cubes 查表实现约 300 行,列后续增量;
    此版提供阈值面元(active cells)→ 网格的直接映射,用于 3D 可视化起步。
    """
    mask = field3d > level
    # 输出 active voxel 的表面面片(6 个方向邻居中有非 active 的 voxel)
    faces = []
    verts = []
    idx = np.argwhere(mask).astype(np.int32)
    vmap = {}
    for i, j, k in idx:
        # 6 邻居中任一非 active → 该 voxel 是表面
        is_surface = False
        for di, dj, dk in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
            ni, nj, nk = i+di, j+dj, k+dk
            if (0 <= ni < field3d.shape[0] and 0 <= nj < field3d.shape[1]
                    and 0 <= nk < field3d.shape[2] and not mask[ni, nj, nk]):
                is_surface = True
                break
            if not (0 <= ni < field3d.shape[0] and 0 <= nj < field3d.shape[1]
                    and 0 <= nk < field3d.shape[2]):
                is_surface = True
                break
        if not is_surface:
            continue
        # 8 角顶点(去重)
        corners = []
        for oi in (0, 1):
            for oj in (0, 1):
                for ok in (0, 1):
                    p = (i+oi, j+oj, k+ok)
                    if p not in vmap:
                        vmap[p] = len(verts)
                        verts.append(p)
                    corners.append(vmap[p])
        # 6 个面(两三角形)只保留朝向非 active 侧的面
        face_defs = [
            ([0,1,3,2], (0,0,-1)),  # k- 面
            ([4,5,7,6], (0,0,1)),   # k+ 面
            ([0,2,6,4], (0,-1,0)),  # j- 面
            ([1,3,7,5], (0,1,0)),   # j+ 面
            ([0,1,5,4], (-1,0,0)),  # i- 面
            ([2,3,7,6], (1,0,0)),   # i+ 面
        ]
        for quad, d in face_defs:
            ni, nj, nk = i+d[0], j+d[1], k+d[2]
            outside = not (0 <= ni < field3d.shape[0] and 0 <= nj < field3d.shape[1]
                           and 0 <= nk < field3d.shape[2]) or not mask[ni, nj, nk]
            if outside:
                faces.append([corners[quad[0]], corners[quad[1]], corners[quad[2]]])
                faces.append([corners[quad[0]], corners[quad[2]], corners[quad[3]]])
    return np.array(verts, dtype=np.float32), np.array(faces, dtype=np.int32)


def surface_nets_smooth(field3d, level=0.5, smooth_iterations=1):
    """Naive Surface Nets 等值面提取(光滑版)。

    与 marching_cubes_naive(体素面元,棱角方)相对:
    - 每个"表面单元"(8 角不全同侧)在 12 条棱的线性插值交点均值处放一个顶点;
    - 相邻表面单元的顶点按跨越的格点棱连四边形,再拆三角形;
    - 法线按场值侧别逐面定向(内侧在棱起点 → 法线指 +轴),保证朝外;
    - 可选拉普拉斯平滑迭代(smooth_iterations)进一步圆润表面。
    返回与 MC 同签名:(verts (V,3) float32, faces (F,3) int32)。
    """
    f = np.asarray(field3d)
    n0, n1, n2 = f.shape
    empty_v = np.zeros((0, 3), dtype=np.float32)
    empty_f = np.zeros((0, 3), dtype=np.int32)
    if n0 < 2 or n1 < 2 or n2 < 2:
        return empty_v, empty_f
    mask = f > level
    if not mask.any() or mask.all():
        return empty_v, empty_f
    # 表面单元:8 角不全同侧
    csum = np.zeros((n0 - 1, n1 - 1, n2 - 1), dtype=np.int32)
    for di in (0, 1):
        for dj in (0, 1):
            for dk in (0, 1):
                csum += mask[di:di + n0 - 1, dj:dj + n1 - 1, dk:dk + n2 - 1]
    ci, cj, ck = np.nonzero((csum > 0) & (csum < 8))
    n_cells = len(ci)
    if n_cells == 0:
        return empty_v, empty_f
    vidx = np.full((n0 - 1, n1 - 1, n2 - 1), -1, dtype=np.int64)
    vidx[ci, cj, ck] = np.arange(n_cells)

    # 顶点 = 单元 12 条棱的线性插值交点均值
    edges = [
        ((0, 0, 0), (1, 0, 0)), ((0, 1, 0), (1, 1, 0)),
        ((0, 0, 1), (1, 0, 1)), ((0, 1, 1), (1, 1, 1)),
        ((0, 0, 0), (0, 1, 0)), ((1, 0, 0), (1, 1, 0)),
        ((0, 0, 1), (0, 1, 1)), ((1, 0, 1), (1, 1, 1)),
        ((0, 0, 0), (0, 0, 1)), ((1, 0, 0), (1, 0, 1)),
        ((0, 1, 0), (0, 1, 1)), ((1, 1, 0), (1, 1, 1)),
    ]
    px = np.zeros(n_cells, dtype=np.float64)
    py = np.zeros(n_cells, dtype=np.float64)
    pz = np.zeros(n_cells, dtype=np.float64)
    cnt = np.zeros(n_cells, dtype=np.int32)
    for (oa, ob, oc), (pa, pb, pc) in edges:
        va = f[ci + oa, cj + ob, ck + oc]
        vb = f[ci + pa, cj + pb, ck + pc]
        cross = (va > level) != (vb > level)
        if not cross.any():
            continue
        denom = vb - va
        safe = np.where(denom != 0.0, denom, 1.0)
        t = np.where(cross, (level - va) / safe, 0.0)
        px[cross] += ci[cross] + oa + t[cross] * (pa - oa)
        py[cross] += cj[cross] + ob + t[cross] * (pb - ob)
        pz[cross] += ck[cross] + oc + t[cross] * (pc - oc)
        cnt[cross] += 1
    c_safe = np.maximum(cnt, 1)
    verts = np.stack([px / c_safe, py / c_safe, pz / c_safe], axis=1).astype(np.float32)

    # 四边形组装:三个方向的跨越格点棱,各连 4 个相邻表面单元的顶点
    quad_blocks = []

    def _push(q1, q2, q3, q4, inside_start):
        ok = (q1 >= 0) & (q2 >= 0) & (q3 >= 0) & (q4 >= 0)
        if not ok.any():
            return
        quad_blocks.append((q1[ok], q2[ok], q3[ok], q4[ok], inside_start[ok]))

    # x 向棱 (i,j,k)-(i+1,j,k):+x 法线绕向 (j-1,k-1)→(j,k-1)→(j,k)→(j-1,k)
    if n1 >= 3 and n2 >= 3:
        cx = mask[:-1, 1:n1 - 1, 1:n2 - 1] != mask[1:, 1:n1 - 1, 1:n2 - 1]
        ii, jj, kk = np.nonzero(cx)
        if len(ii):
            j = jj + 1
            k = kk + 1
            _push(vidx[ii, j - 1, k - 1], vidx[ii, j, k - 1],
                  vidx[ii, j, k], vidx[ii, j - 1, k], mask[ii, j, k])
    # y 向棱 (i,j,k)-(i,j+1,k):+y 法线绕向 (i-1,k-1)→(i-1,k)→(i,k)→(i,k-1)
    if n0 >= 3 and n2 >= 3:
        cy = mask[1:n0 - 1, :-1, 1:n2 - 1] != mask[1:n0 - 1, 1:, 1:n2 - 1]
        ii, jj, kk = np.nonzero(cy)
        if len(ii):
            i = ii + 1
            k = kk + 1
            _push(vidx[i - 1, jj, k - 1], vidx[i - 1, jj, k],
                  vidx[i, jj, k], vidx[i, jj, k - 1], mask[i, jj, k])
    # z 向棱 (i,j,k)-(i,j,k+1):+z 法线绕向 (i-1,j-1)→(i,j-1)→(i,j)→(i-1,j)
    if n0 >= 3 and n1 >= 3:
        cz = mask[1:n0 - 1, 1:n1 - 1, :-1] != mask[1:n0 - 1, 1:n1 - 1, 1:]
        ii, jj, kk = np.nonzero(cz)
        if len(ii):
            i = ii + 1
            j = jj + 1
            _push(vidx[i - 1, j - 1, kk], vidx[i, j - 1, kk],
                  vidx[i, j, kk], vidx[i - 1, j, kk], mask[i, j, kk])

    tri_blocks = []
    for q1, q2, q3, q4, ins in quad_blocks:
        t1 = np.stack([q1, q2, q3], axis=1)
        t2 = np.stack([q1, q3, q4], axis=1)
        flip = (~ins)[:, None]  # 棱起点在外侧 → 法线应指 -轴 → 反转绕向
        t1 = np.where(flip, t1[:, ::-1], t1)
        t2 = np.where(flip, t2[:, ::-1], t2)
        tri_blocks.append(t1)
        tri_blocks.append(t2)
    faces = (np.concatenate(tri_blocks).astype(np.int32)
             if tri_blocks else empty_f)

    # 可选拉普拉斯平滑(邻接均值松弛,α=0.5)
    for _ in range(int(smooth_iterations)):
        if len(faces) == 0 or len(verts) == 0:
            break
        e = faces[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
        e = np.unique(np.sort(e, axis=1), axis=0)
        a_i, b_i = e[:, 0], e[:, 1]
        nv = len(verts)
        sx = np.zeros(nv)
        sy = np.zeros(nv)
        sz = np.zeros(nv)
        cn = np.zeros(nv)
        np.add.at(sx, a_i, verts[b_i, 0])
        np.add.at(sx, b_i, verts[a_i, 0])
        np.add.at(sy, a_i, verts[b_i, 1])
        np.add.at(sy, b_i, verts[a_i, 1])
        np.add.at(sz, a_i, verts[b_i, 2])
        np.add.at(sz, b_i, verts[a_i, 2])
        np.add.at(cn, a_i, 1.0)
        np.add.at(cn, b_i, 1.0)
        has = cn > 0
        c2 = np.maximum(cn, 1.0)
        tgt = np.stack([sx / c2, sy / c2, sz / c2], axis=1)
        verts[has] = (verts[has] + 0.5 * (tgt[has] - verts[has])).astype(np.float32)
    return verts, faces


# ── 3D 生长管道(净室)──────────────────────────────────────────────
# 口径源:Ready 生态 grayscott_3D.vti 的公开参数与初始生成器描述
#   (Du=0.082/Dv=0.041/F=0.035/k=0.064/dt=1;a=1 全域;
#    b 为矩形区域白噪声 [0,1),且 a -= b)。
# 本函数按上述口径独立实现(方向:框架边界内生长结构管道)。

def voxelize_mesh(verts, faces, size, chunk_faces=512):
    """三角网格 → 体素内部掩码(射线奇偶法,无 bpy 依赖)。

    网格包围盒铺 N³ 体素;沿 +x 射线束(过每体素中心列)与三角面求交,
    前缀交点数奇偶判定内外(第 1 次穿入、第 2 次穿出……)。
    要求网格基本水密(开口网格奇偶可能误判)。

    参数:
        verts: (V,3) float 顶点
        faces: (F,3) int 三角面
        size: 每轴体素数 N
        chunk_faces: 分块面数(控内存,M×F 广播)
    返回:
        (mask (N,N,N) bool, bbox_min (3,), bbox_size (3,))
        体素 (i,j,k) 中心 = bbox_min + (idx+0.5)/N · bbox_size
    """
    v = np.asarray(verts, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    n = int(size)
    bb_min = v.min(axis=0)
    bb_max = v.max(axis=0)
    bb_size = np.maximum(bb_max - bb_min, 1e-9)
    # 体素中心坐标(每轴)
    ax = [bb_min[d] + (np.arange(n) + 0.5) / n * bb_size[d] for d in range(3)]
    # 射线束:沿 +x,过每个 (y_j, z_k)
    yf, zf = np.meshgrid(ax[1], ax[2], indexing="ij")
    yf = yf.ravel()
    zf = zf.ravel()
    m = len(yf)
    # 每射线交点计数直方图 → 前缀和奇偶
    counts = np.zeros((m, n), dtype=np.int32)
    dx = bb_size[0] / n
    for s in range(0, len(f), chunk_faces):
        tri = v[f[s:s + chunk_faces]]  # (C,3,3)
        x1, y1, z1 = tri[:, 0, 0], tri[:, 0, 1], tri[:, 0, 2]
        x2, y2, z2 = tri[:, 1, 0], tri[:, 1, 1], tri[:, 1, 2]
        x3, y3, z3 = tri[:, 2, 0], tri[:, 2, 1], tri[:, 2, 2]
        # yz 平面投影重心坐标(P=(yf,zf) 在投影三角形内 → α,β,γ ≥ 0)
        den = (y2 - y1) * (z3 - z1) - (y3 - y1) * (z2 - z1)  # (C,)
        ok = np.abs(den) > 1e-12
        if not ok.any():
            continue
        # 广播 (C,) × (M,) → (C,M);逐块控内存;退化面安全分母(结果被 ok 掩蔽)
        yy = yf[None, :]
        zz = zf[None, :]
        d = np.where(ok, den, 1.0)[:, None]
        alpha = ((y2 - y1)[:, None] * (zz - z1[:, None])
                 - (z2 - z1)[:, None] * (yy - y1[:, None])) / d
        beta = ((z3 - z1)[:, None] * (yy - y1[:, None])
                - (y3 - y1)[:, None] * (zz - z1[:, None])) / d
        gamma = 1.0 - alpha - beta
        inside = (alpha >= 0) & (beta >= 0) & (gamma >= 0)
        inside &= ok[:, None]
        if not inside.any():
            continue
        # 交点 x(3D 重心插值;α 对应顶点1,β 顶点2,γ 顶点3)
        x_hit = (alpha * x1[:, None] + beta * x2[:, None]
                 + gamma * x3[:, None])
        ci, mi = np.nonzero(inside)  # 面索引,射线索引
        bins = np.floor((x_hit[ci, mi] - bb_min[0]) / dx).astype(np.int64)
        np.clip(bins, 0, n - 1, out=bins)
        np.add.at(counts, (mi, bins), 1)
    # 前缀交点数奇偶 = 内部(第 1 次穿入后)
    parity = np.cumsum(counts, axis=1) % 2 == 1
    # 射线索引序为 (y,z),parity (M,N0)=(y·N2+z, x_bin) → 转置为 (x,y,z)
    mask = np.ascontiguousarray(parity.reshape(n, n, n).transpose(2, 0, 1))
    return mask, bb_min.astype(np.float32), bb_size.astype(np.float32)


def simulate_growth_3d(size=48, steps=1500, params=None, seed=42,
                       threshold=0.35, seed_box=None,
                       progress_cb=None, method="surfnets", smooth_iterations=1,
                       use_numba=None, domain_mask=None):
    """3D Gray-Scott 管道生长全流程(无 bpy,可测)。

    流程:体素容器 → 白噪声种子 → Dirichlet 边界迭代
    (边界壳固定 a=1/b=0,构成"框架") → 等值面抽取。

    参数:
        size: 每轴体素数 N(场为 N³;耗时与内存 ≈ N³)
        steps: 迭代步数
        params: {"Du","Dv","F","k"}(dt 恒为 1,文献口径)
        seed: 随机种子(白噪声可复现)
        threshold: b 场等值面阈值
        seed_box: 相对坐标矩形 ((x0,y0,z0),(x1,y1,z1)),各分量 ∈ [0,1];
                  None=自动(有 domain_mask 时取掩码中心区域,否则取文献口径角落盒)
        progress_cb: 可选回调 progress_cb(progress∈[0,1]),约每 2% 调一次
        method: "surfnets"(默认,Surface Nets 光滑提取)或 "voxel"(体素面元)
        smooth_iterations: Surface Nets 拉普拉斯平滑迭代(0 关闭)
        use_numba: None=装了 numba 就用;True=同 None;False=强制 numpy
        domain_mask: 可选 (N,N,N) bool,选中网格体素化后的内部掩码。
                     提供时:网格表面(掩码外壳)为 Dirichlet 生长框架,
                     种子放掩码中心,生长完全限制在网格内部。
    返回:
        (verts (V,3) float32 坐标, faces (F,3) int32, b 场 (N,N,N))
        verts 坐标域 [0,N-1],调用方自行居中/缩放。
    """
    try:
        from ..core.field3d import GrayScottRule3D
    except ImportError:
        from core.field3d import GrayScottRule3D

    n = int(size)
    p = {"Du": 0.082, "Dv": 0.041, "F": 0.035, "k": 0.064}
    if params:
        p.update({k2: float(params[k2]) for k2 in ("Du", "Dv", "F", "k")
                  if params.get(k2) is not None})

    if domain_mask is not None:
        domain_mask = np.asarray(domain_mask, dtype=np.bool_)
        if domain_mask.shape != (n, n, n):
            raise ValueError(f"domain_mask 形状 {domain_mask.shape} 与场 ({n},)*3 不符")
        if not domain_mask.any():
            raise ValueError("domain_mask 全空:网格体素化后无内部体素")

    a = np.ones((n, n, n), dtype=np.float32)
    b = np.zeros((n, n, n), dtype=np.float32)

    # 白噪声种子:
    # - domain_mask:掩码质心为中心的立方区域(约 25% 边长),生长自中心
    #   向网格边界均匀扩展(避免角落偏斜/破碎多组分)
    # - 无 mask:文献口径角落矩形盒(默认 ((0.2,0.2,0.3),(0.4,0.5,0.5)))
    rng = np.random.default_rng(seed)
    if domain_mask is not None:
        idx = np.argwhere(domain_mask)
        center = idx.mean(axis=0)
        half = max(2, int(n * 0.125))
        lo = np.maximum(center - half, 1).astype(int)
        hi = np.minimum(center + half, n - 1).astype(int)
        region = np.zeros_like(domain_mask)
        region[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] = True
        region &= domain_mask
        if region.any():
            b[region] = rng.uniform(0.0, 1.0, int(region.sum())).astype(np.float32)
            a[region] -= b[region]
    else:
        if seed_box is None:
            seed_box = ((0.2, 0.2, 0.3), (0.4, 0.5, 0.5))
        (x0, y0, z0), (x1, y1, z1) = seed_box
        i0, i1 = max(1, int(x0 * n)), min(n - 1, int(x1 * n))
        j0, j1 = max(1, int(y0 * n)), min(n - 1, int(y1 * n))
        k0, k1 = max(1, int(z0 * n)), min(n - 1, int(z1 * n))
        if i1 > i0 and j1 > j0 and k1 > k0:
            box = (slice(i0, i1), slice(j0, j1), slice(k0, k1))
            b[box] = rng.uniform(0.0, 1.0, (i1 - i0, j1 - j0, k1 - k0)).astype(np.float32)
            a[box] -= b[box]

    # 求解:numba 快路径(装好且未强制关闭)或 numpy 基线,数值同口径
    use_fast = False
    if use_numba is not False:
        try:
            from ..backend.numba_backend import NUMBA_AVAILABLE
        except ImportError:
            from backend.numba_backend import NUMBA_AVAILABLE
        use_fast = bool(NUMBA_AVAILABLE)

    if use_fast:
        try:
            from ..backend.numba_backend import run_gs3d_numba
        except ImportError:
            from backend.numba_backend import run_gs3d_numba
        chunk = max(1, steps // 50)
        done = 0
        while done < steps:
            m = min(chunk, steps - done)
            run_gs3d_numba(a, b, p, m, domain_mask=domain_mask)
            done += m
            if progress_cb is not None:
                progress_cb(done / max(steps, 1))
    else:
        rule = GrayScottRule3D()
        notify_every = max(1, steps // 50)
        for step in range(steps):
            rule.update([a, b], p, dt=1.0, wrap=False)
            # 数值防护(与 2D 内核同口径)
            np.clip(a, 0.0, 2.0, out=a)
            np.clip(b, 0.0, 1.0, out=b)
            if domain_mask is not None:
                # Dirichlet:网格表面(掩码外壳)与外部固定 a=1/b=0
                a[~domain_mask] = 1.0
                b[~domain_mask] = 0.0
            else:
                # Dirichlet 边界壳(方盒框架)
                a[0, :, :] = 1.0; a[-1, :, :] = 1.0
                a[:, 0, :] = 1.0; a[:, -1, :] = 1.0
                a[:, :, 0] = 1.0; a[:, :, -1] = 1.0
                b[0, :, :] = 0.0; b[-1, :, :] = 0.0
                b[:, 0, :] = 0.0; b[:, -1, :] = 0.0
                b[:, :, 0] = 0.0; b[:, :, -1] = 0.0
            if progress_cb is not None and step % notify_every == 0:
                progress_cb(step / max(steps, 1))

    if method == "voxel":
        verts, faces = marching_cubes_naive(b, level=threshold)
    else:
        verts, faces = surface_nets_smooth(b, level=threshold,
                                           smooth_iterations=smooth_iterations)
    return verts, faces, b
