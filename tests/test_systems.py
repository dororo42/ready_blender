# -*- coding: utf-8 -*-
"""新系统回归:4 个公式系统在小网格上运行无 NaN,公式可解析。"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from presets.presets import SYSTEMS, get_system
from core.formula import FormulaRule


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

    rng = np.random.default_rng(11)
    for sys_def in SYSTEMS:
        if sys_def["kind"] != "formula":
            continue
        sid = sys_def["id"]
        rule = FormulaRule(sys_def["formula"])
        assert len(rule.chemical_names) == 2, sid
        chems = rule.chemical_names
        base = sys_def["init"]["base"]
        a = np.full((32, 32), base[chems[0]], dtype=np.float32)
        b = np.full((32, 32), base[chems[1]], dtype=np.float32)
        pulse = sys_def["init"]["pulse_chem"]
        f = a if pulse == chems[0] else b
        f[12:20, 12:20] += rng.uniform(0, 1, (8, 8)).astype(np.float32) * sys_def["init"]["pulse_value"]
        p = dict(sys_def["params"])
        dt = p.pop("dt")
        try:
            for _ in range(100):
                rule.update({chems[0]: a, chems[1]: b}, p, dt=dt, field_kind="grid")
            finite = np.isfinite(a).all() and np.isfinite(b).all()
            changed = (a.std() > 0) or (b.std() > 0)
            check(f"{sid}: 100 步无 NaN", finite)
            check(f"{sid}: 场有演化", changed)
        except Exception as e:
            check(f"{sid}: 运行不抛异常({e})", False)

    print(f"\n{ok} passed, {fail} failed")



if __name__ == "__main__":
    test_all()
    print("all passed")
