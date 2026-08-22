# -*- coding: utf-8 -*-
"""纯 Python PNG 编码器(无外部依赖),生成 Pearson 1993 灰度验证图。"""
import struct, zlib, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.rule import GrayScottRule
from core.field import RegularGridField

def write_png(path, data2d, cmap="gray", vmin=None, vmax=None):
    """data2d: (H,W) float → 8-bit PNG。支持 gray / magma-ish / viridis-ish 伪彩。"""
    h, w = data2d.shape
    if vmin is None: vmin = float(data2d.min())
    if vmax is None: vmax = float(data2d.max())
    rng = max(vmax - vmin, 1e-9)
    norm = np.clip((data2d - vmin) / rng, 0, 1)
    if cmap == "gray":
        raw = (norm * 255).astype(np.uint8)
        raw = np.stack([raw, raw, raw], axis=-1)  # RGB
    elif cmap == "magma":
        t = norm
        r = np.clip(1.5 * t, 0, 1)
        g = np.clip(t**2 * 1.2, 0, 1)
        b = np.clip(0.3 + 0.7 * t, 0, 1)
        raw = (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)
    elif cmap == "viridis":
        t = norm
        r = np.clip(0.267 * (1-t) + 0.993 * t, 0, 1)
        g = np.clip(0.005 * (1-t) + 0.906 * t, 0, 1)
        b = np.clip(0.329 * (1-t) + 0.143 * t, 0, 1)
        raw = (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)
    else:
        raw = (norm * 255).astype(np.uint8)
        raw = np.stack([raw, raw, raw], axis=-1)
    # PNG encode
    def chunk(ctype, data):
        c = ctype + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xffffffff)
        return struct.pack(">I", len(data)) + c + crc
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8-bit RGB
    raw_bytes = raw.tobytes()
    # add filter byte (0=None) per row
    stride = w * 3
    filtered = b""
    for y in range(h):
        filtered += b"\x00" + raw_bytes[y*stride:(y+1)*stride]
    idat = zlib.compress(filtered, 9)
    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return path

def run_pearson():
    a = RegularGridField((256, 256), wrap=True)
    b = RegularGridField((256, 256), wrap=True)
    rng = np.random.default_rng(42)
    a.data[:] = 1.0
    b.data[:] = 0.0
    cx, cy = 128, 128
    s = 32
    b.data[cy-s:cy+s, cx-s:cx+s] = rng.uniform(0, 1, (2*s, 2*s)).astype(np.float32)
    params = {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0, "wrap": True}
    rule = GrayScottRule()
    for _ in range(5000):
        rule.update([a.data, b.data], params, 1.0, "grid")
    out_dir = os.path.join(os.path.dirname(__file__), "..", "DELIVERY")
    out_dir = os.path.normpath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    p_a = write_png(os.path.join(out_dir, "m0_pearson_a.png"), a.data, "viridis", 0, 1)
    p_b = write_png(os.path.join(out_dir, "m0_pearson_b.png"), b.data, "magma", 0, 0.5)
    print(f"Pearson a saved: {p_a}")
    print(f"Pearson b saved: {p_b}")
    # stats for verification
    print(f"a: min={a.data.min():.4f} max={a.data.max():.4f} std={a.data.std():.4f}")
    print(f"b: min={b.data.min():.4f} max={b.data.max():.4f} std={b.data.std():.4f}")
    return p_a, p_b

if __name__ == "__main__":
    run_pearson()
