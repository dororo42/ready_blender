# -*- coding: utf-8 -*-
"""ui/previews.py 兼容层修复:Blender 4.2+ 部分版本已移除 bpy.utils.previews。

降级策略:previews 集合不可用时,register() 静默跳过、preset_icon() 恒返回 0,
预设下拉退化为纯文本枚举(功能不受影响,仅无缩略图)。任何异常不向外抛。
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

_pc = None          # preview collection(不可用时保持 None)
_icon_cache = {}    # preset_id -> icon_value
_previews_mod = None  # bpy.utils.previews 模块引用;缺失为 None


def _detect_previews():
    """探测 bpy.utils.previews 是否可用(Blender 4.2+ 部分版本已移除)。"""
    global _previews_mod
    try:
        _previews_mod = getattr(bpy.utils, "previews", None)
    except Exception:
        _previews_mod = None
    return _previews_mod is not None


def register():
    global _pc
    if not _detect_previews():
        _pc = None  # 无 previews:缩略图禁用(纯文本枚举)
        return
    try:
        if _pc is None:
            _pc = _previews_mod.new()
    except Exception:
        _pc = None


def unregister():
    global _pc, _icon_cache
    if _pc is not None and _previews_mod is not None:
        try:
            _previews_mod.remove(_pc)
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
    """返回该预设的 icon_value;previews 不可用/未生成/失败返回 0(不抛异常)。"""
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