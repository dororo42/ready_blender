# -*- coding: utf-8 -*-
"""numpy 后端:统一 step 接口的最小实现。净室实现。"""
import numpy as np

try:
    from ..core.rule import GrayScottRule
except ImportError:
    from core.rule import GrayScottRule


class NumpyBackend:
    """保底后端。step() 在给定 fields/rule 上执行 n 步。

    规则网格 fields: [np.ndarray, ...](shape=(H,W),就地更新)
    网格 fields:    [np.ndarray, ...](shape=(F,))+ nbr=(nbr_idx, nbr_w)
    """

    name = "numpy"
    capabilities = {"grid": True, "mesh": True, "volume": False}

    def __init__(self):
        self.steps_done = 0

    def step(self, rule, fields, params, n=1, field_kind="grid", nbr=None):
        # 审查修复(架构红线1):规则网格 Gray-Scott 走 fast_ops 优化内核(2.26x),
        # 其余路径保持通用循环。B7 修复:isinstance 判型。
        if (field_kind == "grid" and isinstance(rule, GrayScottRule)
                and len(fields) == 2 and fields[0].ndim == 2):
            try:
                from ..core.fast_ops import gray_scott_step_opt, gray_scott_step_aniso_opt
            except ImportError:
                from core.fast_ops import gray_scott_step_opt, gray_scott_step_aniso_opt
            a, b = fields[0], fields[1]
            Du = params.get("Du")
            Dv = params.get("Dv")
            F = params.get("F")
            k = params.get("k")
            dt = params.get("dt", 1.0)
            wrap = params.get("wrap", False)
            o_kind = params.get("orientation_kind", "none")
            o_str = params.get("orientation_strength", 0.0)
            f_kind = params.get("flow_kind", "none")
            f_str = params.get("flow_strength", 0.0)
            aniso = bool(o_str) and (o_kind or "").lower() not in ("", "none")
            flow = bool(f_kind and f_kind != "none" and f_str)
            lap_a = np.empty_like(a)
            lap_b = np.empty_like(b)
            abb = np.empty_like(a)
            if aniso:
                try:
                    from ..core.ops import orientation_maps
                except ImportError:
                    from core.ops import orientation_maps
                wx, wy = orientation_maps(
                    a.shape, o_kind, o_str,
                    params.get("orientation_angle", 90.0))
                if wx is None:
                    aniso = False
            else:
                wx = wy = None
            if flow:
                try:
                    from ..core.flow_field import velocity_field
                except ImportError:
                    from core.flow_field import velocity_field
                fvx, fvy = velocity_field(a.shape, f_kind, f_str)
            else:
                fvx = fvy = None
            n_eff = n * int(params.get("_n_sub", 1))  # 1d:Scale 子步
            use_aniso = aniso or flow  # 任一扩展参数启用 → aniso 核(含平流)
            for _ in range(n_eff):
                if use_aniso:
                    gray_scott_step_aniso_opt(a, b, Du, Dv, F, k, dt,
                                              wx, wy, wrap=wrap,
                                              vx=fvx, vy=fvy,
                                              lap_a=lap_a, lap_b=lap_b, abb=abb)
                else:
                    gray_scott_step_opt(a, b, Du, Dv, F, k, dt, wrap=wrap,
                                        lap_a=lap_a, lap_b=lap_b, abb=abb)
            self.steps_done += n
            return fields
        if field_kind == "grid":
            wrap = params.get("wrap", False)
            dt = params["dt"]
            p = dict(params)
            p["wrap"] = wrap
            for _ in range(n):
                rule.update(fields, p, dt, field_kind="grid")
        else:
            dt = params["dt"]
            for _ in range(n):
                rule.update(fields, dict(params), dt, field_kind="mesh", nbr=nbr)
        self.steps_done += n
        return fields
