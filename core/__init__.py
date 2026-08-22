# -*- coding: utf-8 -*-
"""Ready→Blender 插件 · core 包(纯 Python+numpy,零 bpy 依赖)
净室实现:算法来自公开文献(Pearson 1993 等),不包含任何 Ready 源码翻译。
"""
from . import field, rule, ops, parameter, initial

__all__ = ["field", "rule", "ops", "parameter", "initial"]
