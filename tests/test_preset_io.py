# -*- coding: utf-8 -*-
"""W1 preset_io 测试:往返/校验/去重/容错/合并唯一性。"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fileio.preset_io import (export_preset_dict, import_preset_dict,
                              import_preset_file, import_preset_text,
                              load_user_presets, write_user_preset)
from presets import presets as pp


def test_roundtrip():
    d = export_preset_dict({"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649,
                            "dt": 1.0, "wrap": True}, "测试预设",
                           seed_region="center_disc", noise_ratio=0.3)
    d2 = import_preset_dict(json.loads(json.dumps(d)))
    assert d2["name"] == "测试预设"
    assert d2["params"]["F"] == 0.0367
    assert d2["params"]["wrap"] is True
    assert d2["seed_region"] == "center_disc"
    # extensions 前瞻键保留
    assert set(d2["extensions"]) == {"pattern_scale", "style_map",
                                     "orientation", "flow"}


def test_invalid():
    for bad in [
        {}, {"name": "x"}, {"id": "x", "name": "y"},
        {"id": "x", "name": "y", "params": {"Du": 1}},
        {"id": "x", "name": "y", "params": {"Du": 1, "Dv": 1, "F": 1,
                                            "k": 1, "dt": 1},
         "seed_region": "bogus"},
        {"id": "x", "name": "y", "params": {"Du": 99, "Dv": 1, "F": 1,
                                            "k": 1, "dt": 1}},
        {"id": "x", "name": "y", "params": {"Du": 1, "Dv": 1, "F": "nan",
                                            "k": 1, "dt": 1}},
    ]:
        try:
            import_preset_dict(bad)
            raise AssertionError(f"应抛 ValueError: {bad}")
        except ValueError:
            pass


def test_user_file_dedup(tmpdir=None):
    with tempfile.TemporaryDirectory() as td:
        uf = os.path.join(td, "user_presets.json")
        d1 = export_preset_dict({"Du": 0.1, "Dv": 0.05, "F": 0.04,
                                 "k": 0.06, "dt": 1.0}, "A", preset_id="p1")
        write_user_preset(d1, uf)
        assert len(load_user_presets(uf)) == 1
        d2 = export_preset_dict({"Du": 0.2, "Dv": 0.1, "F": 0.05,
                                 "k": 0.07, "dt": 1.0}, "A2", preset_id="p1")
        write_user_preset(d2, uf)  # 同 id → 覆盖
        items = load_user_presets(uf)
        assert len(items) == 1 and items[0]["params"]["Du"] == 0.2


def test_load_missing_and_corrupt():
    with tempfile.TemporaryDirectory() as td:
        uf = os.path.join(td, "nope.json")
        assert load_user_presets(uf) == []
        with open(uf, "w", encoding="utf-8") as f:
            f.write("{broken")
        assert load_user_presets(uf) == []


def test_import_preset_text_and_file():
    import tempfile
    good = json.dumps(export_preset_dict(
        {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0},
        "剪贴板测试", preset_id="cb_1"), ensure_ascii=False)
    # 文本导入
    d = import_preset_text(good)
    assert d["name"] == "剪贴板测试"
    # 非法文本
    for bad in ("", "   ", "not json", "{"):
        try:
            import_preset_text(bad)
            raise AssertionError(f"应抛 ValueError: {bad!r}")
        except ValueError:
            pass
    # 文件:UTF-8 无 BOM / 带 BOM / GBK 三种编码
    with tempfile.TemporaryDirectory() as td:
        for enc, name in (("utf-8", "a.json"), ("utf-8-sig", "bom.json"),
                          ("gbk", "gbk.json")):
            path = os.path.join(td, name)
            with open(path, "w", encoding=enc) as f:
                f.write(good)
            d2 = import_preset_file(path)
            assert d2["params"]["F"] == 0.0367, name


def test_write_fallback_on_readonly():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        import fileio.preset_io as pio
        old_fb = pio._FALLBACK_USER_FILE
        old_def = pio.DEFAULT_USER_FILE
        blocker = os.path.join(td, "blocker")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("x")
        pio.DEFAULT_USER_FILE = os.path.join(blocker, "user_presets.json")
        pio._FALLBACK_USER_FILE = os.path.join(td, "fb.json")
        try:
            d = export_preset_dict({"Du": 0.1, "Dv": 0.05, "F": 0.04,
                                    "k": 0.06, "dt": 1.0}, "FB", preset_id="fb_1")
            target = write_user_preset(d)  # 无参 → 默认路径写失败 → fallback
            assert target == pio._FALLBACK_USER_FILE
            assert os.path.exists(target)
            items = load_user_presets()  # 无参 → 默认路径缺失 → fallback 兜底
            assert any(x["id"] == "fb_1" for x in items), items
        finally:
            pio.DEFAULT_USER_FILE = old_def
            pio._FALLBACK_USER_FILE = old_fb


def test_merge_unique_ids():
    # 用户预设合并后 id 唯一且带 [导入] 前缀
    with tempfile.TemporaryDirectory() as td:
        uf = os.path.join(td, "user_presets.json")
        d = export_preset_dict({"Du": 0.1, "Dv": 0.05, "F": 0.04,
                                "k": 0.06, "dt": 1.0}, "网页拣选",
                               preset_id="web_test_1")
        write_user_preset(d, uf)
        pp._USER_CACHE = None
        orig = pp._load_user
        pp._load_user = lambda: load_user_presets(uf)
        try:
            items = pp.get_items()
            ids = [it[0] for it in items]
            assert len(ids) == len(set(ids))
            assert "web_test_1" in ids
            named = [it[1] for it in items if it[0] == "web_test_1"]
            assert named and named[0].startswith("[导入]")
            p = pp.get_preset("web_test_1")
            assert p is not None and p["params"]["F"] == 0.04
        finally:
            pp._load_user = orig
            pp._USER_CACHE = None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("preset_io: all passed")