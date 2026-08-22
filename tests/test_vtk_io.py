# -*- coding: utf-8 -*-
"""vti/vtu IO 验收:93 个真实 pattern 文件全部解析。"""
import sys, os, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fileio.vtk_xml import read_file, VTKError

import os as _os
root_dir = _os.environ.get(
    "READY_PATTERNS_DIR",
    r"C:\Users\Administrator\.openclaw-autoclaw\workspace\.cluster\ready-blender-analysis\repo_src\ready-Ready-0.6\Patterns")
if not _os.path.isdir(root_dir):
    print(f"[FAIL] patterns 目录不存在: {root_dir}(可用环境变量 READY_PATTERNS_DIR 指定)")
    sys.exit(1)
files = sorted(glob.glob(os.path.join(root_dir, "**", "*.vti"), recursive=True) +
               glob.glob(os.path.join(root_dir, "**", "*.vtu"), recursive=True))
if not files:
    print("[FAIL] patterns 目录下未找到任何 .vti/.vtu 文件")
    sys.exit(1)

ok = fail = 0
stats = {"ImageData": 0, "UnstructuredGrid": 0}
rule_types = {}
failures = []

for p in files:
    try:
        r = read_file(p)
        stats[r["type"]] += 1
        # 校验:数据一致性
        if r["type"] == "ImageData":
            nx, ny, nz = r["dimensions"]
            expected = nx * ny * nz
            for name, arr in r["point_data"].items():
                if len(arr.shape) > 1:
                    assert arr.shape[0] in (expected, nx * ny), (p, name, arr.shape)
                else:
                    assert arr.shape[0] == expected, (p, name, arr.shape, expected)
            # 检查 RD 元数据
            if r["rd"].get("rule_type"):
                rule_types[r["rd"]["rule_type"]] = rule_types.get(r["rd"]["rule_type"], 0) + 1
        else:
            assert r["points"] is not None and r["points"].shape[0] == r["n_points"], (p, r["points"].shape if r["points"] is not None else None, r["n_points"])
            for name, arr in r["cell_data"].items():
                if len(arr.shape) > 1:
                    assert arr.shape[0] in (r["n_cells"], r["n_points"]), (p, name, arr.shape)
                else:
                    assert arr.shape[0] in (r["n_cells"], r["n_points"]), (p, name, arr.shape)
            if r["rd"].get("rule_type"):
                rule_types[r["rd"]["rule_type"]] = rule_types.get(r["rd"]["rule_type"], 0) + 1
        ok += 1
    except Exception as e:
        fail += 1
        failures.append((os.path.relpath(p, root_dir), str(e)[:100]))

print(f"解析完成: {ok} 成功 / {fail} 失败(共 {len(files)} 个文件)")
print(f"类型统计: ImageData {stats['ImageData']} / UnstructuredGrid {stats['UnstructuredGrid']}")
print(f"规则类型: {rule_types}")
for f, e in failures[:10]:
    print(f"  FAIL {f}: {e}")
sys.exit(1 if fail else 0)
