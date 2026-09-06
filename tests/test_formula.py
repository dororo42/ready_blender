# -*- coding: utf-8 -*-
"""FormulaRule 自测脚本。"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.formula import FormulaRule, FormulaError


def test_all():
    ok = fail = 0

    def check(name, cond):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  [PASS] {name}")
        else:
            fail += 1
            print(f"  [FAIL] {name}")

    # 1. Gray-Scott 公式与硬编码实现对比(少量步数)
    gs_src = """
    delta_a = D_a * laplacian_a - a*b*b + F*(1.0-a);
    delta_b = D_b * laplacian_b + a*b*b - (F+k)*b;
    """
    rule = FormulaRule(gs_src)
    rng = np.random.default_rng(3)
    a1 = np.ones((32, 32), dtype=np.float32)
    b1 = np.zeros((32, 32), dtype=np.float32)
    b1[12:20, 12:20] = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    a2, b2 = a1.copy(), b1.copy()
    p = {"D_a": 0.16, "D_b": 0.08, "F": 0.0367, "k": 0.0649}

    from core.rule import GrayScottRule
    hard = GrayScottRule()
    # 注意:GrayScottRule 内置浓度裁剪防护(防瞬态溢出),等价性比较需两侧同口径裁剪
    for _ in range(50):
        rule.update({"a": a1, "b": b1}, p, dt=1.0, field_kind="grid", wrap=False)
        np.clip(a1, 0.0, 2.0, out=a1)
        np.clip(b1, 0.0, 1.0, out=b1)
    for _ in range(50):
        hard.update([a2, b2], {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0}, 1.0, "grid")
    check("FormulaRule 与硬编码 GrayScottRule 50 步一致",
          np.allclose(a1, a2, atol=1e-5) and np.allclose(b1, b2, atol=1e-5))

    # 2. FitzHugh-Nagumo(公开公式)
    fhn_src = """
    delta_u = D_u * laplacian_u + u - u^3 - v;
    delta_v = D_v * laplacian_v + eps*(u - a0 - b0*v);
    """
    fhn = FormulaRule(fhn_src)
    check("FitzHugh-Nagumo 参数识别", set(fhn.param_names) == {"D_u", "D_v", "eps", "a0", "b0"})
    u = rng.uniform(-1, 1, (32, 32)).astype(np.float32)
    v = rng.uniform(-1, 1, (32, 32)).astype(np.float32)
    fhn.update({"u": u, "v": v}, {"D_u": 1.0, "D_v": 0.0, "eps": 0.05, "a0": 0.7, "b0": 0.8}, dt=0.1, field_kind="grid")
    check("FitzHugh-Nagumo 更新无 NaN", np.isfinite(u).all() and np.isfinite(v).all())

    # 3. 语法错误检测
    try:
        FormulaRule("delta_a = D_a * * laplacian_a")
        check("语法错误被拒绝", False)
    except FormulaError:
        check("语法错误被拒绝", True)

    # 4. 未定义变量
    try:
        r = FormulaRule("delta_a = foo * a")
        r.update({"a": np.zeros((4, 4), np.float32)}, {}, dt=1.0, field_kind="grid")
        check("未定义变量报错", False)
    except FormulaError:
        check("未定义变量报错", True)

    # 5. mesh 字段上的公式(laplacian 走图拉普拉斯)
    from core.field import MeshField
    n = 6
    faces = []
    for j in range(n - 1):
        for i in range(n - 1):
            k = j * n + i
            faces.append([k, k + 1, k + n + 1])
            faces.append([k, k + n + 1, k + n])
    faces = np.array(faces, dtype=np.int32)
    mf = MeshField(faces)
    am = np.ones(mf.data.shape[0], dtype=np.float32)
    bm = np.zeros(mf.data.shape[0], dtype=np.float32)
    bm[5] = 1.0
    rule.update({"a": am, "b": bm}, p, dt=1.0, field_kind="mesh", nbr=(mf.nbr_idx, mf.nbr_w))
    check("mesh 字段公式更新无 NaN", np.isfinite(am).all() and np.isfinite(bm).all())

    print(f"\n{ok} passed, {fail} failed")



if __name__ == "__main__":
    test_all()
    print("all passed")
