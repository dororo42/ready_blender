# -*- coding: utf-8 -*-
"""元胞自动机规则(Conway Life / Larger-than-Life / SmoothLife 简化版)。净室实现,规则来自公开文献。"""
from __future__ import annotations
import numpy as np


def neighbor_count_8(u: np.ndarray, wrap: bool = True) -> np.ndarray:
    """8 邻居计数(Moore 邻域)。审查修复:clamp 边界用常数 0 填充(界外视为死亡),
    避免 edge 填充把角落 cell 自身计 3 次。"""
    if wrap:
        total = sum(
            np.roll(np.roll(u, dx, 0), dy, 1)
            for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)
        )
    else:
        up = np.pad(u, 1, mode="constant")
        total = np.zeros_like(u)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (dx, dy) == (0, 0):
                    continue
                total += up[1 + dx:1 + dx + u.shape[0], 1 + dy:1 + dy + u.shape[1]]
    return total


def neighbor_count_radius(u: np.ndarray, r: int, wrap: bool = True) -> np.ndarray:
    """半径 r 的邻居计数(Larger-than-Life 用,大半径时较慢,仅供小网格)。"""
    if wrap:
        total = np.zeros_like(u)
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx == 0 and dy == 0:
                    continue
                total += np.roll(np.roll(u, dx, 0), dy, 1)
        return total
    up = np.pad(u, r, mode="constant")
    total = np.zeros_like(u)
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            if dx == 0 and dy == 0:
                continue
            total += up[r + dx:r + dx + u.shape[0], r + dy:r + dy + u.shape[1]]
    return total


class ConwayLifeRule:
    """Conway 生命游戏 B3/S23。二值场(0/1)。规则源:Gardner 1970(Sci. Am.)。"""
    name = "ConwayLife"
    n_chemicals = 1

    def update(self, fields, params=None, dt=1.0, field_kind="grid", nbr=None, wrap=True):
        u = fields[0]
        c = neighbor_count_8(u, wrap)
        born = (u == 0) & (c == 3)
        survive = (u == 1) & ((c == 2) | (c == 3))
        u[:] = np.where(born | survive, 1, 0)
        return fields

    def describe_parameters(self):
        return []


class LargerThanLifeRule:
    """Larger-than-Life 连续规则(B1/S1 参数族,Evans 1996-2000 文献)。

    参数:r 半径,b_low/b_high 出生区间,s_low/s_high 存活区间。
    """
    name = "LargerThanLife"
    n_chemicals = 1

    def update(self, fields, params=None, dt=1.0, field_kind="grid", nbr=None, wrap=True):
        u = fields[0]
        p = params or {}
        r = int(p.get("r", 3))
        b_lo, b_hi = p.get("b_low", 0.2), p.get("b_high", 0.4)
        s_lo, s_hi = p.get("s_low", 0.2), p.get("s_high", 0.4)
        n_total = (2 * r + 1) ** 2 - 1
        c = neighbor_count_radius(u, r, wrap) / n_total
        born = (u == 0) & (c >= b_lo) & (c <= b_hi)
        survive = (u == 1) & (c >= s_lo) & (c <= s_hi)
        u[:] = np.where(born | survive, 1, 0)
        return fields

    def describe_parameters(self):
        return [("r", 3, 1, 10), ("b_low", 0.2, 0, 1), ("b_high", 0.4, 0, 1),
                ("s_low", 0.2, 0, 1), ("s_high", 0.4, 0, 1)]


class SmoothLifeRule:
    """SmoothLife 简化连续版(Rafler 2011 思路的轻量实现)。

    说明:完整 SmoothLife 需要 FFT 卷积;本版用 r=1 邻域 + 连续化规则,
    产生类似效果的连续图案,性能与精度取舍在 P3-4 优化。
    """
    name = "SmoothLife"
    n_chemicals = 1

    def update(self, fields, params=None, dt=1.0, field_kind="grid", nbr=None, wrap=True):
        u = fields[0]
        p = params or {}
        alpha = p.get("alpha", 0.028)
        b1, b2 = p.get("b1", 0.278), p.get("b2", 0.365)
        d1, d2 = p.get("d1", 0.267), p.get("d2", 0.445)
        if wrap:
            m = sum(np.roll(np.roll(u, dx, 0), dy, 1) for dx in (-1, 0, 1) for dy in (-1, 0, 1)) / 9.0
        else:
            up = np.pad(u, 1, mode="edge")
            m = sum(up[1+dx:1+dx+u.shape[0], 1+dy:1+dy+u.shape[1]] for dx in (-1,0,1) for dy in (-1,0,1)) / 9.0
        alive = _smooth_interval(m, b1, b2)
        dead = _smooth_interval(m, d1, d2)
        delta = alive * (1 - u) * (dt * 60 * alpha) - dead * u * (dt * 60 * alpha)
        u[:] = np.clip(u + delta, 0, 1)
        return fields

    def describe_parameters(self):
        return [("alpha", 0.028, 0, 0.1), ("b1", 0.278, 0, 1), ("b2", 0.365, 0, 1),
                ("d1", 0.267, 0, 1), ("d2", 0.445, 0, 1)]


def _smooth_interval(x, lo, hi):
    """区间 [lo,hi] 的平滑指示函数(sigmoid 过渡)。"""
    return 1.0 / (1.0 + np.exp(-60 * (x - lo))) * (1.0 - 1.0 / (1.0 + np.exp(-60 * (x - hi))))
