# -*- coding: utf-8 -*-
"""W1 预设导入/导出(preset_io)测试:纯 Python,无 bpy。
覆盖:export→import 往返 / 非法输入 ValueError / 去重覆盖 / 容错 / 预设合并。"""
import sys, os, json, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fileio.preset_io import (export_preset_dict, import_preset_dict,
                              write_user_preset, load_user_presets,
                              DEFAULT_USER_FILE)

# 1) export → import 往返一致
params = {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0, "wrap": True}
d = export_preset_dict(params, "网页拣选 · mitosis", seed_region="center_disc",
                       noise_ratio=0.3, preset_id="web_test_001")
d2 = import_preset_dict(d)
assert d2["id"] == "web_test_001" and d2["name"] == "网页拣选 · mitosis"
for key in ("Du", "Dv", "F", "k", "dt"):
    assert d2["params"][key] == params[key], f"往返失真: {key}"
assert d2["params"]["wrap"] is True
assert d2["rule"] == "Gray-Scott" and d2["seed_region"] == "center_disc"
assert d2["extensions"]["pattern_scale"] == 1.0  # 前瞻键默认值
print("[PASS] export→import 往返一致(五参数 + wrap + 前瞻键)")

# 2) 合法性校验:缺键/非数值/超范围 → ValueError
bad_cases = [
    ({}, "空对象"),
    ({"id": "x"}, "缺 name"),
    ({"id": "x", "name": "y"}, "缺 params"),
    ({"id": "x", "name": "y", "params": {"Du": 0.1, "Dv": 0.05, "F": 0.03, "k": 0.06}},
     "缺 dt"),
    ({"id": "x", "name": "y",
      "params": {"Du": "abc", "Dv": 0.05, "F": 0.03, "k": 0.06, "dt": 1.0}},
     "Du 非数值"),
    ({"id": "x", "name": "y",
      "params": {"Du": float("nan"), "Dv": 0.05, "F": 0.03, "k": 0.06, "dt": 1.0}},
     "Du NaN"),
    ({"id": "x", "name": "y",
      "params": {"Du": 5.0, "Dv": 0.05, "F": 0.03, "k": 0.06, "dt": 1.0}},
     "Du 超范围"),
    ({"id": "x", "name": "y",
      "params": {"Du": 0.16, "Dv": 0.08, "F": 0.9, "k": 0.06, "dt": 1.0}},
     "F 超范围"),
    ({"id": "x", "name": "y",
      "params": {"Du": 0.16, "Dv": 0.08, "F": 0.03, "k": 0.06, "dt": 0.0001}},
     "dt 超范围"),
    ({"id": "x", "name": "y",
      "params": {"Du": 0.16, "Dv": 0.08, "F": 0.03, "k": 0.06, "dt": 1.0},
      "seed_region": "invalid_region"}, "seed_region 非法"),
    (["not", "a", "dict"], "非 dict"),
]
for bad, label in bad_cases:
    try:
        import_preset_dict(bad)
        raise AssertionError(f"非法输入未拒绝: {label}")
    except ValueError:
        pass
print(f"[PASS] 非法输入全部拒绝: {len(bad_cases)} 种 → ValueError")

# 3) 去重覆盖语义(同 id 二写 → 列表长度不变,内容更新)
with tempfile.TemporaryDirectory() as td:
    uf = os.path.join(td, "user_presets.json")
    write_user_preset(d, uf)
    assert len(load_user_presets(uf)) == 1
    d_mod = dict(d, name="改名后的预设")
    write_user_preset(d_mod, uf)  # 同 id 覆盖
    lst = load_user_presets(uf)
    assert len(lst) == 1, f"同 id 未去重: {len(lst)}"
    assert lst[0]["name"] == "改名后的预设"
    # 不同 id 追加
    d_other = export_preset_dict(params, "第二个", preset_id="web_test_002")
    write_user_preset(d_other, uf)
    assert len(load_user_presets(uf)) == 2
print("[PASS] 去重覆盖: 同 id 覆盖, 异 id 追加")

# 4) 容错:文件不存在 / 损坏 JSON / 空列表
with tempfile.TemporaryDirectory() as td:
    missing = os.path.join(td, "missing.json")
    assert load_user_presets(missing) == []
    corrupt = os.path.join(td, "corrupt.json")
    with open(corrupt, "w", encoding="utf-8") as f:
        f.write("{broken json!!!")
    assert load_user_presets(corrupt) == []
    empty = os.path.join(td, "empty.json")
    with open(empty, "w", encoding="utf-8") as f:
        f.write("[]")
    assert load_user_presets(empty) == []
    # 混合列表:非 dict 条目被滤除,dict 条目保留
    mixed = os.path.join(td, "mixed.json")
    with open(mixed, "w", encoding="utf-8") as f:
        json.dump([d, 42, "str", None], f)
    lst = load_user_presets(mixed)
    assert len(lst) == 1 and lst[0]["id"] == "web_test_001"
print("[PASS] 容错: 不存在/损坏/空列表/混合列表")

# 5) presets.get_items 合并用户预设(直接注入缓存,模拟 load_user_presets 返回)
from presets import presets as P
P._USER_CACHE = [d]  # 注入用户预设(等价 load 成功)
try:
    items = P.get_items()
    user_items = [it for it in items if it[0] == "web_test_001"]
    assert len(user_items) == 1, "用户预设未并入 get_items"
    assert user_items[0][1].startswith("[导入] "), f"前缀缺失: {user_items[0][1]}"
    # id 唯一性
    ids = [it[0] for it in items]
    assert len(ids) == len(set(ids)), "get_items 存在重复 id"
    # get_preset 也能取到用户预设
    got = P.get_preset("web_test_001")
    assert got is not None and got["name"] == "网页拣选 · mitosis"
    # refresh_user_presets 重读(文件不存在 → 回落空列表)
    P.refresh_user_presets()
    assert P.get_preset("web_test_001") is None
finally:
    P._USER_CACHE = None
print("[PASS] 预设合并: [导入] 前缀 + id 唯一 + get_preset/refresh 可用")

print("\ntest_preset_io: all passed")
