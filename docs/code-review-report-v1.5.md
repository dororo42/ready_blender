# Ready→Blender 评估报告 v1.5(核实 + Bug 修复)

> 日期:2026-08-18 ｜ 对象:上轮报告后的工作区 ｜ 本轮含 **1 项已实施的 Bug 修复**(用户报障)
> 报障现象:加载 FitzHugh-Nagumo 系统的"螺旋波"预设报 `TypeError: enum "fhn_spiral" not found in ('default')`(operators.py:575)

---

## 第一部分:本轮优化核实

### 1.1 v1.3 遗留项 F14-F17 全部落实

| # | 状态 | 核查详情 |
|---|---|---|
| F14(N8 GN 默认模式陷阱) | ✅ 已修 | [operators.py:882](../ui/operators.py) `add_displacement_gn` 直接调 `write_displacement(obj, engine.fields[chem_idx])`,不再依赖 output_mode 分发——任何输出模式下点按钮都会写入 RD_disp |
| F15(N9 预设字段死数据) | ✅ 已修 | preset_load 增加 sr_map 命名映射,seed_region/noise_ratio 随预设同步到 settings(operators.py:590-594) |
| F16(N10 双 bmesh) | ✅ 已修 | write_vertex_color 外层 bmesh 已去除,顶点色经 `_face_to_vertex_values` + `mesh.vertices` 遍历,每帧仅一次 bmesh(mesh_adapter.py:71-81) |
| F17(N11 导入层级) | ✅ 已修 | session.py:18 改 `from .engine import`(正确同包层级) |

### 1.2 新功能盘点

| 项 | 核查详情 |
|---|---|
| PRO 风格预设 7 组 | presets.py:127-135,Karl Sims 经典参数区(珊瑚/斑点/迷宫/虫纹/科幻/电路/机械),seed_region 全部 uniform_sparse——即对比报告批次 B1 落实 |
| 公式系统参数变体 | FORMULA_VARIANTS:FHN 2 组(兴奋波/螺旋波)、Brusselator 3 组、Schnakenberg 2 组、Oregonator 2 组(靶波/螺旋波),共 4 系统 9 变体;`formula_variant` 动态枚举 + 面板已接线 |
| uniform_sparse 种子 | 枚举项(properties.py:225)+ grid 路径(operators.py:95-98,5% 随机点)+ mesh 路径(operators.py:132-134)双接线——v1.4 报告第三部分原理的工程化落地 |
| FormulaRule 系统化 | init_engine_from_settings 按 SYSTEMS 定义分发 builtin/formula 两类规则,公式系统带文献默认 init(base+pulse) |

---

## 第二部分:Bug 修复(本轮唯一实施项)

### 2.1 根因分析

**错误链**:

```
_formula_variant_items 回调(properties.py:115)
  → from .presets import presets   ← 层级错误:ui/ 下无 presets 模块(ui.presets 不存在)
  → ImportError → fallback: from presets import presets
      → dev 工作区:插件根目录在 sys.path → 顶层 presets 可导入 → 侥幸通过(测试全绿的原因)
      → 扩展安装模式:仅 ready_blender 包可导入(父目录在 sys.path),顶层 presets 不存在 → ImportError
  → 外层 except 吞掉异常 → items 只返回 [("default", "文献默认", "")]
→ operators.py:575 赋值 s.formula_variant = "fhn_spiral"
  → Blender 按 items 回调校验 → "fhn_spiral" not in ('default',) → TypeError
```

**两个佐证**:
1. 报错 traceback 路径为 `...\extensions\user_default\ready_blender\...`(扩展安装),而 dev 工作区测试从不复现——**典型的 dev/安装态路径分叉**,fallback 双导入模式掩盖了层级错误;
2. 错误信息 `not found in ('default')` 恰是回调 except 分支的返回值——即回调在扩展模式下必然走进了导入失败分支。

**次生隐患**:即使导入修好,Blender 动态枚举 items 有缓存——刚切换 system_enum 就立即加载预设时,赋值可能仍按旧缓存校验失败(变体下拉在安装态也因此一直只显示"文献默认")。

### 2.2 修复内容(已实施)

| # | 文件 | 修改 |
|---|---|---|
| 修 1 | [ui/properties.py:115](../ui/properties.py) | `from .presets import presets` → `from ..presets import presets`(ui 的同级包是 presets,正确层级;dev fallback 保留) |
| 修 2 | [ui/operators.py:575-580](../ui/operators.py) | 赋值加 TypeError 兜底:失败时直接写底层标识符 `s["formula_variant"] = ...`(EnumProperty 底层存储即标识符字符串,绕过缓存校验;值本身有效,重绘后正常显示) |

**同类问题排查**:全项目单点相对导入扫描,仅此一处层级错误;另两处(`core/formula.py:225` 的 `.ops`、`controller/session.py:18` 的 `.engine`)均为正确同包导入。

### 2.3 修复验证

新增 [tests/test_ext_mode_import.py](../tests/test_ext_mode_import.py):模拟扩展安装环境(注册 `ready_blender` 为包、**不**把插件根目录放入 sys.path)——

| 验证 | 结果 |
|---|---|
| 扩展模式下顶层 presets 不可导入(复现旧代码死因) | ✅ |
| `from ..presets import presets` 在扩展模式下成功 | ✅ |
| FHN 变体含 fhn_spiral/fhn_excite | ✅ |
| Brusselator/Schnakenberg/Oregonator 变体完整 | ✅ |
| items 回调将包含 fhn_spiral(赋值不再 TypeError) | ✅ |

全量测试复验:**151 项断言全绿**(run.py 10 + vertex_rd 11 + review_fixes 9 + formula 6 + m2_modules 13 + writer 2 + vtk_io 93 + ext_mode 7),0 失败;py_compile 通过。

### 2.4 布防建议(未实施,待确认)

本次暴露的系统性风险:**`try: 相对导入 / except: 顶层导入` 双路径 fallback 使层级错误在 dev 态不可见,只在安装态爆发**。可选布防:

| 方案 | 内容 | 成本 |
|---|---|---|
| 防 1(推荐) | 新增启动自检:`__init__.py` register 时静默验证 `from .presets import presets`、`from .core import rule` 等关键包路径,失败时弹 report 提示"插件安装损坏" | ~15 行 |
| 防 2 | 测试套件加一条"包模式导入"用例(即 test_ext_mode_import.py 已做的模拟,纳入常规回归) | 已有,纳入 run_all 即可 |
| 防 3 | 统一导入规范:禁用顶层 fallback,全部走 `..` 相对导入(需要 dev 脚本以包模式跑) | 改动面大,收益一般 |

---

## 第三部分:总体评估与遗留

- **质量趋势**:v1.3 的 F14-F17 与对比报告 B1(风格预设)全部落实,公式系统(4 系统 9 变体)是本轮最大增量,净室口径保持(文献典型参数,未照搬 Ready 文件数值)。
- **本次 Bug 性质**:新功能(参数变体)的导入层级错误,属 dev/安装态分叉类缺陷——**恰好也解释了为何本地 144 项测试从未捕获**;新增的扩展模式模拟测试补上了这一空档。
- **修复状态**:已实施并验证(用户机器重新安装扩展后即可生效:Blender 偏好设置 → 扩展 → 刷新/重装 ready_blender)。
- **遗留项**(未实施):
  1. 防 1/防 3 布防方案(2.4 节,待拍板);
  2. v1.4 报告 V2-V6 观察项(顶点凹凸 rng 播种/seed_ratio 接属性、一次性流程与播放路径双语义、拉普拉斯归一化口径差异文档化);
  3. C 类 Blender 运行时冒烟(GN 凹凸实际效果、FHN 螺旋波在 2D 网格的实际演化——本机无 Blender,需用户机器执行);
  4. 加速路线(numba 配置窗口 + 2D compute shader 试点,v1.4 报告 2.3 节)。

**建议下一步**:用户机器重装扩展验证"螺旋波"预设加载;若通过,C 类冒烟清单(含 FHN 螺旋波目视验证)可一并执行。
