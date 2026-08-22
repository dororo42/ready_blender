# -*- coding: utf-8 -*-
"""W1:网页导出/导入用户预设(纯 Python,无 bpy,可独立测试)。

Schema(与 presets.json 条目同构,extensions 为前瞻键):
{
  "id": "web_YYYYMMDD_HHMMSS",
  "name": "...",
  "rule": "Gray-Scott",
  "params": {"Du": .., "Dv": .., "F": .., "k": .., "dt": .., "wrap": true},
  "seed_region": "center_disc",
  "noise_ratio": 0.3,
  "source": "RD_Tool 本地网页导出",
  "exported_at": "ISO",
  "extensions": {"pattern_scale": 1.0, "style_map": null, "orientation": null, "flow": null}
}
"""
from __future__ import annotations
import json
import os
import time

_PARAM_KEYS = ("Du", "Dv", "F", "k", "dt")
_WRAP_KEYS = ("wrap",)
_SEED_REGIONS = ("center_square", "center_disc", "uniform_sparse", "global",
                 "center_square_0.25")
_EXT_KEYS = ("pattern_scale", "style_map", "orientation", "flow")

# 插件根(本文件在 fileio/)
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_USER_FILE = os.path.join(_PLUGIN_ROOT, "presets", "user_presets.json")


def _now_id():
    return "web_" + time.strftime("%Y%m%d_%H%M%S")


def export_preset_dict(params, name, seed_region="center_disc",
                       noise_ratio=0.3, source="RD_Tool 本地网页导出",
                       preset_id=None, extensions=None):
    """组装 W4 schema dict(params 至少含 Du/Dv/F/k/dt)。"""
    p = dict(params)
    d = {
        "id": preset_id or _now_id(),
        "name": name,
        "rule": "Gray-Scott",
        "params": p,
        "seed_region": seed_region,
        "noise_ratio": float(noise_ratio),
        "source": source,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "extensions": {
            "pattern_scale": 1.0, "style_map": None,
            "orientation": None, "flow": None,
        },
    }
    if extensions:
        d["extensions"].update(extensions)
    return d


def import_preset_dict(d):
    """校验并规范化网页/文件导入的预设 dict;非法抛 ValueError。

    规则:id/name/params 必填;params 五键齐全且数值合法(有限数、在物理范围);
    wrap 可选布尔;未知顶层键(extensions 等)原样保留;返回新 dict(不修改入参)。
    """
    if not isinstance(d, dict):
        raise ValueError("预设必须是 JSON 对象")
    out = dict(d)
    for key in ("id", "name"):
        v = out.get(key)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"缺少必填字段: {key}")
    params = out.get("params")
    if not isinstance(params, dict):
        raise ValueError("缺少 params 对象")
    p = dict(params)
    for key in _PARAM_KEYS:
        v = p.get(key)
        if v is None:
            raise ValueError(f"params 缺少 {key}")
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"params.{key} 不是数值")
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError(f"params.{key} 非有限数")
        p[key] = v
    if "wrap" in p:
        p["wrap"] = bool(p["wrap"])
    for key in ("Du", "Dv"):
        if not (0.0 <= p[key] <= 2.0):
            raise ValueError(f"params.{key} 超出范围 [0,2]")
    for key in ("F", "k"):
        if not (0.0 <= p[key] <= 0.5):
            raise ValueError(f"params.{key} 超出范围 [0,0.5]")
    if not (0.001 <= p["dt"] <= 10.0):
        raise ValueError("params.dt 超出范围")
    sr = out.get("seed_region", "center_disc")
    if sr not in _SEED_REGIONS:
        raise ValueError(f"seed_region 非法: {sr}")
    out["seed_region"] = sr
    out["params"] = p
    return out


def load_user_presets(user_file=DEFAULT_USER_FILE):
    """读用户预设列表;文件不存在/损坏返回 []。"""
    if not user_file or not os.path.exists(user_file):
        return []
    try:
        with open(user_file, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict) and d.get("params")]
    except Exception:
        return []
    return []


def write_user_preset(d, user_file=DEFAULT_USER_FILE):
    """把规范化后的预设追加进用户文件;同 id 去重覆盖。返回 True。"""
    d = import_preset_dict(dict(d))  # 再校验一次(调用方未规范化时兜底)
    items = load_user_presets(user_file)
    items = [x for x in items if x.get("id") != d["id"]]
    items.append(d)
    os.makedirs(os.path.dirname(user_file) or ".", exist_ok=True)
    with open(user_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return True