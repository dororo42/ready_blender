# -*- coding: utf-8 -*-
"""Rule 抽象(多变量原生)与 Gray-Scott 实现。净室实现,公式来自公开论文。"""
from __future__ import annotations
import numpy as np
from .ops import laplacian_5, graph_laplacian, laplacian_aniso_5, orientation_maps
from . import flow_field as _ff


class Rule:
    """反应扩散规则接口。fields: list[np.ndarray],按化学顺序。
    设计目标:后续任意 PDE/多变量系统只新增 Rule 子类,引擎不变。"""

    name = "base"
    n_chemicals = 0

    def update(self, fields, params, dt, field_kind="grid", nbr=None):
        raise NotImplementedError

    def describe_parameters(self):
        """返回 [(name, default, min, max), ...] 驱动 UI 动态生成。"""
        return []


class GrayScottRule(Rule):
    """Gray-Scott 两变量反应扩散(2 化学 a=u, b=v)。

    方程(净室源:Gray & Scott 1983-84;Pearson 1993):
      ∂a/∂t = Du·∇²a − a·b² + F·(1 − a)
      ∂b/∂t = Dv·∇²b + a·b² − (F + k)·b
    2D 规则网格:5 点拉普拉斯,dt 可配;clamp/wrap 边界由 field 决定。
    """

    name = "Gray-Scott"
    n_chemicals = 2

    _mesh_ext_cache = None  # (key, weights, vel) 顶点域扩展缓存

    def _mesh_ext(self, params, nbr):
        """3D 网格扩展:Orientation 各向异性边权重 + Flow 速度场(带缓存)。"""
        verts = params.get("mesh_verts")
        if verts is None:
            return None, None
        o_kind = params.get("orientation_kind", "none")
        o_str = float(params.get("orientation_strength", 0.0) or 0.0)
        f_kind = params.get("flow_kind", "none")
        f_str = float(params.get("flow_strength", 0.0) or 0.0)
        w = None
        vel = None
        if o_kind and o_kind != "none" and o_str > 0:
            key = ("o", id(verts), o_kind, round(o_str, 3), id(nbr[0]))
            if self._mesh_ext_cache and self._mesh_ext_cache[0] == key:
                w = self._mesh_ext_cache[1]
            else:
                try:
                    from .vertex_rd import orientation_vectors_3d, aniso_edge_weights
                    dirs = orientation_vectors_3d(verts, o_kind)
                    w = aniso_edge_weights(nbr[0], nbr[1], verts, dirs,
                                           min(o_str, 0.95))
                except Exception:
                    w = None
                self._mesh_ext_cache = (key, w, None)
        if f_kind and f_kind != "none" and f_str > 0:
            key = ("f", id(verts), f_kind, round(f_str, 4), id(nbr[0]))
            if self._mesh_ext_cache and self._mesh_ext_cache[0] == key:
                vel = self._mesh_ext_cache[2]
            else:
                try:
                    from .vertex_rd import velocity_field_3d
                    vel = velocity_field_3d(verts, f_kind, f_str)
                except Exception:
                    vel = None
                self._mesh_ext_cache = (key, None, vel)
        return w, vel

    def update(self, fields, params, dt, field_kind="grid", nbr=None):
        a, b = fields[0], fields[1]
        Du, Dv = params["Du"], params["Dv"]
        F, k = params["F"], params["k"]
        if field_kind == "grid":
            wrap = params.get("wrap", False)
            # Orientation(各向异性扩散):kind/strength → wx/wy(wx+wy≡2 保谱半径)
            o_kind = params.get("orientation_kind", "none")
            o_ang = params.get("orientation_angle", 90.0)
            o_str = params.get("orientation_strength", 0.0)
            wx, wy = orientation_maps(a.shape, o_kind, o_str, o_ang)
            if wx is not None and wy is not None:
                lap_a = laplacian_aniso_5(a, wx, wy, wrap)
                lap_b = laplacian_aniso_5(b, wx, wy, wrap)
            else:
                lap_a = laplacian_5(a, wrap)
                lap_b = laplacian_5(b, wrap)
        elif field_kind == "mesh":
            # 3D 扩展:Orientation(各向异性边权重,行归一化保稳定) + Flow(顶点平流)
            nbr_w = nbr[1]
            _w, _vel = self._mesh_ext(params, nbr)
            if _w is not None:
                nbr_w = _w
            lap_a = graph_laplacian(a, nbr[0], nbr_w)
            lap_b = graph_laplacian(b, nbr[0], nbr_w)
            if _vel is not None:
                try:
                    from .vertex_rd import advect_mesh
                    advect_mesh(a, params.get("mesh_verts"), _vel, dt, nbr[0])
                    advect_mesh(b, params.get("mesh_verts"), _vel, dt, nbr[0])
                except Exception:
                    pass
        else:
            raise ValueError(field_kind)
        abb = a * b * b
        # 就地更新(欧拉步进):先算好两个 laplacian 再写回,等价双缓冲
        a += (Du * lap_a - abb + F * (1.0 - a)) * dt
        b += (Dv * lap_b + abb - (F + k) * b) * dt
        # 数值防护(M0 遗留问题 #3):浓度物理边界裁剪,防止瞬态溢出→NaN;
        # b ∈ [0,1] 不改变斑图形态,a 上限放宽到 2 保留瞬态余量
        np.clip(a, 0.0, 2.0, out=a)
        np.clip(b, 0.0, 1.0, out=b)
        if field_kind == "grid":
            # Flow(半拉格朗日平流):kind/strength → 速度场,反应步后平流
            f_kind = params.get("flow_kind", "none")
            f_str = params.get("flow_strength", 0.0)
            if f_kind and f_kind != "none" and f_str:
                try:
                    vx, vy = _ff.velocity_field(a.shape, f_kind, f_str)
                except Exception:
                    vx = vy = None
                if vx is not None and vy is not None:
                    wrap = params.get("wrap", False)
                    from .ops import advect_semi_lagrangian
                    a[:] = advect_semi_lagrangian(a, vx, vy, dt, wrap=wrap)
                    b[:] = advect_semi_lagrangian(b, vx, vy, dt, wrap=wrap)
        return a, b

    def describe_parameters(self):
        # 净室说明:默认参数取 Pearson 1993 经典斑图参数(公开论文图例值)
        return [
            ("Du", 0.16, 0.0, 1.0),
            ("Dv", 0.08, 0.0, 1.0),
            ("F", 0.0367, 0.0, 0.2),
            ("k", 0.0649, 0.0, 0.2),
            ("dt", 1.0, 0.05, 2.0),
        ]


# ── Oil-Water 相分离(Agmon et al. 2014)─────────────────────────────
# 净室说明:算法思想与参数(排斥常数 0.7 / dt 0.05 / Moore 8 邻域 / 双场白噪声)
# 来自公开论文 Agmon, Gates, Churavy & Beer (2014) "Quantifying robustness in
# a spatial model of metabolism-boundary co-construction" (ALife 14),MIT Press。
# 本实现为独立 numpy 向量化编写,非任何现有代码翻译。

_MOORE = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]


def _bias(d):
    """Agmon 2014 偏置函数 bias(d) = d/(1-e^(-d)),d→0 时 →1。

    数值稳定分支(原式两侧各怕一头溢出):
      d ≥ 0: |d|/(1-e^(-|d|))            e^(-|d|)∈(0,1] 安全
      d < 0: |d|·e^(-|d|)/(1-e^(-|d|))   ≡ |d|/(e^{|d|}-1) 安全
    """
    d = np.asarray(d, dtype=np.float64)  # float32 下 1e-300 会下溢为 0
    ad = np.abs(d)
    denom = -np.expm1(-ad)  # 1-exp(-|d|) ∈ (0,1]
    safe = np.maximum(denom, 1e-300)  # d=0 时 0/0 → where 兜底,仅需压警告
    pos = ad / safe
    neg = ad * np.exp(-ad) / safe
    return np.where(d > 0.0, pos, np.where(d < 0.0, neg, 1.0))


class OilWaterRule(Rule):
    """油水相分离:两种互相排斥流体的偏置扩散(2 化学 a,b)。

    模型(净室源:Agmon et al. 2014):
      排斥势  R_a = c·b , R_b = c·a        (a 被 b 排斥,反之亦然)
      势场    P = R 的 3×3 邻域和(Moore 8 邻居 + 自身)
      通量    对每个邻居 t:
                流入 = bias(P_t − P_x)·chem_t
                流出 = bias(P_x − P_t)·chem_x
      更新    chem += dt · Σ(流入 − 流出),wrap 边界
    性质:逐对交换对称 → 总质量严格守恒(相分离特征:序参量演化,质量不变);
          每步末尾正性投影(非负 + 保质量 ⇒ 场有界,防 mesh 高连接度发散/NaN)。

    域支持:
      grid:2D 规则网格,Moore 8 邻域(np.roll wrap);
      mesh:3D 网格顶点/面域图邻域(nbr=(nbr_idx, nbr_w)),图推广版:
            势为邻域求和(与 Moore 9 项和同构),通量权重 w=1/max(1, K/8)
            (全局标量 → 逐对交换对称 → 质量守恒;K≤8 与 2D 版等强)。
    """

    name = "Oil-Water"
    n_chemicals = 2

    def update(self, fields, params, dt, field_kind="grid", nbr=None):
        a, b = fields[0], fields[1]
        c = float(params.get("repulsion", 0.7))
        tau = float(dt)  # 与 GS 同口径:签名 dt 承载时间步(引擎传 params["dt"])
        if field_kind == "mesh":
            return self._update_mesh(a, b, c, tau, nbr)
        if field_kind != "grid":
            raise ValueError(f"oil-water 不支持域类型: {field_kind}")
        # 排斥势(逐点)
        ra = c * b
        rb = c * a
        # 势场 P = 3×3 邻域和(含自身);np.roll 天然 wrap
        pa = ra.copy()
        pb = rb.copy()
        for dx, dy in _MOORE:
            pa += np.roll(ra, (dy, dx), axis=(0, 1))
            pb += np.roll(rb, (dy, dx), axis=(0, 1))
        # 通量累加:对 8 个邻居,流入/流出(bias 恒正,方向由势差决定)
        da = np.zeros_like(a)
        db = np.zeros_like(b)
        for dx, dy in _MOORE:
            # 邻居 t 的势场 = P 平移(-dy,-dx)方向?邻居位于 (x+dx, y+dy),
            # 其 P 值 = np.roll(P, (-dy,-dx)) 使 neighbor 值对齐到当前格
            pt_a = np.roll(pa, (-dy, -dx), axis=(0, 1))
            pt_b = np.roll(pb, (-dy, -dx), axis=(0, 1))
            a_t = np.roll(a, (-dy, -dx), axis=(0, 1))
            b_t = np.roll(b, (-dy, -dx), axis=(0, 1))
            delta_a = pa - pt_a  # 势差(center − neighbor)
            delta_b = pb - pt_b
            da += _bias(-delta_a) * a_t - _bias(delta_a) * a
            db += _bias(-delta_b) * b_t - _bias(delta_b) * b
        a += tau * da
        b += tau * db
        OilWaterRule._project_positive(a, b)
        return a, b

    @staticmethod
    def _update_mesh(a, b, c, tau, nbr):
        """图邻域版(Agmon 算法的图推广)。

        nbr=(nbr_idx, nbr_w):稠密 K 列平铺;填充槽位 idx==自身。
        与 2D Moore 版同尺度:势为邻域求和(不归一),
        通量权重 w=1/max(1, K/8)(K≤8 与 2D 等强;K>8 全局对称衰减防爆):
          P_x = R_x + Σ_{t∈N(x)} R_t
          Δchem_x = w·Σ_{t∈N(x)} [bias(P_t−P_x)·chem_t − bias(P_x−P_t)·chem_x]
        w 为全局标量 → 逐对交互对称 → 总质量守恒。
        """
        if nbr is None:
            raise ValueError("oil-water mesh 模式需要邻接表 nbr=(nbr_idx, nbr_w)")
        idx = nbr[0]
        n = len(a)
        k = int(idx.shape[1]) if idx.ndim == 2 else 0
        if k == 0:
            return a, b
        w_flux = 1.0 / max(1.0, k / 8.0)
        # 有效槽位:真实邻居(填充槽位 idx==自身,排除)
        slot_valid = (idx != np.arange(n)[:, None])
        sv = slot_valid.astype(a.dtype)
        ra = c * b
        rb = c * a
        # 势(含自身,邻域求和——与 2D Moore 9 项和同构)
        pa = ra + (ra[idx] * sv).sum(axis=1)
        pb = rb + (rb[idx] * sv).sum(axis=1)
        # 通量:对每真实邻居 t:
        #   Δ = w·[bias(P_t−P_x)·chem_t − bias(P_x−P_t)·chem_x]
        pt_a = pa[idx]
        pt_b = pb[idx]
        d_a = _bias(pt_a - pa[:, None]) * a[idx] - _bias(pa[:, None] - pt_a) * a[:, None]
        d_b = _bias(pt_b - pb[:, None]) * b[idx] - _bias(pb[:, None] - pt_b) * b[:, None]
        a += tau * w_flux * (d_a * sv).sum(axis=1)
        b += tau * w_flux * (d_b * sv).sum(axis=1)
        OilWaterRule._project_positive(a, b)
        return a, b

    @staticmethod
    def _project_positive(*fields):
        """正性投影(浓度非负),严格保质量:负值清零,亏欠按比例从正值扣除。

        必要性:Agmon 通量无极大值原理——单步流出系数
        tau·w·Σ_t bias(P_x−P_t) > 1 时值穿 0;势场(=c·对侧化学量)随负值
        翻转,逐对通量反向放大 → 振荡发散(mesh 顶点邻接 K≈12 时增益约为
        2D Moore 的 2 倍,细分立方体实测 ~85 步发散到 1e6 → inf/NaN,
        表现为视口突然全黑、RD_disp NaN 使 GN 位移把顶点推到无穷远)。
        投影后:质量守恒 + 非负 ⇒ 场有界于 [0, 总质量],发散不可能;
        温和参数区不产生负值时投影零激活,2D 行为逐位不变。
        """
        for x in fields:
            debt = float(np.where(x < 0.0, -x, 0.0).sum())
            if debt > 0.0:
                np.maximum(x, 0.0, out=x)
                pos_sum = float(x.sum())
                if pos_sum > 1e-12:
                    x *= max(pos_sum - debt, 0.0) / pos_sum
                else:
                    x[:] = 0.0

    def describe_parameters(self):
        return [
            ("repulsion", 0.7, 0.0, 2.0),
            ("dt", 0.05, 0.005, 0.2),
        ]
