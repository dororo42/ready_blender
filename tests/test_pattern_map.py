# -*- coding: utf-8 -*-
"""1a Pattern Map 渲染器测试:形状/值域、已知参数点差异、确定性、缓存、PNG。"""
import os
import sys
import struct
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from presets import pattern_map as pm


def _close():
    pm._mem_cache.clear()


def test_shape_and_range():
    arr = pm.render_pattern_map(cols=8, rows=6, cell=12, steps=200, use_cache=False)
    assert arr.shape == (6, 8)
    assert arr.dtype == np_uint8()
    assert arr.min() >= 0 and arr.max() <= 255


def np_uint8():
    import numpy as np
    return np.uint8


def test_known_points_differ():
    # mitosis (f=0.0367,k=0.0649) 与 chaos 区灰度应显著不同(活跃区 vs 恒定区)
    m = pm.render_pattern_thumbnail(0.0367, 0.0649, size=48, thumb=12,
                                    steps=300, use_cache=False)
    c = pm.render_pattern_thumbnail(0.026, 0.051, size=48, thumb=12,
                                    steps=300, use_cache=False)
    mu = int(m.mean())
    cu = int(c.mean())
    assert abs(mu - cu) > 10, f"mitosis={mu} chaos={cu} 差异过小"


def test_determinism():
    a = pm.render_pattern_map(cols=6, rows=4, cell=12, steps=150, use_cache=False)
    b = pm.render_pattern_map(cols=6, rows=4, cell=12, steps=150, use_cache=False)
    import numpy as np
    assert np.array_equal(a, b)


def test_cache_roundtrip(tmpdir=None):
    import numpy as np
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pm_cache_test")
    os.makedirs(d, exist_ok=True)
    pm.set_cache_dir(d)
    try:
        a = pm.render_pattern_map(cols=5, rows=4, cell=10, steps=100)
        b = pm.render_pattern_map(cols=5, rows=4, cell=10, steps=100)
        assert np.array_equal(a, b)
        assert os.listdir(d), "npy 缓存文件应已写入"
    finally:
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
        os.rmdir(d)
        pm.set_cache_dir(None)


def test_uv_roundtrip():
    for k, f in [(0.0367, 0.0649), (0.0545, 0.062), (0.055, 0.035), (0.045, 0.1)]:
        u, v = pm.uv_from_kf(k, f)
        k2, f2 = pm.kf_from_uv(u, v)
        assert abs(k2 - k) < 1e-9 and abs(f2 - f) < 1e-9


def test_map_pixels_flip():
    import numpy as np
    arr = np.array([[1, 2], [3, 4]], dtype=np.uint8)  # 行 0 = 顶部(F 上限)
    px = pm.map_image_pixels(arr)
    assert len(px) == 2 * 2 * 4
    # buffer 前 4 元素 = 底部行 = arr 底部行 [3,4]
    lo = [round(px[i], 6) for i in range(4)]
    assert all(abs(lo[i] - 3 / 255.0) < 1e-5 for i in range(3)) and lo[3] == 1.0
    top = [round(px[8 + i], 6) for i in range(4)]  # buffer 行 1(顶部)第一个像素
    assert all(abs(top[i] - 1 / 255.0) < 1e-5 for i in range(3)) and top[3] == 1.0


def test_png_encode():
    import numpy as np
    arr = np.arange(64, dtype=np.uint8).reshape(8, 8)
    png = pm.png_encode_gray(arr)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    # 解出 IDAT 校验尺寸与内容
    pos = 8
    w = h = ch = None
    idat = b""
    while pos < len(png):
        length = struct.unpack(">I", png[pos:pos + 4])[0]
        typ = png[pos + 4:pos + 8]
        data = png[pos + 8:pos + 8 + length]
        if typ == b"IHDR":
            w, h, ch = struct.unpack(">IIB", data[:9])
        elif typ == b"IDAT":
            idat += data
        pos += 12 + length
    assert (w, h, ch) == (8, 8, 8)
    raw = zlib.decompress(idat)
    import numpy as np
    assert len(raw) == h * (w + 1), "每行 1 filter + w 字节"
    filters = [raw[y * (w + 1)] for y in range(h)]
    assert all(f == 0 for f in filters), "全部 None filter"
    pixels = [raw[y * (w + 1) + 1:(y + 1) * (w + 1)] for y in range(h)]
    assert np.array_equal(np.frombuffer(b"".join(pixels), dtype=np.uint8).reshape(8, 8), arr)


if __name__ == "__main__":
    _close()
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                print(f"FAIL {name}: {e}")
                raise
    print("pattern_map: all passed")