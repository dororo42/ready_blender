# -*- coding: utf-8 -*-
"""Pattern Map 渲染器(净室:Karl Sims 地图的数学自实现,图片/代码不复制)。

生成 (k,F) 参数地图与单个图案缩略图:
  - 每个格子 = 一次微型 Gray-Scott 模拟(本插件 5 点拉普拉斯口径,与主输出一致);
  - 输出灰度 uint8:纯 A 区≈0(白),纯 B 区≈1(黑),活跃区呈现中间纹理;
  - 结果缓存为 npy(文件名含参数指纹),二次加载即时;
  - 地图坐标约定:x 轴(列) = k ∈ k_range,y 轴(行) = F(第 0 行 = F 上限,
    与 Blender 图像 buffer 底 → 顶行序配合时写入前需翻转)。
"""
from __future__ import annotations
import os
import struct
import zlib
import numpy as np

try:
    from .fast_ops import gray_scott_step_opt
except ImportError:  # 顶层模式(直接运行/测试)
    from core.fast_ops import gray_scott_step_opt

# 默认内核口径(与 §2.3 数值契约一致):Du/Dv 为缩放后典型值,F/k 跨内核通用
DEFAULT_DU = 0.16
DEFAULT_DV = 0.08
DEFAULT_DT = 1.0
# 地图范围(与 Karl Sims 教程一致)
DEFAULT_K_RANGE = (0.045, 0.07)
DEFAULT_F_RANGE = (0.01, 0.1)

_cache_dir = None      # 可被测试 monkeypatch;None → 仅内存缓存
_mem_cache = {}


def set_cache_dir(path):
    """设置 npy 缓存目录(默认 None=仅内存缓存;插件端可指到 presets/)。"""
    global _cache_dir
    _cache_dir = path


def kf_from_uv(u, v, k_range=DEFAULT_K_RANGE, f_range=DEFAULT_F_RANGE):
    """地图 UV(0..1) → (k, F)。v 轴翻转:图像顶部(y 大)= F 上限。"""
    k = k_range[0] + u * (k_range[1] - k_range[0])
    f = f_range[1] - v * (f_range[1] - f_range[0])
    return k, f


def uv_from_kf(k, f, k_range=DEFAULT_K_RANGE, f_range=DEFAULT_F_RANGE):
    """(k, F) → 地图 UV(供拾取光标定位/往返断言)。"""
    u = (k - k_range[0]) / (k_range[1] - k_range[0])
    v = (f_range[1] - f) / (f_range[1] - f_range[0])
    return u, v


def _mini_sim(cell, F, k, steps, seed, Du, Dv, dt, wrap=True):
    """单格微型 GS 模拟:中心 4×4 种子 b=1,a 基底 1.0。返回 b 均值 [0,1]。"""
    rng = np.random.default_rng(seed)
    a = np.ones((cell, cell), dtype=np.float32)
    b = np.zeros((cell, cell), dtype=np.float32)
    c = cell // 2
    b[c - 2:c + 2, c - 2:c + 2] = 1.0
    # 微扰打破对称(确定性种子)
    a += (rng.random((cell, cell), dtype=np.float32) - 0.5) * 1e-2
    lap_a = np.empty_like(a)
    lap_b = np.empty_like(b)
    abb = np.empty_like(a)
    for _ in range(steps):
        gray_scott_step_opt(a, b, Du, Dv, F, k, dt, wrap=wrap,
                            lap_a=lap_a, lap_b=lap_b, abb=abb)
    return float(b.mean())


def render_pattern_map(cols=24, rows=18, cell=24, steps=400, seed=42,
                       k_range=DEFAULT_K_RANGE, f_range=DEFAULT_F_RANGE,
                       Du=DEFAULT_DU, Dv=DEFAULT_DV, dt=DEFAULT_DT,
                       use_cache=True):
    """渲染 (k,F) 参数地图,返回 (rows, cols) uint8 灰度(0=白,255=黑)。

    每格 = 该 (k,F) 处微型模拟的 b 均值 ×255。确定性强(seed 派生),缓存可复用。
    """
    key = ("map", cols, rows, cell, steps, seed, k_range, f_range, Du, Dv, dt)
    if use_cache:
        hit = _cache_get(key, (rows, cols), np.uint8)
        if hit is not None:
            return hit
    out = np.zeros((rows, cols), dtype=np.uint8)
    for r in range(rows):
        for c in range(cols):
            k, f = kf_from_uv(c / max(cols - 1, 1), r / max(rows - 1, 1),
                              k_range, f_range)
            out[r, c] = int(round(_mini_sim(cell, f, k, steps,
                                            seed + r * cols + c,
                                            Du, Dv, dt) * 255.0))
    if use_cache:
        _cache_put(key, out)
    return out


def render_pattern_thumbnail(F, k, size=64, thumb=24, steps=300, seed=42,
                             Du=DEFAULT_DU, Dv=DEFAULT_DV, dt=DEFAULT_DT,
                             use_cache=True):
    """单个 (F,k) 的图案缩略图:size×size 模拟 → 缩到 thumb×thumb uint8。"""
    key = ("thumb", size, F, k, steps, seed, Du, Dv, dt)
    if use_cache:
        hit = _cache_get(key, (thumb, thumb), np.uint8)
        if hit is not None:
            return hit
    rng = np.random.default_rng(seed)
    a = np.ones((size, size), dtype=np.float32)
    b = np.zeros((size, size), dtype=np.float32)
    c = size // 2
    b[c - 2:c + 2, c - 2:c + 2] = 1.0
    a += (rng.random((size, size), dtype=np.float32) - 0.5) * 1e-2
    lap_a = np.empty_like(a)
    lap_b = np.empty_like(b)
    abb = np.empty_like(a)
    for _ in range(steps):
        gray_scott_step_opt(a, b, Du, Dv, F, k, dt, wrap=True,
                            lap_a=lap_a, lap_b=lap_b, abb=abb)
    # 块平均降采样
    s = size // thumb
    small = b[:thumb * s, :thumb * s].reshape(thumb, s, thumb, s).mean(axis=(1, 3))
    out = (small * 255.0).round().astype(np.uint8)
    if use_cache:
        _cache_put(key, out)
    return out


# ── 缓存 ─────────────────────────────────────────────────────────────
def map_image_pixels(arr: np.ndarray) -> list:
    """地图数组 → Blender image pixels(行序翻转:数组第 0 行=顶部→buffer 底→顶)。

    arr 为 (rows, cols) uint8 灰度;返回长度 = rows*cols*4 的 float 列表
    (R=G=B=灰度/255, A=1)。"""
    h, w = arr.shape
    flipped = arr[::-1]  # 底→顶
    out = np.empty((h, w, 4), dtype=np.float32)
    g = flipped.astype(np.float32) / 255.0
    out[..., 0] = g
    out[..., 1] = g
    out[..., 2] = g
    out[..., 3] = 1.0
    return out.ravel().tolist()


def _cache_path(key):
    if not _cache_dir:
        return None
    sig = "_".join(str(x).replace(".", "p").replace("(", "").replace(")", "")
                   for x in key)
    return os.path.join(_cache_dir, f"pattern_cache_{sig}.npy")


def _cache_get(key, shape, dtype):
    hit = _mem_cache.get(key)
    if hit is not None:
        return hit
    p = _cache_path(key)
    if p and os.path.exists(p):
        try:
            arr = np.load(p, allow_pickle=False)
            if arr.shape == shape and arr.dtype == dtype:
                _mem_cache[key] = arr
                return arr
        except Exception:
            pass
    return None


def _cache_put(key, arr):
    if len(_mem_cache) > 64:  # 防止缩略图枚举撑爆内存
        _mem_cache.clear()
    _mem_cache[key] = arr
    p = _cache_path(key)
    if p:
        try:
            np.save(p, arr)
        except Exception:
            pass


# ── 最小 PNG 编码(gray 8-bit,无 PIL 依赖;供预览枚举/网页缩略图)────────
def png_encode_gray(arr: np.ndarray) -> bytes:
    """uint8 2D → 8-bit 灰度 PNG 字节流(自包含,minimal zlib+struct)。"""
    arr = np.asarray(arr, dtype=np.uint8)
    h, w = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))