# -*- coding: utf-8 -*-
"""P2-2/2-3/2-8 自测:CA 规则 / 网格生成器 / 3D 体素。"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ok = fail = 0

def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail += 1
        print(f"  [FAIL] {name}")

# ---- Conway Life:glider 平移 ----
from core.ca_rules import ConwayLifeRule
u = np.zeros((16, 16), dtype=np.float32)
glider = [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]
for x, y in glider:
    u[y, x] = 1.0
rule = ConwayLifeRule()
for _ in range(4):
    rule.update([u], wrap=True)
# 4 代后 glider 右下移 1 格:(2,1),(3,2),(1,3),(2,3),(3,3)
expected = [(2, 1), (3, 2), (1, 3), (2, 3), (3, 3)]
check("Conway glider 4 代后平移(1,1)且存活 5 格",
      u.sum() == 5 and all(u[y, x] == 1 for x, y in expected))
check("Conway 无 NaN", np.isfinite(u).all())

# ---- LargerThanLife 运行稳定性 ----
from core.ca_rules import LargerThanLifeRule
u2 = np.random.default_rng(1).random((32, 32)) < 0.3
u2 = u2.astype(np.float32)
ltl = LargerThanLifeRule()
for _ in range(20):
    ltl.update([u2], {"r": 3, "b_low": 0.2, "b_high": 0.4, "s_low": 0.2, "s_high": 0.4}, wrap=True)
check("LargerThanLife 20 代稳定", np.isfinite(u2).all() and set(np.unique(u2)) <= {0, 1})

# ---- SmoothLife 运行稳定性 ----
from core.ca_rules import SmoothLifeRule
u3 = np.random.default_rng(2).random((32, 32)).astype(np.float32)
sl = SmoothLifeRule()
for _ in range(50):
    sl.update([u3], wrap=True)
check("SmoothLife 50 步稳定且值域 [0,1]", np.isfinite(u3).all() and u3.min() >= 0 and u3.max() <= 1)

# ---- 网格生成器 ----
from core.meshgen import triangular, hexagonal, rhombille, geodesic_sphere, torus
verts, faces = triangular(10, 10)
check("triangular: 100 verts 162 faces", len(verts) == 100 and len(faces) == 2 * 9 * 9)
v, f = hexagonal(4, 4)
check("hexagonal: 顶点/面数为正且三角形", len(v) > 0 and len(f) == 4 * 4 * 6)
v, f = rhombille(4, 4)
check("rhombille: 4x4x12 = 192 三角形(每 cell 6 菱形)", len(f) == 4 * 4 * 12)
v, f = geodesic_sphere(2)
check("geodesic: 细分 2 后 320 面(二十面体)", len(f) == 20 * 4 ** 2)
v, f = torus(24, 12)
check("torus: 24x12x2 = 576 面", len(f) == 24 * 12 * 2)
check("所有网格顶点无 NaN", all(np.isfinite(x).all() for x, _ in
      [triangular(5, 5), hexagonal(3, 3), rhombille(3, 3), geodesic_sphere(1), torus(8, 4)]))

# ---- 3D 体素 ----
from core.field3d import RegularGridField3D, laplacian_7, GrayScottRule3D, extract_slice
c = np.ones((8, 8, 8), dtype=np.float32)
check("laplacian_7 常数场 → 0", np.allclose(laplacian_7(c), 0, atol=1e-6))
a = np.ones((16, 16, 16), dtype=np.float32)
b = np.zeros((16, 16, 16), dtype=np.float32)
rng = np.random.default_rng(5)
b[6:10, 6:10, 6:10] = rng.uniform(0, 1, (4, 4, 4)).astype(np.float32)
gs3 = GrayScottRule3D()
for _ in range(100):
    gs3.update([a, b], {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0}, wrap=False)
check("Gray-Scott 3D 100 步无 NaN", np.isfinite(a).all() and np.isfinite(b).all())
sl = extract_slice(b, axis=2)
check("切片形状正确", sl.shape == (16, 16))

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
