# -*- coding: utf-8 -*-
"""image_adapter:场 ↔ Image.pixels。净室实现。"""
from __future__ import annotations
import numpy as np


def field_to_image(field_2d, image_name="RD_preview", colormap="viridis", vmin=None, vmax=None):
    """2D 场 → Blender Image(RGBA float)。"""
    import bpy
    data = field_2d
    if vmin is None:
        vmin = float(data.min())
    if vmax is None:
        vmax = float(data.max())
    rng = max(vmax - vmin, 1e-9)
    norm = np.clip((data - vmin) / rng, 0, 1)
    h, w = norm.shape
    if colormap == "viridis":
        t = norm
        r = 0.267 * (1 - t) + 0.993 * t
        g = 0.005 * (1 - t) + 0.906 * t
        b = 0.329 * (1 - t) + 0.143 * t
    elif colormap == "magma":
        t = norm
        r = np.clip(1.5 * t, 0, 1)
        g = np.clip(t * t * 1.2, 0, 1)
        b = np.clip(0.3 + 0.7 * t, 0, 1)
    else:  # grayscale
        r = g = b = norm
    rgba = np.zeros((h, w, 4), dtype=np.float32)
    rgba[..., 0] = r
    rgba[..., 1] = g
    rgba[..., 2] = b
    rgba[..., 3] = 1.0
    # 写入 Image
    img = None
    if image_name in bpy.data.images:
        img = bpy.data.images[image_name]
        if img.size[0] != w or img.size[1] != h:
            img.scale(w, h)
    else:
        img = bpy.data.images.new(image_name, width=w, height=h, float_buffer=True)
    img.pixels[:] = rgba.ravel()
    img.update_tag()
    return img


def image_to_field(img):
    """Blender Image → numpy 2D 场(取 R 通道)。"""
    import bpy
    w, h = img.size
    pixels = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    return pixels[..., 0].copy()
