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
# 写入插件目录失败时的兜底路径(用户主目录,纯 python 可测)
_FALLBACK_USER_FILE = os.path.join(os.path.expanduser("~"),
                                   ".ready_blender_user_presets.json")
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
    if not user_file:
        user_file = DEFAULT_USER_FILE
    paths = [user_file]
    if user_file == DEFAULT_USER_FILE:
        paths.append(_FALLBACK_USER_FILE)
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8-sig") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict) and d.get("params")]
        except Exception:
            continue
    return []


def write_user_preset(d, user_file=None):
    """把规范化后的预设追加进用户文件;同 id 去重覆盖。

    返回实际写入路径(主路径,主路径只读时为回退路径 ~/.ready_blender_user_presets.json)。
    """
    d = import_preset_dict(dict(d))  # 再校验一次(调用方未规范化时兜底)
    if not user_file:
        user_file = DEFAULT_USER_FILE
    target = user_file
    items = load_user_presets(user_file)
    items = [x for x in items if x.get("id") != d["id"]]
    items.append(d)
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except OSError:
        # 插件目录只读(系统盘安装等):回退用户主目录
        target = _FALLBACK_USER_FILE
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    return target

def import_preset_text(text):
    """从 JSON 字符串导入(剪贴板粘贴用);非法抛 ValueError。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("剪贴板为空")
    try:
        d = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}")
    return import_preset_dict(d)


def import_preset_file(path):
    """从文件导入;兼容 UTF-8(含 BOM)与 GBK(记事本 ANSI 另存);非法抛 ValueError。"""
    raw = None
    with open(path, "rb") as f:
        raw = f.read()
    text = None
    for enc in ("utf-8-sig", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("文件编码无法识别(支持 UTF-8 / GBK)")
    return import_preset_text(text)
