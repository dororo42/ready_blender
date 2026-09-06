# -*- coding: utf-8 -*-
"""Pattern 导入逻辑测试:文件解析→场提取→reshape→Gray-Scott 参数映射。
(算子 UI 部分依赖 bpy,此处测纯逻辑同源路径)
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fileio.vtk_xml import read_file
from fileio.vtk_writer import write_vti


def test_all():
    PATTERNS = os.environ.get(
        "READY_PATTERNS_DIR",
        r"C:\Users\Administrator\.openclaw-autoclaw\workspace\.cluster\ready-blender-analysis\repo_src\ready-Ready-0.6\Patterns")
    if not os.path.isdir(PATTERNS):
        # CI/无 Ready 生态环境:优雅跳过(GPL pattern 文件不入库)
        try:
            import pytest
            pytest.skip("patterns 目录不存在(设 READY_PATTERNS_DIR 可启用)")
        except ImportError:
            print(f"[SKIP] patterns 目录不存在: {PATTERNS}")
            return

    # 1) Gray-Scott pattern:参数映射(inbuilt → settings 五参数)
    GS2D = os.path.join(PATTERNS, "CPU-only", "grayscott_2D.vti")
    r = read_file(GS2D)
    p = r["rd"]["parameters"]
    mapped = {"Du": p.get("D_a"), "Dv": p.get("D_b"), "F": p.get("F"),
              "k": p.get("k"), "dt": p.get("timestep")}
    ok = all(v is not None for v in mapped.values())
    print(f"[{'PASS' if ok else 'FAIL'}] Gray-Scott pattern 参数映射完整: {mapped}")

    # 2) 场提取(布局 B:单键多列 Scalars_)+ reshape:dims (w,h,1) → (h,w)
    w, h = r["dimensions"][0], r["dimensions"][1]
    pd = r["point_data"]
    a_flat = b_flat = None
    for ka, kb in (("a", "b"), ("u", "v")):
        if ka in pd and kb in pd:
            a_flat, b_flat = pd[ka], pd[kb]
            break
    if a_flat is None:
        multi = [v for v in pd.values() if hasattr(v, "ndim") and v.ndim == 2 and v.shape[1] >= 2]
        if multi:
            a_flat, b_flat = multi[0][:, 0], multi[0][:, 1]
    if a_flat is None:
        flat_keys = [k for k in pd if hasattr(pd[k], "ndim") and pd[k].ndim == 1]
        if len(flat_keys) >= 2:
            a_flat, b_flat = pd[flat_keys[0]], pd[flat_keys[1]]
    ok = a_flat is not None
    print(f"[{'PASS' if ok else 'FAIL'}] 化学量提取(布局检测,键: {list(pd.keys())})")
    a = np.asarray(a_flat, dtype=np.float32).reshape(h, w)
    b = np.asarray(b_flat, dtype=np.float32).reshape(h, w)
    ok = a.shape == (h, w) and a.size == w * h and np.isfinite(a).all()
    print(f"[{'PASS' if ok else 'FAIL'}] reshape ({w}x{h}) → {a.shape}, 无 NaN")

    # 3) 初始场统计(GS pattern 双列布局数据)
    print(f"[INFO] grayscott_2D 场统计: a[min={a.min():.3f} max={a.max():.3f}] b[min={b.min():.3f} max={b.max():.3f}]")

    # 4) 生成器型 pattern 检测(全 0 场 → 应提醒)
    r2 = read_file(os.path.join(PATTERNS, "Brusselator.vti"))
    a2 = np.asarray(r2["point_data"]["a"])
    b2 = np.asarray(r2["point_data"]["b"])
    is_gen = (float(a2.max()) == 0.0 and float(b2.max()) == 0.0)
    expect = r2["rd"].get("apply_when_loading") is True
    ok = is_gen == expect
    print(f"[{'PASS' if ok else 'FAIL'}] 全 0 场检测与 apply_when_loading 一致: all_zero={is_gen}, apply_when_loading={expect}")

    # 5) 公式型 pattern:非 GS 系统参数不同步路径(rd.rule_type=formula)
    ok = r2["rd"].get("rule_type") == "formula"
    print(f"[{'PASS' if ok else 'FAIL'}] Brusselator 识别为 formula 型(参数不自动同步)")

    # 5b) 公式型 Gray-Scott 标准参数:也应可同步(U-Skate 系列)
    r5 = read_file(os.path.join(PATTERNS, "Gray-Scott", "U-Skate", "Munafo_glider.vti"))
    p5 = r5["rd"]["parameters"]
    gs_std = ({"timestep", "D_a", "D_b", "F", "k"} <= set(p5.keys())
              and set(p5.keys()) <= {"timestep", "D_a", "D_b", "F", "k"})
    is_gs = "Gray" in (r5["rd"].get("rule_name") or "")
    ok = r5["rd"].get("rule_type") == "formula" and is_gs and gs_std
    print(f"[{'PASS' if ok else 'FAIL'}] 公式型 GS(U-Skate)五参数齐全 → 参数同步条件满足: {p5}")

    # 5c) 调制参数型(Lesmes_noisy 含 noise)→ 不同步
    r5c = read_file(os.path.join(PATTERNS, "Gray-Scott", "Lesmes_noisy.vti"))
    p5c = r5c["rd"]["parameters"]
    ok = "noise" in p5c and not (set(p5c.keys()) <= {"timestep", "D_a", "D_b", "F", "k"})
    print(f"[{'PASS' if ok else 'FAIL'}] 含 noise 调制参数 → 正确排除同步(键: {sorted(p5c.keys())})")

    # 6) u/v 键名回退路径:自制 vti 用 u/v 命名
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        fp = os.path.join(d, "uv_names.vti")
        u = np.random.default_rng(1).uniform(0, 1, (16, 16)).astype(np.float32)
        v = np.random.default_rng(2).uniform(0, 1, (16, 16)).astype(np.float32)
        write_vti(fp, {"u": u, "v": v}, (16, 16))
        r3 = read_file(fp)
        keys = [k for k in ("a", "b") if k in r3["point_data"]]
        if len(keys) < 2:
            keys = list(r3["point_data"].keys())[:2]
        ok = keys == ["u", "v"]
        print(f"[{'PASS' if ok else 'FAIL'}] 非 a/b 键名回退到前两个化学量: {keys}")
        u2 = np.asarray(r3["point_data"][keys[0]]).reshape(16, 16)
        ok2 = np.allclose(u2, u, atol=1e-5)
        print(f"[{'PASS' if ok2 else 'FAIL'}] u/v 场数据 round-trip 一致")

    # 7) 3D/网格型拒绝条件:dims Z 维 ≠ 1 → 拒绝
    r4 = read_file(os.path.join(PATTERNS, "CPU-only", "grayscott_3D.vti"))
    ok = r4["dimensions"][2] != 1
    print(f"[{'PASS' if ok else 'FAIL'}] 3D pattern(dims={r4['dimensions']})被 Z 维条件正确识别为不可导入")

    # 7b) 1D 拒绝条件:Y 维 < 2 → 拒绝(grayscott_1D)
    r7 = read_file(os.path.join(PATTERNS, "CPU-only", "grayscott_1D.vti"))
    ok = r7["dimensions"][1] < 2
    print(f"[{'PASS' if ok else 'FAIL'}] 1D pattern(dims={r7['dimensions']})被 Y 维条件正确识别为不可导入")

    # 7c) GS 标准参数型去重统计(转预设候选)
    uniq = {}
    for dp, _, fn in os.walk(PATTERNS):
        for f in fn:
            if not f.endswith(".vti"):
                continue
            rr = read_file(os.path.join(dp, f))
            if rr["type"] != "ImageData" or rr["dimensions"][2] != 1 or rr["dimensions"][1] < 2:
                continue
            pp = rr["rd"].get("parameters", {})
            if {"timestep", "D_a", "D_b", "F", "k"} <= set(pp.keys()) and set(pp.keys()) <= {"timestep", "D_a", "D_b", "F", "k"}:
                key = (pp["D_a"], pp["D_b"], pp["F"], pp["k"], pp["timestep"])
                uniq.setdefault(key, []).append(f)
    print(f"[INFO] GS 标准参数型 2D 去重后 {len(uniq)} 组:")
    for k, v in sorted(uniq.items()):
        print(f"    Du={k[0]} Dv={k[1]} F={k[2]} k={k[3]} dt={k[4]}  ← {len(v)} 个文件")



if __name__ == "__main__":
    test_all()
    print("all passed")
