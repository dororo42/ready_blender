# -*- coding: utf-8 -*-
"""M0 基准脚本:三场景性能 + 邻接构建实测 + Pearson 图案视觉验证。
运行:python benchmark_m0.py
"""
import time, sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.rule import GrayScottRule
from core.field import RegularGridField, MeshField, build_face_adjacency

def make_grid_field(size, wrap=True):
    return RegularGridField((size, size), wrap=wrap, dtype=np.float32)

def init_grid(a, b, seed=42):
    rng = np.random.default_rng(seed)
    a.data[:] = 1.0
    b.data[:] = 0.0
    cx, cy = a.shape[0]//2, a.shape[1]//2
    s = a.shape[0]//8
    b.data[cy-s:cy+s, cx-s:cx+s] = rng.uniform(0, 1, (2*s, 2*s)).astype(np.float32)

def bench_grid(size, n_steps=1000):
    a = make_grid_field(size)
    b = make_grid_field(size)
    init_grid(a, b)
    params = {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0, "wrap": True}
    rule = GrayScottRule()
    t0 = time.perf_counter()
    for _ in range(n_steps):
        rule.update([a.data, b.data], params, 1.0, "grid")
    elapsed = time.perf_counter() - t0
    return {"size": f"{size}x{size}", "steps": n_steps, "elapsed_s": round(elapsed, 3),
            "steps_per_s": round(n_steps / elapsed, 1), "ms_per_step": round(elapsed / n_steps * 1000, 2)}

def make_triangulated_grid(n):
    """n x n 顶点三角化平面,返回 faces (F,3)。"""
    faces = []
    for j in range(n - 1):
        for i in range(n - 1):
            p = j * n + i
            faces.append([p, p + 1, p + n + 1])
            faces.append([p, p + n + 1, p + n])
    return np.array(faces, dtype=np.int32)

def bench_mesh(n_verts_side, n_steps=1000):
    faces = make_triangulated_grid(n_verts_side)
    t_build0 = time.perf_counter()
    mf = MeshField(faces, kind="vertex")
    t_build = time.perf_counter() - t_build0
    rng = np.random.default_rng(99)
    a = np.ones(mf.data.shape[0], dtype=np.float32)
    b = np.zeros(mf.data.shape[0], dtype=np.float32)
    sel = rng.random(len(a)) < 0.03
    b[sel] = rng.uniform(0, 1, sel.sum()).astype(np.float32)
    params = {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0}
    rule = GrayScottRule()
    nbr = (mf.nbr_idx, mf.nbr_w)
    t0 = time.perf_counter()
    for _ in range(n_steps):
        rule.update([a, b], params, 1.0, "mesh", nbr=nbr)
    elapsed = time.perf_counter() - t0
    n_cells = faces.shape[0]
    return {"mesh": f"{n_verts_side}x{n_verts_side} verts", "n_cells": n_cells, "max_k": mf.max_k,
            "avg_k": round(mf.avg_k, 1), "build_ms": round(t_build * 1000, 1),
            "steps": n_steps, "elapsed_s": round(elapsed, 3),
            "steps_per_s": round(n_steps / elapsed, 1), "ms_per_step": round(elapsed / n_steps * 1000, 2)}

def save_pearson_image():
    """跑 256² Gray-Scott 5000 步,保存 b 场为 PNG(Pearson 1993 经典斑图验证)。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    a = make_grid_field(256, wrap=True)
    b = make_grid_field(256, wrap=True)
    init_grid(a, b)
    params = {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0, "wrap": True}
    rule = GrayScottRule()
    for _ in range(5000):
        rule.update([a.data, b.data], params, 1.0, "grid")
    out = os.path.join(os.path.dirname(__file__), "..", "DELIVERY", "m0_pearson_256.png")
    out = os.path.normpath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    im0 = ax[0].imshow(a.data, cmap="viridis", vmin=0, vmax=1)
    ax[0].set_title("chemical a (substrate)")
    fig.colorbar(im0, ax=ax[0], fraction=0.046)
    im1 = ax[1].imshow(b.data, cmap="magma", vmin=0, vmax=0.5)
    ax[1].set_title("chemical b (catalyst)")
    fig.colorbar(im1, ax=ax[1], fraction=0.046)
    fig.suptitle("Gray-Scott 256² · 5000 steps · Pearson 1993 parameters", fontsize=13)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out

if __name__ == "__main__":
    results = {}
    print("=== M0 Performance Benchmark ===\n")

    # Scene 1: 256² grid
    print("[1/4] 256² regular grid, 1000 steps...")
    r1 = bench_grid(256, 1000)
    print(f"  {r1['steps_per_s']} steps/s | {r1['ms_per_step']} ms/step | {r1['elapsed_s']}s total")
    results["grid_256"] = r1

    # Scene 2: 512² grid
    print("[2/4] 512² regular grid, 1000 steps...")
    r2 = bench_grid(512, 1000)
    print(f"  {r2['steps_per_s']} steps/s | {r2['ms_per_step']} ms/step | {r2['elapsed_s']}s total")
    results["grid_512"] = r2

    # Scene 3: 10k mesh (~50x50 verts → 4802 faces)
    print("[3/4] mesh 50x50 verts (~4802 faces), 1000 steps...")
    r3 = bench_mesh(50, 1000)
    print(f"  {r3['n_cells']} cells | K avg={r3['avg_k']} max={r3['max_k']} | build={r3['build_ms']}ms")
    print(f"  {r3['steps_per_s']} steps/s | {r3['ms_per_step']} ms/step | {r3['elapsed_s']}s total")
    results["mesh_10k"] = r3

    # Scene 4: 50k mesh (~115x115 verts → 25922 faces)
    print("[4/4] mesh 115x115 verts (~25922 faces), 1000 steps...")
    r4 = bench_mesh(115, 1000)
    print(f"  {r4['n_cells']} cells | K avg={r4['avg_k']} max={r4['max_k']} | build={r4['build_ms']}ms")
    print(f"  {r4['steps_per_s']} steps/s | {r4['ms_per_step']} ms/step | {r4['elapsed_s']}s total")
    results["mesh_50k"] = r4

    # 10k-step projection for performance budget verification
    print("\n=== Performance Budget Check (10,000 steps) ===")
    for label, r in results.items():
        proj10k = r["ms_per_step"] * 10000 / 1000
        ok = "✓ PASS" if proj10k < 300 else "✗ FAIL"
        print(f"  {label}: projected 10k steps ≈ {proj10k:.1f}s {ok} (budget <300s)")

    # Pearson image
    print("\n=== Pearson 1993 Visual Verification ===")
    png = save_pearson_image()
    if png:
        print(f"  Saved: {png}")
        results["pearson_image"] = os.path.basename(png)
    else:
        print("  matplotlib not available, skipping PNG")

    # Save JSON
    out_json = os.path.join(os.path.dirname(__file__), "..", "DELIVERY", "m0_benchmark.json")
    out_json = os.path.normpath(out_json)
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_json}")
