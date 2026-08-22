# -*- coding: utf-8 -*-
"""vti/vtu ASCII writer(双向 IO 的写出侧)。净室实现:按 VTK XML 公开格式规范输出。"""
from __future__ import annotations
import xml.etree.ElementTree as ET
import numpy as np


def _fmt_vals(arr):
    """数组 → VTK ascii 文本。审查修复:整数 dtype 按整数输出(避免科学计数法),浮点用 %.8g。"""
    flat = np.asarray(arr).ravel()
    if np.issubdtype(flat.dtype, np.integer):
        parts = [" ".join(str(int(v)) for v in flat[i:i + 10])
                 for i in range(0, len(flat), 10)]
    else:
        parts = [" ".join(f"{float(v):.8g}" for v in flat[i:i + 10])
                 for i in range(0, len(flat), 10)]
    return "\n        ".join(parts)


def write_vti(filepath, fields, dims, rd_meta=None):
    """写出 .vti(ImageData,ASCII)。fields: {chem_name: (nx,ny[,nz]) array}。

    兼容 Ready 读取:含 <RD> 扩展段(rule type/name + parameters)。
    """
    nx, ny = dims
    nz = 1
    dims3 = (nx, ny, nz)
    root = ET.Element("VTKFile", {
        "type": "ImageData", "version": "0.1",
        "byte_order": "LittleEndian",
    })
    if rd_meta:
        rd = ET.SubElement(root, "RD", {"format_version": "2"})
        rule = ET.SubElement(rd, "rule", {
            "name": rd_meta.get("rule_name", "Gray-Scott"),
            "type": rd_meta.get("rule_type", "inbuilt"),
        })
        for name, val in rd_meta.get("parameters", {}).items():
            p = ET.SubElement(rule, "param", {"name": name})
            p.text = str(val)
        if rd_meta.get("formula"):
            f = ET.SubElement(rule, "formula", {
                "number_of_chemicals": str(len(fields))})
            f.text = rd_meta["formula"]
    img = ET.SubElement(root, "ImageData", {
        "WholeExtent": f"0 {nx-1} 0 {ny-1} 0 {nz-1}",
        "Origin": "0 0 0", "Spacing": "1 1 1",
    })
    piece = ET.SubElement(img, "Piece", {"Extent": f"0 {nx-1} 0 {ny-1} 0 {nz-1}"})
    pd = ET.SubElement(piece, "PointData")
    for name, arr in fields.items():
        da = ET.SubElement(pd, "DataArray", {
            "type": "Float32", "Name": name, "format": "ascii"})
        da.text = "\n        " + _fmt_vals(arr) + "\n      "
    ET.SubElement(piece, "CellData")
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(filepath, encoding="utf-8", xml_declaration=True)
    return filepath


def write_vtu(filepath, points, faces, cell_data=None, rd_meta=None):
    """写出 .vtu(UnstructuredGrid,ASCII)。faces: (F,3) 三角面 int 索引。"""
    points = np.asarray(points, dtype=np.float32)
    faces = np.asarray(faces, dtype=np.int32)
    n_points = points.shape[0]
    n_cells = faces.shape[0]
    root = ET.Element("VTKFile", {
        "type": "UnstructuredGrid", "version": "0.1",
        "byte_order": "LittleEndian",
    })
    if rd_meta:
        rd = ET.SubElement(root, "RD", {"format_version": "2"})
        rule = ET.SubElement(rd, "rule", {
            "name": rd_meta.get("rule_name", "Gray-Scott"),
            "type": rd_meta.get("rule_type", "inbuilt"),
        })
        for name, val in rd_meta.get("parameters", {}).items():
            p = ET.SubElement(rule, "param", {"name": name})
            p.text = str(val)
        if rd_meta.get("formula"):
            f = ET.SubElement(rule, "formula", {
                "number_of_chemicals": str(len(cell_data or {}))})
            f.text = rd_meta["formula"]
    ug = ET.SubElement(root, "UnstructuredGrid")
    piece = ET.SubElement(ug, "Piece", {
        "NumberOfPoints": str(n_points), "NumberOfCells": str(n_cells)})
    # Points
    pts = ET.SubElement(piece, "Points")
    da = ET.SubElement(pts, "DataArray", {
        "type": "Float32", "NumberOfComponents": "3", "format": "ascii"})
    da.text = "\n        " + _fmt_vals(points) + "\n      "
    # Cells
    cells = ET.SubElement(piece, "Cells")
    conn = ET.SubElement(cells, "DataArray", {
        "type": "Int32", "Name": "connectivity", "format": "ascii"})
    conn.text = "\n        " + _fmt_vals(faces) + "\n      "
    offs = ET.SubElement(cells, "DataArray", {
        "type": "Int32", "Name": "offsets", "format": "ascii"})
    offs.text = "\n        " + " ".join(str(3 * (i + 1)) for i in range(n_cells)) + "\n      "
    types = ET.SubElement(cells, "DataArray", {
        "type": "UInt8", "Name": "types", "format": "ascii"})
    types.text = "\n        " + " ".join("5" for _ in range(n_cells)) + "\n      "
    # PointData / CellData
    pd = ET.SubElement(piece, "PointData")
    cd = ET.SubElement(piece, "CellData")
    for name, arr in (cell_data or {}).items():
        da = ET.SubElement(cd, "DataArray", {
            "type": "Float32", "Name": name, "format": "ascii"})
        da.text = "\n        " + _fmt_vals(arr) + "\n      "
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(filepath, encoding="utf-8", xml_declaration=True)
    return filepath
