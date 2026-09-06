# -*- coding: utf-8 -*-
"""预设数据嵌入模块(修复下拉乱码:消除文件读取链路,数据与 presets.json 同源)。"""
from __future__ import annotations

# 与 presets/presets.json 同源的预设数据(数值取自 Pearson 1993 公开论文图例)
PRESETS = [
    {
        "id": "pearson_spots",
        "name": "Pearson 1993 · 斑点 (Spots)",
        "rule": "Gray-Scott",
        "params": {"Du": 0.16, "Dv": 0.08, "F": 0.030, "k": 0.062, "dt": 1.0},
        "seed_region": "center_square_0.25",
        "noise_ratio": 1.0,
        "source": "Pearson 1993 图例孤子斑点区参数(mrob 分类口径,用户已确认方案 a)",
    },
    {
        "id": "coral_growth",
        "name": "珊瑚生长 (Coral Growth)",
        "rule": "Gray-Scott",
        "params": {"Du": 0.16, "Dv": 0.08, "F": 0.0545, "k": 0.062, "dt": 1.0},
        "seed_region": "center_square_0.25",
        "noise_ratio": 1.0,
        "source": "Pearson 1993 图例珊瑚生长参数区;Karl Sims 教程亦称指纹 (Fingerprint)",
    },
    {
        "id": "mitosis",
        "name": "有丝分裂 (Mitosis)",
        "rule": "Gray-Scott",
        "params": {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0},
        "seed_region": "center_disc",
        "noise_ratio": 0.3,
        "source": "Karl Sims 教程经典 mitosis 参数(用户已确认方案 a:spots 已区分)",
    },
    {
        "id": "worms",
        "name": "蠕虫 (Worms)",
        "rule": "Gray-Scott",
        "params": {"Du": 0.16, "Dv": 0.08, "F": 0.058, "k": 0.065, "dt": 1.0},
        "seed_region": "center_square_0.25",
        "noise_ratio": 1.0,
        "source": "Pearson 1993 图例蠕虫参数区(公开论文图例参数)",
    },
    {
        "id": "chaos",
        "name": "混沌纹理 (Chaotic)",
        "rule": "Gray-Scott",
        "params": {"Du": 0.16, "Dv": 0.08, "F": 0.026, "k": 0.051, "dt": 1.0},
        "seed_region": "center_square_0.25",
        "noise_ratio": 1.0,
        "source": "Pearson 1993 图例混沌参数区(公开论文图例参数)",
    },
]


_USER_CACHE = None  # W1:用户预设惰性缓存(导入后 refresh_user_presets 刷新)


def _load_user():
    global _USER_CACHE
    if _USER_CACHE is None:
        try:
            from ..fileio.preset_io import load_user_presets
        except ImportError:
            try:
                from fileio.preset_io import load_user_presets
            except ImportError:
                load_user_presets = lambda *a, **k: []
        _USER_CACHE = load_user_presets()
    return _USER_CACHE


def refresh_user_presets():
    """W1:导入/删除用户预设后调用,使下拉即时更新。"""
    global _USER_CACHE
    _USER_CACHE = None
    return _load_user()


def get_preset(id_or_name):
    """按 id 或名称取预设,找不到返回 None。"""
    for p in PRESETS + PRO_PRESETS:
        if p["id"] == id_or_name or p["name"] == id_or_name:
            return p
    for p in _load_user():
        if p["id"] == id_or_name or p["name"] == id_or_name:
            return p
    return None


def get_items():
    """EnumProperty items:(id, name, description)。用户预设带 [导入] 前缀。"""
    items = [(p["id"], p["name"], p.get("source", ""))
             for p in PRESETS + PRO_PRESETS]
    for p in _load_user():
        items.append((p["id"], "[导入] " + p.get("name", p["id"]),
                      p.get("source", "RD 网页导出预设")))
    return items


# ── 内置反应扩散系统(公式来自公开文献,净室口径) ────────────────────
SYSTEMS = [
    {
        "id": "gray_scott",
        "name": "Gray-Scott",
        "chemicals": ["a", "b"],
        "kind": "builtin",
        "source": "Gray & Scott 1983-84; Pearson 1993",
    },
    {
        "id": "fitzhugh_nagumo",
        "name": "FitzHugh-Nagumo",
        "chemicals": ["u", "v"],
        "kind": "formula",
        "formula": ("delta_u = D_u * laplacian_u + u - u^3/3 - v;\n"
                   "delta_v = D_v * laplacian_v + eps*(u + a0 - b0*v);"),
        "params": {"D_u": 1.0, "D_v": 0.0, "eps": 0.05, "a0": 0.7, "b0": 0.8, "dt": 0.1},
        "init": {"base": {"u": -1.2, "v": -0.6}, "pulse_chem": "u", "pulse_value": 2.0},
        "source": "FitzHugh 1961 (Biophys. J.); Nagumo et al. 1962",
    },
    {
        "id": "brusselator",
        "name": "Brusselator",
        "chemicals": ["u", "v"],
        "kind": "formula",
        "formula": ("delta_u = D_u * laplacian_u + A - (B+1)*u + u*u*v;\n"
                   "delta_v = D_v * laplacian_v + B*u - u*u*v;"),
        "params": {"D_u": 1.0, "D_v": 10.0, "A": 1.0, "B": 3.0, "dt": 0.02},
        "init": {"base": {"u": 1.0, "v": 3.0}, "pulse_chem": "v", "pulse_value": 0.1},
        "source": "Prigogine & Lefever 1968 (J. Chem. Phys.)",
    },
    {
        "id": "schnakenberg",
        "name": "Turing (Schnakenberg)",
        "chemicals": ["u", "v"],
        "kind": "formula",
        "formula": ("delta_u = D_u * laplacian_u + a - u + u*u*v;\n"
                   "delta_v = D_v * laplacian_v + b - u*u*v;"),
        "params": {"D_u": 1.0, "D_v": 40.0, "a": 0.1, "b": 0.9, "dt": 0.004},
        "init": {"base": {"u": 1.0, "v": 0.9}, "pulse_chem": "u", "pulse_value": 0.1},
        "source": "Schnakenberg 1979 (J. Theor. Biol.)",
    },
    {
        "id": "oregonator",
        "name": "Oregonator (BZ)",
        "chemicals": ["u", "v"],
        "kind": "formula",
        "formula": ("delta_u = D_u * laplacian_u + (1/tau)*(u*(1-u) - f*v*(u-q)/(u+q));\n"
                   "delta_v = u - v;"),
        "params": {"D_u": 0.5, "tau": 0.05, "f": 0.8, "q": 0.002, "dt": 0.002},
        "init": {"base": {"u": 0.5, "v": 0.5}, "pulse_chem": "u", "pulse_value": 0.1},
        "source": "Field & Noyes 1974 (J. Chem. Phys.) 二变量简化",
    },
    {
        "id": "oil_water",
        "name": "Oil-Water 相分离",
        "chemicals": ["a", "b"],
        "kind": "oil_water",
        "params": {"repulsion": 0.7, "dt": 0.05},
        "init": {"mode": "white_noise"},
        "source": "Agmon, Gates, Churavy & Beer 2014 (ALife 14)",
    },
]




# ── 风格化预设(外部插件同款 (f,k) 组合,Karl Sims 经典分类图;不改动现有五组) ──
PRO_PRESETS = [
    {"id": "pro_coral", "name": "珊瑚 / 网纹", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.0545, "k": 0.062, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 1.0, "source": "Karl Sims 经典珊瑚区"},
    {"id": "pro_spots", "name": "斑点 / 豹纹", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.025, "k": 0.06, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 1.0, "source": "Karl Sims 经典斑点区"},
    {"id": "pro_maze", "name": "迷宫 / 条纹", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.029, "k": 0.057, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 1.0, "source": "Karl Sims 经典迷宫区"},
    {"id": "pro_worms", "name": "虫纹 / 拉伸", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.078, "k": 0.061, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 1.0, "source": "Karl Sims 经典虫纹区"},
    {"id": "pro_scifi", "name": "科幻 / 装甲", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.046, "k": 0.065, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 1.0, "source": "Karl Sims 经典装甲区"},
    {"id": "pro_circuit", "name": "电路 / 芯片", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.039, "k": 0.058, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 1.0, "source": "Karl Sims 经典电路区"},
    {"id": "pro_mechanical", "name": "机械 / 齿轮", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.05, "k": 0.064, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 1.0, "source": "Karl Sims 经典机械区"},
    {"id": "lm_default", "name": "默认 (Default)", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.042, "k": 0.06, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.8, "environment_noise_scale": 250, "diffusion_scale_variation": 0.375, "feed_variation": 0.001, "kill_variation": 0.001}},
    {"id": "lm_dunes_zebra", "name": "沙漠斑马 (Dunes/Zebra)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.05, "k": 0.061, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.9, "environment_noise_scale": 700, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_fingerprints", "name": "指纹 (Fingerprints)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.037, "k": 0.06, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.8, "environment_noise_scale": 250, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_spots_worms", "name": "斑点与虫纹 (Spots and Worms)", "params": {"Du": 0.128, "Dv": 0.064, "F": 0.034, "k": 0.0618, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.5, "environment_noise_scale": 250, "diffusion_scale_variation": 0.375, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_cell_division", "name": "细胞分裂 (Cell Division)", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.03, "k": 0.063, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.5, "environment_noise_scale": 250, "diffusion_scale_variation": 0.375, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_buoys", "name": "浮标 (Buoys)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.025, "k": 0.06, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.9, "environment_noise_scale": 250, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_currents", "name": "洋流 (Currents)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.08, "k": 0.06, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.9, "environment_noise_scale": 500, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_oil_spill", "name": "油污 (Oil Spill)", "params": {"Du": 0.128, "Dv": 0.064, "F": 0.0475, "k": 0.06, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.1, "environment_noise_scale": 250, "diffusion_scale_variation": 0.375, "feed_variation": 0.01, "kill_variation": 0.01}},
    {"id": "lm_trypophobia", "name": "密集孔洞 (Trypophobia)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.039, "k": 0.0581, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.9, "environment_noise_scale": 250, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_travellers", "name": "旅者 (Travellers)", "params": {"Du": 0.128, "Dv": 0.064, "F": 0.014, "k": 0.054, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.8, "environment_noise_scale": 250, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_ocean", "name": "海洋 (Ocean)", "params": {"Du": 0.16, "Dv": 0.08, "F": 0.014, "k": 0.04, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.1, "environment_noise_scale": 250, "diffusion_scale_variation": 0.5, "feed_variation": 0.001, "kill_variation": 0.001}},
    {"id": "lm_differential_line", "name": "微分线 (Differential Line)", "params": {"Du": 0.128, "Dv": 0.064, "F": 0.072, "k": 0.062, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.3, "environment_noise_scale": 250, "diffusion_scale_variation": 0.375, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_voronoi", "name": "沃罗诺伊 (Voronoi)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.098, "k": 0.0555, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.5, "environment_noise_scale": 250, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_worms", "name": "虫纹 (Worms)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.058, "k": 0.065, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.5, "environment_noise_scale": 250, "diffusion_scale_variation": 0.125, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_worm_mazes", "name": "虫洞迷宫 (Worm Mazes)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.046, "k": 0.063, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.7, "environment_noise_scale": 250, "diffusion_scale_variation": 0.125, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_maze", "name": "迷宫 (Maze)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.03, "k": 0.0565, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.5, "environment_noise_scale": 250, "diffusion_scale_variation": 0.0625, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_unstable_maze", "name": "不稳定迷宫 (Unstable Maze)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.026, "k": 0.055, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.5, "environment_noise_scale": 250, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_ripping", "name": "撕裂 (Ripping)", "params": {"Du": 0.096, "Dv": 0.048, "F": 0.034, "k": 0.056, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.9, "environment_noise_scale": 250, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_waves", "name": "波浪 (Waves)", "params": {"Du": 0.064, "Dv": 0.032, "F": 0.013, "k": 0.045, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.9, "environment_noise_scale": 250, "diffusion_scale_variation": 0.0, "feed_variation": 0.0, "kill_variation": 0.0}},
    {"id": "lm_tensor_field", "name": "张量场可视化 (Tensor Field)", "params": {"Du": 0.096, "Dv": 0.048, "F": 0.03, "k": 0.063, "dt": 1.0}, "seed_region": "uniform_sparse", "noise_ratio": 0.05, "source": "linusmossberg/reaction-diffusion (MIT) 预设,换算 Du=0.256·DS", "extensions": {"anisotropy": 0.9, "environment_noise_scale": 250, "diffusion_scale_variation": 0.25, "feed_variation": 0.0, "kill_variation": 0.0}},
]





FORMULA_VARIANTS = {
    "fitzhugh_nagumo": [
        {"id": "fhn_excite", "name": "兴奋波(标准)", "params": {"D_u": 1.0, "D_v": 0.0, "eps": 0.05, "a0": 0.7, "b0": 0.8, "dt": 0.1}},
        {"id": "fhn_spiral", "name": "螺旋波", "params": {"D_u": 0.8, "D_v": 0.02, "eps": 0.08, "a0": 0.75, "b0": 0.8, "dt": 0.1}},
    ],
    "brusselator": [
        {"id": "bru_spots", "name": "图灵斑点", "params": {"D_u": 1.0, "D_v": 10.0, "A": 1.0, "B": 3.0, "dt": 0.02}},
        {"id": "bru_stripes", "name": "图灵条纹", "params": {"D_u": 1.0, "D_v": 12.0, "A": 1.0, "B": 3.2, "dt": 0.02}},
        {"id": "bru_osc", "name": "均匀振荡", "params": {"D_u": 0.0, "D_v": 0.0, "A": 1.0, "B": 3.0, "dt": 0.01}},
    ],
    "schnakenberg": [
        {"id": "sch_spots", "name": "图灵斑点", "params": {"D_u": 1.0, "D_v": 40.0, "a": 0.1, "b": 0.9, "dt": 0.004}},
        {"id": "sch_stripes", "name": "图灵条纹", "params": {"D_u": 1.0, "D_v": 30.0, "a": 0.2, "b": 0.8, "dt": 0.004}},
    ],
    "oregonator": [
        {"id": "ore_target", "name": "靶波", "params": {"D_u": 0.5, "tau": 0.05, "f": 0.8, "q": 0.002, "dt": 0.002}},
        {"id": "ore_spiral", "name": "螺旋波", "params": {"D_u": 1.0, "tau": 0.1, "f": 1.4, "q": 0.002, "dt": 0.002}},
    ],
}


def get_variants(system_id):
    return FORMULA_VARIANTS.get(system_id, [])


def get_variant(system_id, variant_id):
    for v in get_variants(system_id):
        if v["id"] == variant_id:
            return v
    return None

def get_system(sid):
    for s in SYSTEMS:
        if s["id"] == sid:
            return s
    return None
