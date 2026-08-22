# -*- coding: utf-8 -*-
"""提取 93 个 pattern 元数据 → JSON(供表格生成)。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fileio.vtk_xml import read_file

root = r"C:\Users\Administrator\.openclaw-autoclaw\workspace\.cluster\ready-blender-analysis\repo_src\ready-Ready-0.6\Patterns"
out = []
for dp, _, fn in os.walk(root):
    for f in sorted(fn):
        if not f.endswith((".vti", ".vtu")):
            continue
        fp = os.path.join(dp, f)
        try:
            r = read_file(fp)
        except Exception as e:
            out.append({"file": os.path.relpath(fp, root), "error": str(e)})
            continue
        rd = r.get("rd", {})
        desc = (rd.get("description") or "").strip()
        # 去标签/压缩空白
        import re
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()
        if len(desc) > 150:
            desc = desc[:147] + "..."
        params = rd.get("parameters", {})
        pstr = ", ".join(f"{k}={v}" for k, v in params.items()
                         if isinstance(v, (int, float)) and len(params) <= 10)
        if len(pstr) > 90:
            pstr = pstr[:87] + "..."
        # 初始场检测
        init_state = "unknown"
        if r["type"] == "ImageData":
            pd = r["point_data"]
            arrs = None
            for ka, kb in (("a", "b"), ("u", "v")):
                if ka in pd and kb in pd:
                    arrs = (pd[ka], pd[kb]); break
            if arrs is None:
                multi = [v for v in pd.values() if hasattr(v, "ndim") and v.ndim == 2 and v.shape[1] >= 2]
                if multi: arrs = (multi[0][:, 0], multi[0][:, 1])
            if arrs is not None:
                import numpy as np
                nz = float(np.abs(arrs[0]).max()) > 1e-9 or float(np.abs(arrs[1]).max()) > 1e-9
                init_state = "nonzero" if nz else "zero"
        out.append({
            "file": os.path.relpath(fp, root),
            "type": "vti" if f.endswith(".vti") else "vtu",
            "dims": list(r["dimensions"]) if r["type"] == "ImageData" else None,
            "rule_type": rd.get("rule_type", ""),
            "rule_name": rd.get("rule_name", ""),
            "n_chem": rd.get("n_chemicals", 0),
            "init": init_state,
            "desc": desc,
            "params": pstr,
            "formula": (rd.get("formula") or "").strip().replace("\n", " ")[:120],
            # GS 标准五参数齐全且无额外调制参数(noise/delta_x/k1k2 等) → 参数可直接映射
            "_gs_std_params": set(params.keys()) >= {"timestep", "D_a", "D_b", "F", "k"}
                              and set(params.keys()) <= {"timestep", "D_a", "D_b", "F", "k"},
        })

dst = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "patterns_catalog.json")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"extracted {len(out)} -> {dst}")
from collections import Counter
print(Counter(p.get("rule_type") for p in out))
print(Counter(p.get("init") for p in out))
