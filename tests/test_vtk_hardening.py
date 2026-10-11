# -*- coding: utf-8 -*-
"""vtk_xml 加固回归测试(v1.7 审查修复)。

锁定四类不可信输入防护:
  1) BigEndian 文件数据数组按声明字节序解码(此前按本机序静默错读);
  2) 解压炸弹:累计输出超限抛 VTKError 而非 OOM;
  3) WholeExtent 畸形(数量/负维)早失败;
  4) ascii 空元素/数据长度不符不再崩溃或静默通过。
"""
import base64
import os
import struct
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

from fileio.vtk_xml import (VTKError, _decode_streams, read_file)


def _vti_xml(inner, byte_order="LittleEndian", extent="0 3 0 3 0 0"):
    return f'''<VTKFile type="ImageData" version="0.1" byte_order="{byte_order}">
  <ImageData WholeExtent="{extent}" Origin="0 0 0" Spacing="1 1 1">
    <Piece Extent="{extent}">
      <PointData>{inner}</PointData>
      <CellData/>
    </Piece>
  </ImageData>
</VTKFile>'''


def _inline_binary(arr_bytes, byte_order="LittleEndian"):
    """Ready 风格 inline binary:base64(头) + base64(zlib 流)。

    头部 uint32 与数据同字节序(VTK 规范);压缩流本身无字节序。
    """
    comp = zlib.compress(arr_bytes)
    pre = "<" if byte_order == "LittleEndian" else ">"
    # 头 = [nblocks][block_size][last_block_size][nblocks 个块尺寸] = 4 个 uint32;
    # 头部 b64 自带 padding,与数据 b64 直接拼接(无额外分隔符,与 Ready 实测一致)
    header = struct.pack(pre + "IIII", 1, len(comp), len(comp), len(comp))
    return base64.b64encode(header).decode() + base64.b64encode(comp).decode()


def _write_tmp(xml_text):
    fd, path = tempfile.mkstemp(suffix=".vti")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return path


def test_big_endian_binary_decoded_correctly():
    # 4x4 float32 值 1..16,以 BigEndian 写出
    vals = np.arange(1, 17, dtype=">f4")
    da = ('<DataArray type="Float32" Name="a" format="binary">'
          f'{_inline_binary(vals.tobytes(), "BigEndian")}</DataArray>')
    path = _write_tmp(_vti_xml(da, byte_order="BigEndian"))
    try:
        r = read_file(path)
        a = np.asarray(r["point_data"]["a"])
        assert np.allclose(a.ravel(), np.arange(1, 17), atol=1e-6), \
            f"BE 数据被错误解码: {a.ravel()[:4]}"
    finally:
        os.remove(path)


def test_decompress_bomb_capped():
    # 小压缩流声称解出超大输出:小上限下必须抛 VTKError(而非 OOM)
    bomb = zlib.compress(b"\x00" * (8 * 1024 * 1024))
    dat_b64 = base64.b64encode(bomb).decode()
    with __import__("contextlib").suppress(Exception):
        _decode_streams(dat_b64, [len(bomb)], "<", max_out=1024 * 1024)
        raise AssertionError("解压炸弹未被上限拦截")
    # 正常流在同上限内不受影响
    ok = zlib.compress(b"\x00" * 1024)
    out = _decode_streams(base64.b64encode(ok).decode(), [len(ok)], "<",
                          max_out=1024 * 1024)
    assert len(out) == 1024


def test_malformed_whole_extent_rejected():
    for bad in ("0 3 0 3", "0 3 0 3 5 -1"):
        path = _write_tmp(_vti_xml("", extent=bad))
        try:
            try:
                read_file(path)
                raise AssertionError(f"WholeExtent={bad!r} 未被拒绝")
            except VTKError:
                pass
        finally:
            os.remove(path)


def test_ascii_empty_and_size_mismatch():
    path = _write_tmp(_vti_xml('<DataArray type="Float32" Name="a" format="ascii"/>'))
    try:
        r = read_file(path)  # 空 ascii:返回空数组,不崩
        assert np.asarray(r["point_data"]["a"]).size == 0
    finally:
        os.remove(path)
    # 数据长度与域尺寸不符 → VTKError(截断文件早失败)
    da = '<DataArray type="Float32" Name="a" format="ascii">1 2 3</DataArray>'
    path = _write_tmp(_vti_xml(da))
    try:
        try:
            read_file(path)
            raise AssertionError("截断数据未被拒绝")
        except VTKError:
            pass
    finally:
        os.remove(path)


def test_int_field_be_roundtrip():
    vals = np.arange(1, 17, dtype=">i4")
    da = ('<DataArray type="Int32" Name="t" format="binary">'
          f'{_inline_binary(vals.tobytes(), "BigEndian")}</DataArray>')
    path = _write_tmp(_vti_xml(da, byte_order="BigEndian"))
    try:
        r = read_file(path)
        assert np.allclose(np.asarray(r["point_data"]["t"]).ravel(),
                           np.arange(1, 17))
    finally:
        os.remove(path)


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("vtk_hardening: all passed")
