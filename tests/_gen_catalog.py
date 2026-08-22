# -*- coding: utf-8 -*-
"""从 patterns_catalog.json 生成按可用性分级排序的 markdown 表格。"""
import json, os

src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "patterns_catalog.json")
with open(src, encoding="utf-8") as f:
    pats = json.load(f)

def usable_rank(p):
    """可用性分级(对"导入 Pattern 为初始条件"功能):
    1 = Gray-Scott 标准参数型 2D(五参数齐全,导入即用)
    2 = 公式型 2D(参数/文献参考;初始场多为生成器型,含 GS 特殊变体)
    3 = 内核型 2D(本项目无内核引擎,仅文献参考)
    4 = 3D/vtu(导入不支持)
    注:2D vti 无一带真实初始场(唯一 nonzero 是 1D),故无"可续跑"层。
    """
    is_2d_vti = p.get("type") == "vti" and p.get("dims") and p["dims"][2] == 1
    if not is_2d_vti:
        return 4
    if p.get("rule_type") == "kernel":
        return 3
    # Gray-Scott 判定:内置型,或公式型且 rule_name 含 Gray-Scott
    is_gs = (p.get("rule_type") == "inbuilt" or
             "Gray-Scott" in (p.get("rule_name") or "") or
             "grayscott" in p["file"].lower())
    if is_gs and p.get("_gs_std_params"):
        return 1
    return 2

RANK_LABEL = {1: "① 导入即用", 2: "② 参数参考", 3: "③ 仅文献参考", 4: "④ 不支持导入"}
RANK_TITLE = {
    1: "① 导入即用 —— Gray-Scott 标准参数型(2D,五参数齐全)",
    2: "② 参数参考 —— 公式型/特殊变体(2D)",
    3: "③ 仅文献参考 —— 内核型(2D,本项目无内核引擎)",
    4: "④ 不支持导入 —— 3D 体素 / .vtu 网格型",
}

for p in pats:
    p["rank"] = usable_rank(p)
pats.sort(key=lambda p: (p["rank"], p["file"].lower()))

lines = []
lines.append("# Ready 生态 93 个 Pattern 目录(按可用性排序)")
lines.append("")
lines.append("> 生成:2026-08-18 ｜ 数据源:Ready 0.6 官方 Patterns 目录 ｜ 解析:本项目 fileio.vtk_xml(93/93)")
lines.append("")
lines.append('**可用性分级说明**(对本插件的"导入 Pattern 为初始条件"功能而言):')
lines.append("")
lines.append("| 级 | 含义 | 数量 |")
lines.append("|---|---|---|")
from collections import Counter
cnt = Counter(p["rank"] for p in pats)
for rk in (1, 2, 3, 4):
    lines.append(f"| {RANK_LABEL[rk]} | {RANK_TITLE[rk].split('——')[1].strip()} | {cnt.get(rk, 0)} |")
lines.append("")
lines.append("> 注:全部 93 个 pattern 中,仅 grayscott_1D 带真实初始场(1D,不在导入范围);"
             "2D pattern 均为生成器型(初始场为空,导入时自动改用基底+中央种子)。")
lines.append("")

cur = None
for p in pats:
    if p["rank"] != cur:
        cur = p["rank"]
        lines.append(f"\n## {RANK_TITLE[cur]}({cnt.get(cur, 0)} 个)\n")
        lines.append("| Pattern | 规则 | 化学量 | 参数 | 文献描述/说明 |")
        lines.append("|---|---|---|---|---|")
    name = p["file"].replace("\\", "/")
    rule = p.get("rule_name") or p.get("rule_type", "?")
    desc = p.get("desc", "")
    if p.get("init") == "nonzero":
        desc = "★**真实初始场** " + desc
    elif p.get("init") == "zero":
        desc = "(生成器型,场为空) " + desc
    # 化学量显示修正与标注
    nchem = p.get("n_chem", 0) or 2  # inbuilt GS 记录为 0,实为双化学量
    chem_disp = f"{nchem}"
    if nchem > 2:
        chem_disp += "(导入取前两个)"
    if p.get("dims") and p["dims"][2] == 1 and p["dims"][1] == 1:
        name += " *(1D)*"
    lines.append(f"| {name} | {rule} | {chem_disp} | {p.get('params', '')} | {desc} |")

dst = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "patterns-catalog.md")
with open(dst, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"written {dst}, {len(pats)} patterns")
for rk in (1, 2, 3, 4, 5):
    print(f"  rank{rk}: {cnt.get(rk, 0)}")
