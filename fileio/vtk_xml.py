# -*- coding: utf-8 -*-
"""vti/vtu IO:VTK XML 格式解析器 + Ready <RD> 扩展段。净室实现。

实测格式(Ready 全部 93 个 pattern 文件):
- binary 内联:DataArray 文本 = base64(头部 uint32 序列) + '=' + base64(zlib 压缩流)
- appended:AppendedData 文本 = '_' + 各块连续拼接,每块同 binary 结构;
  DataArray 的 offset 属性 = 该块头在去空白后文本中的字符位置
- 头部 uint32 序列:[nblocks][block_size][last_block_size][nblocks 个压缩块尺寸]
  nblocks=0 表示未压缩,数据直接跟随。
"""
from __future__ import annotations
import base64, struct, zlib, os
import xml.etree.ElementTree as ET
import numpy as np


class VTKError(ValueError):
    pass


# 资源上限:.vti 是外部不可信输入(网络下载/他人分享),须防解压炸弹与超大文件
_MAX_FILE_BYTES = 512 * 1024 * 1024        # 单文件上限 512MB
_MAX_DECOMPRESSED_BYTES = 256 * 1024 * 1024  # 单文件解压输出累计上限 256MB
_ZLIB_CHUNK = 4 * 1024 * 1024              # 分块解压步长 4MB


def decode_inline(text: str, byte_order: str) -> bytes:
    """解码 binary 内联数据。

    格式:base64(头部 uint32 序列,含 padding) + base64(zlib 流,含 padding)。
    头部 uint32 序列:[nblocks][block_size][last_block_size][nblocks 个压缩尺寸]。
    """
    endian = "<" if byte_order == "LittleEndian" else ">"
    t = text.strip()
    if not t:
        return b""
    nblocks, hdr_b64_len = _read_nblocks(t, endian)
    if nblocks > 1_000_000 or hdr_b64_len > len(t):
        raise VTKError(f"binary 头部非法(nblocks={nblocks})")
    hdr_b64 = t[:hdr_b64_len]
    pad = (-len(hdr_b64)) % 4
    hdr = base64.b64decode(hdr_b64 + "=" * pad)
    n_u32 = len(hdr) // 4
    vals = struct.unpack(endian + f"{n_u32}I", hdr)
    if nblocks == 0:
        dat = t[hdr_b64_len:]
        pad2 = (-len(dat)) % 4
        return base64.b64decode(dat + "=" * pad2)
    sizes = vals[3:3 + nblocks]
    total = sum(sizes)
    b64_len = ((total + 2) // 3) * 4
    dat_b64 = t[hdr_b64_len:hdr_b64_len + b64_len]
    return _decode_streams(dat_b64, sizes, endian)


def _read_nblocks(t: str, endian: str):
    """从文本头部读 nblocks,返回 (nblocks, header_b64_len)。"""
    probe = t[:8]
    pad = (-len(probe)) % 4
    raw = base64.b64decode(probe + "=" * pad)
    nblocks = struct.unpack_from(endian + "I", raw, 0)[0]
    if nblocks == 0:
        hdr_bytes = 4
    else:
        hdr_bytes = (3 + nblocks) * 4
    hdr_b64_len = ((hdr_bytes + 2) // 3) * 4
    return nblocks, hdr_b64_len


def _decode_streams(dat_b64: str, sizes, endian: str,
                    max_out=_MAX_DECOMPRESSED_BYTES) -> bytes:
    """解压 n 个 zlib 流(每个流 sizes[i] 字节压缩数据)。

    分块解压并限制累计输出(防解压炸弹:几百 KB 恶意文件可声称解出数 GB,
    一次性 zlib.decompress 会直接 OOM Blender 主进程)。
    """
    pad = (-len(dat_b64)) % 4
    raw = base64.b64decode(dat_b64 + "=" * pad)
    outs = []
    pos = 0
    total = 0
    for sz in sizes:
        if sz < 0 or pos + sz > len(raw):
            raise VTKError("压缩块尺寸超出数据长度(文件损坏或恶意构造)")
        d = zlib.decompressobj()
        parts = []
        got = 0
        out = d.decompress(raw[pos:pos + sz], _ZLIB_CHUNK)
        while out:
            got += len(out)
            total += len(out)
            if total > max_out:
                raise VTKError(
                    f"解压输出超过资源上限({max_out // (1024 * 1024)}MB,疑似解压炸弹)")
            parts.append(out)
            out = d.decompress(b"", _ZLIB_CHUNK)
        if not d.eof:
            raise VTKError("压缩流不完整(文件损坏)")
        outs.append(b"".join(parts))
        pos += sz
    return b"".join(outs)


def decode_appended(text: str, byte_order: str) -> dict:
    """解码 AppendedData 整段,返回 {文本位置: 解压后字节}。

    实测格式(Ready 文件):块连续拼接,每块 = base64(头,含 padding) + base64(流);
    DataArray 的 offset 属性 = 块头在去空白后文本中的字符位置。
    """
    body = "".join(text.split())
    if body.startswith("_"):
        body = body[1:]
    endian = "<" if byte_order == "LittleEndian" else ">"
    blocks = {}
    pos = 0
    while pos < len(body):
        try:
            nblocks, hdr_b64_len = _read_nblocks(body[pos:], endian)
        except Exception:
            break
        hdr_b64 = body[pos:pos + hdr_b64_len]
        pad = (-len(hdr_b64)) % 4
        hdr = base64.b64decode(hdr_b64 + "=" * pad)
        n_u32 = len(hdr) // 4
        vals = struct.unpack(endian + f"{n_u32}I", hdr)
        if nblocks == 0:
            dat = body[pos + hdr_b64_len:]
            pad2 = (-len(dat)) % 4
            blocks[pos] = base64.b64decode(dat + "=" * pad2)
            break
        sizes = vals[3:3 + nblocks]
        total = sum(sizes)
        b64_len = ((total + 2) // 3) * 4
        dat_b64 = body[pos + hdr_b64_len:pos + hdr_b64_len + b64_len]
        blocks[pos] = _decode_streams(dat_b64, sizes, endian)
        pos += hdr_b64_len + b64_len
    return blocks


_DTYPE_TABLE = {
    "Float32": np.float32, "Float64": np.float64,
    "Int32": np.int32, "Int64": np.int64, "UInt8": np.uint8,
    "UInt16": np.uint16, "Int16": np.int16, "UInt32": np.uint32,
}


def _parse_data_array(da, byte_order, appended_blocks=None, expected_size=None):
    """解析单个 DataArray,返回 numpy 数组(本机字节序)。

    expected_size:可选,期望元素总数(= 域点数 × NumberOfComponents);
    数据非空且长度不符时抛 VTKError(截断/超长文件早失败,报错靠近根因)。
    """
    dtype = da.attrib.get("type", "Float32")
    if dtype not in _DTYPE_TABLE:
        raise VTKError(f"不支持的 DataArray type: {dtype}")
    ncomp = int(da.attrib.get("NumberOfComponents", "1"))
    fmt = da.attrib.get("format", "binary")
    native_dtype = np.dtype(_DTYPE_TABLE[dtype])
    # byte_order 只在头部解析用过;数据数组此前按本机序解码,BigEndian 文件被静默错读
    file_dtype = (native_dtype.newbyteorder("<") if byte_order == "LittleEndian"
                  else native_dtype.newbyteorder(">"))
    if fmt == "binary":
        raw = (da.text or "").strip()
        if not raw:
            arr = np.array([], dtype=native_dtype)
        else:
            arr = np.frombuffer(decode_inline(raw, byte_order),
                                dtype=file_dtype).astype(native_dtype, copy=False)
    elif fmt == "appended":
        offset = int(da.attrib["offset"])
        if appended_blocks is None or offset not in appended_blocks:
            arr = np.array([], dtype=native_dtype)
        else:
            arr = np.frombuffer(appended_blocks[offset],
                                dtype=file_dtype).astype(native_dtype, copy=False)
    elif fmt == "ascii":
        text = (da.text or "").strip()
        if not text:
            arr = np.array([], dtype=native_dtype)
        else:
            arr = np.array([float(x) for x in text.split()], dtype=native_dtype)
    else:
        raise VTKError(f"unknown format: {fmt}")
    if ncomp > 1:
        if arr.size % ncomp:
            raise VTKError(
                f"数组长度 {arr.size} 不是 NumberOfComponents={ncomp} 的整数倍")
        arr = arr.reshape(-1, ncomp)
    if expected_size is not None and 0 < arr.size != expected_size:
        raise VTKError(
            f"数据长度 {arr.size} 与域尺寸期望值 {expected_size} 不符(截断/损坏?)")
    return arr


def read_vti(filepath):
    """读取 .vti(ImageData)。"""
    return _vti_from_root(ET.parse(filepath).getroot())


def _vti_from_root(root):
    if root.attrib.get("type") != "ImageData":
        raise VTKError(f"expected ImageData, got {root.attrib.get('type')}")
    byte_order = root.attrib.get("byte_order", "LittleEndian")

    appended_blocks = None
    appended = root.find("AppendedData")
    if appended is not None and appended.text:
        appended_blocks = decode_appended(appended.text, byte_order)

    img = root.find("ImageData")
    if img is None:
        raise VTKError("缺少 <ImageData> 节点")
    ext_raw = img.attrib.get("WholeExtent", "").split()
    if len(ext_raw) != 6:
        raise VTKError(f"WholeExtent 需 6 个整数,得到 {len(ext_raw)} 个")
    try:
        ext = [int(x) for x in ext_raw]
    except ValueError as e:
        raise VTKError(f"WholeExtent 含非整数: {e}")
    dims = (ext[1] - ext[0] + 1, ext[3] - ext[2] + 1, ext[5] - ext[4] + 1)
    if min(dims) < 1:
        raise VTKError(f"维度非法(负/零): {dims}")
    origin = [float(x) for x in img.attrib.get("Origin", "0 0 0").split()]
    spacing = [float(x) for x in img.attrib.get("Spacing", "1 1 1").split()]

    n_points = dims[0] * dims[1] * dims[2]
    point_data, cell_data = {}, {}
    piece = img.find("Piece")
    if piece is not None:
        pd = piece.find("PointData")
        if pd is not None:
            for da in pd.findall("DataArray"):
                name = da.attrib.get("Name", "?")
                try:
                    point_data[name] = _parse_data_array(
                        da, byte_order, appended_blocks, expected_size=n_points)
                except VTKError:
                    raise
                except Exception as e:
                    raise VTKError(f"point data '{name}': {e}")
        cd = piece.find("CellData")
        if cd is not None:
            for da in cd.findall("DataArray"):
                name = da.attrib.get("Name", "?")
                try:
                    cell_data[name] = _parse_data_array(da, byte_order, appended_blocks)
                except VTKError:
                    raise
                except Exception as e:
                    raise VTKError(f"cell data '{name}': {e}")

    rd = _parse_rd(root.find("RD"))
    return {"type": "ImageData", "dimensions": dims, "origin": origin, "spacing": spacing,
            "point_data": point_data, "cell_data": cell_data, "rd": rd}


def read_vtu(filepath):
    """读取 .vtu(UnstructuredGrid)。"""
    tree = ET.parse(filepath)
    root = tree.getroot()
    if root.attrib.get("type") != "UnstructuredGrid":
        raise VTKError(f"expected UnstructuredGrid, got {root.attrib.get('type')}")
    byte_order = root.attrib.get("byte_order", "LittleEndian")

    appended_blocks = None
    appended = root.find("AppendedData")
    if appended is not None and appended.text:
        appended_blocks = decode_appended(appended.text, byte_order)

    ug = root.find("UnstructuredGrid")
    piece = ug.find("Piece")
    n_points = int(piece.attrib.get("NumberOfPoints", "0"))
    n_cells = int(piece.attrib.get("NumberOfCells", "0"))

    points, cell_types, cell_conn, cell_off = None, None, None, None
    point_data, cell_data = {}, {}

    pd = piece.find("PointData")
    if pd is not None:
        for da in pd.findall("DataArray"):
            try:
                point_data[da.attrib["Name"]] = _parse_data_array(da, byte_order, appended_blocks)
            except Exception as e:
                raise VTKError(f"point data '{da.attrib.get('Name','?')}': {e}")
    cd = piece.find("CellData")
    if cd is not None:
        for da in cd.findall("DataArray"):
            try:
                cell_data[da.attrib["Name"]] = _parse_data_array(da, byte_order, appended_blocks)
            except Exception as e:
                raise VTKError(f"cell data '{da.attrib.get('Name','?')}': {e}")
    pts = piece.find("Points")
    if pts is not None:
        for da in pts.findall("DataArray"):
            try:
                points = _parse_data_array(da, byte_order, appended_blocks)
            except Exception as e:
                raise VTKError(f"points: {e}")
    cells = piece.find("Cells")
    if cells is not None:
        for da in cells.findall("DataArray"):
            name = da.attrib.get("Name", "")
            try:
                arr = _parse_data_array(da, byte_order, appended_blocks)
            except Exception as e:
                raise VTKError(f"cells '{name}': {e}")
            if name == "connectivity":
                cell_conn = arr
            elif name == "offsets":
                cell_off = arr
            elif name == "types":
                cell_types = arr

    rd = _parse_rd(root.find("RD"))
    return {"type": "UnstructuredGrid", "n_points": n_points, "n_cells": n_cells,
            "points": points, "cell_types": cell_types,
            "cell_connectivity": cell_conn, "cell_offsets": cell_off,
            "point_data": point_data, "cell_data": cell_data, "rd": rd}


def _parse_rd(rd_el):
    rd = {}
    if rd_el is None:
        return rd
    rd["format_version"] = rd_el.attrib.get("format_version", "1")
    desc = rd_el.find("description")
    if desc is not None and desc.text:
        rd["description"] = desc.text
    rule = rd_el.find("rule")
    if rule is not None:
        rd["rule_type"] = rule.attrib.get("type", "")
        rd["rule_name"] = rule.attrib.get("name", "")
        rd["parameters"] = {}
        for p in rule.findall("param"):
            try:
                rd["parameters"][p.attrib["name"]] = float(p.text)
            except (TypeError, ValueError):
                pass
        formula = rule.find("formula")
        if formula is not None and formula.text:
            rd["formula"] = formula.text.strip()
            rd["n_chemicals"] = int(formula.attrib.get("number_of_chemicals", "2"))
        kernel = rule.find("kernel")
        if kernel is not None and kernel.text:
            rd["kernel"] = kernel.text.strip()
    ipg = rd_el.find("initial_pattern_generator")
    if ipg is not None:
        rd["apply_when_loading"] = ipg.attrib.get("apply_when_loading", "false") == "true"
    return rd


def read_file(filepath):
    """自动分发 .vti/.vtu(单次解析;入口限制文件大小防超大输入)。"""
    try:
        if os.path.getsize(filepath) > _MAX_FILE_BYTES:
            raise VTKError(
                f"文件超过 {_MAX_FILE_BYTES // (1024 * 1024)}MB 上限,拒绝解析")
    except OSError as e:
        raise VTKError(f"无法读取文件: {e}")
    root = ET.parse(filepath).getroot()
    vt = root.attrib.get("type")
    if vt == "ImageData":
        return _vti_from_root(root)
    if vt == "UnstructuredGrid":
        return read_vtu(filepath)
    raise VTKError(f"unsupported VTK type: {vt}")
