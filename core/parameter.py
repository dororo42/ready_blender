# -*- coding: utf-8 -*-
"""参数系统:类型化参数表(净室实现)。"""
import numpy as np


class ParameterTable:
    """参数表:名称→(默认, 最小, 最大);set() 自动裁剪。"""

    def __init__(self, spec=None):
        self.spec = dict(spec or {})
        self.values = {}
        for name, (d, lo, hi) in self.spec.items():
            self.values[name] = float(d)

    def set(self, name, value):
        if name not in self.spec:
            raise KeyError(name)
        _, lo, hi = self.spec[name]
        self.values[name] = float(np.clip(value, lo, hi))
        return self.values[name]

    def get(self, name, default=None):
        return self.values.get(name, default)

    def as_dict(self):
        return dict(self.values)


# 1d:图案缩放 s → Du/Dv × s²,子步保护显式欧拉稳定域 dt_eff·Du_eff ≤ 0.2(安全系数 0.8)
def scale_params(Du, Dv, dt, s):
    """图案缩放装配。

    数学:图案波长 λ ∝ √(D/速率),保 (F,k) 类型不变 → Du/Dv 同乘 s²。
    稳定性:s>1 时 D 增大越过 dt·Du≤0.25 硬边界,用 n_sub 子步把每步
    dt 缩小到 dt_eff = dt/n_sub,使 dt_eff·Du_eff ≤ 0.2。
    s=1 → (Du, Dv, dt, 1) 原样返回,零回归。
    """
    import math
    s = float(s)
    Du_eff = Du * s * s
    Dv_eff = Dv * s * s
    n_sub = max(1, int(math.ceil(Du_eff * float(dt) / 0.20)))
    return Du_eff, Dv_eff, float(dt) / n_sub, n_sub
