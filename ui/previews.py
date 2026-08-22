# -*- coding: utf-8 -*-
"""预设缩略图预览集合(bpy.utils.previews 胶水层;实施阶段 1b)。

- 缩略图数组由 presets.pattern_map 实时渲染(本插件求解内核,净室);
- PNG 编码复用 pattern_map.png_encode_gray(最小 zlib+struct,无 PIL 依赖);
- 图标缓存:preset_id → icon_value,重复调用零成本;
- 无 bpy 或渲染失败时一律返回 0(Blender 显示普通文本项,不报错)。
"""
import bpy

try:
    from ..presets.pattern_map import render_pattern_thumbnail, png_encode_gray
    from ..presets.presets import get_preset
except ImportError:
    try:
        from presets.pattern_map import render_pattern_thumbnail, png_encode_gray
        from presets.presets import get_preset
    except ImportError:
        render_pattern_thumbnail = None
        png_encode_gray = None
        get_preset = None

_pc = None          # preview collection
_icon_cache = {}    # preset_id -> icon_value


def register():
    global _pc
    if _pc is None:
        _pc = bpy.utils.previews.new()


def unregister():
    global _pc, _icon_cache
    if _pc is not None:
        try:
            bpy.utils.previews.remove(_pc)
        except Exception:
            pass
        _pc = None
    _icon_cache.clear()


def _thumb_for_preset(preset_id):
    """GS 预设 → 24×24 缩略图数组;无 (F,k) 参数或失败返回 None。"""
    if get_preset is None or render_pattern_thumbnail is None:
        return None
    try:
        p = get_preset(preset_id)
        if p is None:
            return None
        params = p.get("params") or {}
        F = params.get("F")
        k = params.get("k")
        if F is None or k is None:
            return None
        return render_pattern_thumbnail(float(F), float(k),
                                        size=48, thumb=24, steps=250,
                                        seed=7, use_cache=True)
    except Exception:
        return None


def preset_icon(preset_id):
    """返回该预设的 icon_value;未生成/失败返回 0(不抛异常)。"""
    global _pc
    if _pc is None:
        return 0
    if preset_id in _icon_cache:
        return _icon_cache[preset_id]
    arr = _thumb_for_preset(preset_id)
    if arr is None or png_encode_gray is None:
        _icon_cache[preset_id] = 0
        return 0
    try:
        png = png_encode_gray(arr)
        name = f"rd_thumb_{preset_id}"
        img = _pc.load(name, png, "IMAGE")
        _icon_cache[preset_id] = img.icon_id
        return img.icon_id
    except Exception:
        _icon_cache[preset_id] = 0
        return 0