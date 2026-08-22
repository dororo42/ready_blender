# Ready→Blender 优化落实核查报告(v1.2)

> 日期:2026-08-18 ｜ 对象:针对 v1.1 报告(docs/code-review-report-v1.1.md)N1-N7 及批次修复后的工作区
> 方法:逐项源码比对 + 全量测试复跑 + py_compile 语法检查
> 结论先行:**上一轮 2 项 P0、2 项 P1 回归全部正确修复,无新增回归;133 项测试断言全绿;剩余 5 项未落实项中仅 1 项影响功能语义(A3 预设同参数,待拍板),其余为架构打磨项。插件已恢复可注册、可运行状态,质量较 v1.1 显著提升。**

---

## 0. 测试复验记录

| 套件 | 结果 | 备注 |
|---|---|---|
| tests/run.py(core) | 10/10 ✅ | 含修复后的 laplacian peak 断言 |
| tests/test_m2_modules.py | 13/13 ✅ | CA/网格生成器/3D |
| tests/test_formula.py | 6/6 ✅ | 公式系统 |
| tests/test_writer.py | 2/2 ✅ | vti/vtu 写入往返 |
| tests/test_review_fixes.py | **9/9 ✅** | 上轮崩溃的 UnboundLocalError 已消失,"backend 快路径 50 步无 NaN"通过 |
| tests/test_vtk_io.py | **93/93 ✅** | 81 vti + 12 vtu |
| py_compile 全部改动文件 | ✅ | 11 个文件语法全过 |

合计 **133 项断言全绿,0 失败**。

---

## 1. 上一轮问题修复核对

### 1.1 P0/P1 回归(v1.1 新发现)

| # | 状态 | 核查详情 |
|---|---|---|
| N1 | ✅ 已修 | [numpy_backend.py:5-8](../backend/numpy_backend.py) GrayScottRule 导入移至模块顶层(try 包/顶层双模式),isinstance 判断(27 行)正常;实测快路径 50 步无 NaN |
| N2 | ✅ 已修 | [operators.py:489](../ui/operators.py) `_get_preset_items` 定义移至 `RD_OT_preset_load` 类(503 行)之前,前向引用消除;且预设改从 `presets.presets` 模块读取(消除文件读取编码风险),items 回调带 ImportError 兜底 |
| N3 | ✅ 已修 | [test_core.py:33-35](../tests/test_core.py) 断言改 `== -16.0` / `== 4.0`,符号正确,run.py 10/10 通过 |
| N4 | ✅ 已修 | [panels.py:200](../ui/panels.py) 改用 `layout.template_ID(context.space_data, "image")`——IMAGE_EDITOR 的 space_data 即 SpaceImageEditor,标准 API;另加"当前显示的不是 RD_preview"提示与一键切换 |
| N5 | ✅ 已修 | operators.py:592-597 统一 `bpy.context.window_manager.windows` 干净遍历,硬编码 "WinMan" 消失 |

### 1.2 v1.0 原始问题批次状态更新

| # | v1.1 状态 | v1.2 状态 | 核查详情 |
|---|---|---|---|
| A3-① 预设参数 | ❌ | ⏸ 待拍板 | spots 与 mitosis 的 F/k 仍同为 0.0367/0.0649(presets.py:11/29,presets.json 同步),mitosis 条目自注"待用户确认后区分"——按约定保留,合理 |
| A3-② noise_ratio 接线 | ❌ | ⚠️ 部分 | mesh 路径已用 `settings.noise_ratio`(operators.py:124/128);**grid 路径仍硬编码中心方形扰动(80-87 行),未接 noise_ratio** |
| A3-③ seed_region | ❌ | ❌ 未动 | presets 定义了 center_square_0.25/center_disc 但初始化代码未读取,仍为死数据 |
| B1 域变更重建 | ⚠️ 死代码 | ✅ 已修 | `_domain_changed` 挂到 field_kind/target_object/system_enum 三个属性的 update=(properties.py:128/132/140);已初始化时自动重建引擎 |
| B3 controller→ui 反向依赖 | ❌ | ❌ 未修 | scheduler.py:49-51、session.py:26-28 仍运行时导入 ui.operators(惰性导入缓解循环,架构方向未变) |
| B4 适配层去重 | ⚠️ 部分 | ⚠️ 部分 | `_face_to_vertex_values` 已建且 POINT 域使用;但 write_vertex_color(76-98)、write_displacement(184-195)仍是内联复制的加权循环 |
| B12 mark_dirty | ❌ | ✅ 已修 | engine.py:72-73 已处于 NEEDS_REBUILD 时直接 return,不污染 dirty_kind;test_review_fixes 双重 rebuild 用例通过 |
| D1 readme 口径 | ❌ | ✅ 已修 | 功能清单加 ✅/📦 标注,"库层就绪、UI 待接入"如实披露(M2 五项均标 📦) |

### 1.3 v1.1 P2 项

| # | v1.2 状态 | 核查详情 |
|---|---|---|
| N6 缓存键 | ✅ 已修 | mesh_adapter.py:245 缓存键 =(对象名, 顶点数, **面数**, 阈值);边滑动等保持顶点数的编辑由面数兜底(注:同时保持顶点数与面数的重构仍会命中过期缓存,概率低) |
| N7 位移归一化漂移 | ✅ 已修 | write_displacement:205 改固定值域 `clip(vals,0,0.5)/0.5`,消除每帧 min/max 漂移 |
| F13 缓存清理 | ✅ 已修 | `clear_density_cache` 存在,unregister 调用(__init__.py:83-88),并还原自动转换的 Image Editor 区域 |

---

## 2. 本轮新增代码观察(非缺陷,记录备查)

| # | 位置 | 观察 | 风险 |
|---|---|---|---|
| O1 | properties.py:12-41 | 2D 模式自动把一个区域转成 Image Editor(`_ensure_image_editor`),unregister/切回 3D 时还原。实现有守卫,但会改变用户工作区布局(优先转换 PROPERTIES/OUTLINER) | 低;有还原机制,建议 C 类冒烟时确认体验 |
| O2 | properties.py:139 | `field_kind` 默认值 "mesh"——新用户默认 3D 网格模式(需选对象);与 readme 使用说明一致 | 口径一致,无需改 |
| O3 | scheduler.py:36/43 | `import time as _time` 重复出现两次 | 无害;顺手可清 |
| O4 | operators.py:124 | `_sel = rng.random(len(_sel)) < settings.noise_ratio`——用 len(布尔数组) 当面数,长度碰巧一致,写法侥幸 | 无害;若实施 F7 顺手规范 |
| O5 | operators.py:89-97 | mesh 模式未选目标对象时自动回退活动物体,报错信息中文化 | 体验改进,已达标 |

---

## 3. 总体评估

- **回归清零**:v1.1 两项 P0(N1 后端崩溃、N2 注册失败)与两项 P1(N3 断言、N4 面板)全部正确修复,且修复方式干净(无新增防御性补丁堆叠)。
- **测试基线**:133 项断言全绿,含 93/93 真实 pattern 解析与 backend 快路径回归用例;test_review_fixes 从崩溃转为 9/9。
- **状态**:插件恢复"可注册、可运行";架构五层与依赖方向无恶化;本轮新增的自动 Image Editor 切换、参数热更新(_param_changed)、速度换算(_speed_changed)均为正向增强。
- **剩余缺口**(按优先序):
  1. A3-① 预设 spots/mitosis 同参数——**需用户拍板**(方案 a 文献区分 / b 删减 / c 如实标注);
  2. A3-②③ grid 初始条件未接 noise_ratio/seed_region(功能语义残留);
  3. B3 controller→ui 反向依赖(架构打磨);
  4. B4 write_vertex_color/write_displacement 内联循环未收敛到 `_face_to_vertex_values`;
  5. C1-C6 Blender 运行时冒烟(需装有 Blender 的机器,本机不可执行)。

---

## 4. 待确认实施项

| # | 修改 | 方案 | 规模 |
|---|---|---|---|
| F6 | A3-① 预设区分 | 方案 a(推荐):spots 改 F=0.030/k=0.062,mitosis 保持 0.0367/0.0649;或方案 b 删减;或方案 c 标注 | 2 行 + json 同步 |
| F7 | A3-②③ 初始条件接线 | grid init 接 noise_ratio 与 seed_region(center_square_0.25 → s=size//8;center_disc → 圆形掩码);顺手规范 O4 | ~20 行 |
| F9 | B4 收敛 | write_vertex_color/write_displacement 内联循环改调 `_face_to_vertex_values` | ~30 行删减 |
| F11 | B3 解耦 | scheduler/session 改 display_hook 注册回调,消除反向导入 | ~40 行 |
| O3 | 小清理 | scheduler 重复 import;O4 写法规范 | 3 行 |
| C | 运行时冒烟 | 输出 C1-C6 检查清单文档供 Blender 机器执行(含 O1 自动切区体验确认) | 文档 |

*建议:F6/F7 一次做完(同属初始条件语义);F9/F11/O3 为代码卫生,可合并一批;C 类独立。*
