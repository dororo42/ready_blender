# -*- coding: utf-8 -*-
"""初始条件与参数辅助。净室实现。"""
import numpy as np


def constant(shape, value):
    return np.full(shape, value, dtype=np.float32)


def uniform_noise(shape, low=0.0, high=1.0, rng=None):
    rng = rng or np.random.default_rng()
    return rng.uniform(low, high, shape).astype(np.float32)


def center_rect(field, rect, value):
    """在规则网格上写矩形区域。rect=(x0,y0,x1,y1) 网格坐标,闭区间。"""
    x0, y0, x1, y1 = rect
    field.data[max(0, y0):min(field.shape[0], y1 + 1),
               max(0, x0):min(field.shape[1], x1 + 1)] = value
    return field
