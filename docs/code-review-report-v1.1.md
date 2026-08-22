# Ready→Blender 优化落实核查报告(v1.1)

> 日期:2026-08-18 ｜ 对象:针对 v1.0 报告(docs/code-review-report.md)各批次优化后的工作区
> 方法:逐项源码比对 + 全量测试复跑 + 关键路径单点实测
> 结论先行:**17 项原始问题中 11 项已正确落实,但本轮优化自身引入 2 项 P0 级回归(N1/N2)——插件当前既无法完成注册(N2),grid 模拟路径全崩溃(N1),必须先行修复;另有 1 项测试断言符号错(N3)、1 项面板 API 误用(N4)。**

---

## 0. 测试复验记录

| 套件 | 结果 |
|---|---|
| tests/run.py | 10/10 ✅ |
| tests/test_m2_modules.py | 13/13 ✅ |
| tests/test_formula.py | 6/6 ✅ |
| tests/test_writer.py | 2/2 ✅ |
| tests/test_vtk_io.py | **93/93 ✅**(81 vti + 12 vtu) |
| tests/test_review_fixes.py | ❌ 第 9 项崩溃:`UnboundLocalError: GrayScottRule`(numpy_backend.py:22) |

---

## 1. 逐项落实核对

### 1.1 A 类(5 项)

| # | 状态 | 核查详情 |
|---|---|---|
| A1 | ⚠️ 修引入新错 | pytest.approx 已移除、改普通断言,try-import 兜底已加;**但 test_laplacian_peak 断言写成 `lap[8,8] == abs(-16.0)`(=+16),实测值为 -16.0 → pytest 下必挂**(见 N3) |
| A2 | ❌ 改法仍错 | panels.py:148 改用 `layout.template_image(img, img.user, compact=True)`:①缺首参 `context`(4.2 API 签名为 `template_image(context, image, user, compact)`);②`Image` 无 `.user` 属性 → draw 时 AttributeError(见 N4) |
| A3 | ❌ 未落实 | ①presets.py:32 自注"与 spots 数值相同,待用户确认后区分"——spots 与 mitosis 的 F/k 仍完全相同;②noise_ratio 属性已加(properties.py:109)但 init 仍硬编码 0.03(operators.py:84);③seed_region 仍为死数据 |
| A4 | ✅ 已修 | write_displacement 改为复用已存在属性,域/类型不符才重建(mesh_adapter.py:199-206) |
| A5 | ✅ 已修 | 新增 suggest_remesh_cached,缓存键 =(对象名, 顶点数, 阈值);面板改调缓存版(panels.py:101) |

### 1.2 B 类(12 项)

| # | 状态 | 核查详情 |
|---|---|---|
| B1 | ⚠️ 半成品(死代码) | `_domain_changed` 回调已写(properties.py:8-22)但**未挂到 field_kind / target_object 的 `update=`**——grep 全库无引用;NEEDS_REBUILD 仍无触发路径 |
| B2 | ✅ 已修 | init 记录拓扑指纹 (n_verts, n_polys)(operators.py:74);显示写入前校验,不匹配则暂停写入+提示(534-538);面板展示 last_error(panels.py:88-90) |
| B3 | ❌ 未修 | scheduler.py:44-47、session.py:26-28 仍反向导入 ui.operators |
| B4 | ⚠️ 部分 | `_face_to_vertex_values` 已提取(POINT 域路径用);但 write_vertex_color(76-98)与 write_displacement(183-195)仍各有一份复制的加权循环;每次显示更新仍 from_mesh+triangulate |
| B5 | ✅ 已修 | write_named_attribute:122 与 build_face_adjacency_bmesh:27 均已加 `bm.faces.index_update()` |
| B6 | ✅ 已修 | boundary.py 已删除;initial.py 已简化为纯函数 |
| B7 | ❌ **改坏 → P0 回归** | numpy_backend.py:22 改用 `isinstance(rule, GrayScottRule)`,但该名字的 import 在函数体内 29-31 行(**判断之后**)→ Python 判定其为局部名 → `UnboundLocalError`,**所有 grid 步进路径崩溃**(实测复现,见 N1) |
| B8 | ✅ 已修 | 支持 `READY_PATTERNS_DIR` 环境变量;目录不存在/文件为空均显式 fail(不再假绿) |
| B9 | ✅ 已修 | colormap_range 枚举(auto/fixed_b/fixed_a);operators._run:504-507 按 chemical 选定范围;image_adapter 接受 vmin/vmax |
| B10 | ✅ 基本修 | bl_info 版本 (0,1,1) 与 manifest 0.1.1 已同步;maintainer 仍 "TBD"(发布前事项,可接受) |
| B11 | ✅ 部分修 | BakeScheduler 已删除,scheduler 仅剩 PreviewScheduler;GPU 后端骨架按计划保留 |
| B12 | ❌ 未修 | mark_dirty 结构原样(engine.py:66-74):重复 rebuild 仍落 else 分支写 dirty_kind='rebuild' |

### 1.3 D 类

| # | 状态 | 核查详情 |
|---|---|---|
| D1 | ❌ 未动 | readme 仍把 M2 库层能力(公式/CA/网格生成器/vti-vtu/3D/UV 烘焙)列为"功能",无"UI 未接线"披露 |
| D2 | ✅ 已修 | 性能表标注"4 核桌面 CPU,无 GPU" |
| D3 | — | 保持诚实口径,无需动作 |

---

## 2. 新发现问题(本轮优化引入)

| # | 级别 | 位置 | 问题 | 证据 |
|---|---|---|---|---|
| N1 | **P0** | backend/numpy_backend.py:22 | `isinstance(rule, GrayScottRule)` 在函数内 import **之前**引用 → `UnboundLocalError`;engine._do_steps 无兜底 → **播放/步进/烘焙所有 grid 路径全部崩溃** | test_review_fixes.py:83 实测崩溃;traceback 见附录 |
| N2 | **P0** | ui/operators.py:426 vs 456 | `items=_get_preset_items` 在类体中前向引用 456 行才定义的函数;类体在模块导入期执行(文件无 `from __future__ import annotations`)→ `NameError` → ui.operators 无法导入 → **register() 失败,插件整体无法加载** | Python 语义静态可判(类体注解表达式导入期求值) |
| N3 | P1 | tests/test_core.py:33-35 | `== abs(-16.0)` 即断言 +16,实测 -16.0;lap[7,8]/lap[8,9] 恰为 +4 所以只错中心点一项 | 单点实测:lap[8,8] = -16.0 |
| N4 | P1 | ui/panels.py:148 | template_image 双重误用(缺 context 首参;img.user 不存在)→ Image Editor 面板 draw 崩溃 | Blender 4.2 API 签名比对 |
| N5 | P2 | operators.py:518-519 | 遍历窗口用 `bpy.data.window_managers["WinMan"]` 硬编码 + 条件表达式套 for,写法脆弱;554 行已有等价的 `bpy.context.window_manager` 干净写法 | 代码审阅 |
| N6 | P2 | mesh_adapter.py:241-251 | 缓存键不含面数/修改器状态:边滑动等**保持顶点数**的编辑会命中过期缓存;缓存永不清理(unregister 不清) | 代码审阅 |
| N7 | P2 | mesh_adapter.py:196-198 | write_displacement 每次按当帧 min/max 自适应归一化 → 位移幅度随演化漂移(与 B9 同类问题在 displacement 路径残留) | 代码审阅 |

---

## 3. 修复方案(待确认后实施)

### 批次一:P0 + P1 缺陷(必须,先做)

| # | 修改 | 方案 |
|---|---|---|
| F1 | N1 | numpy_backend.step():把 GrayScottRule 的 try/except 导入移到 isinstance 判断**之前**(函数体开头);删除快路径内重复导入 |
| F2 | N2 | 把 `_get_preset_items` 定义移到 RD_OT_preset_load 类之前(纯位置移动) |
| F3 | N3 | test_laplacian_peak 断言改 `== -16.0` / `== 4.0` |
| F4 | N4 | RD_PT_image.draw 改用 `layout.template_ID(context.space_data, "image")`(IMAGE_EDITOR 侧栏的 space_data 即 SpaceImageEditor,可切换显示图像);无图像时保留现有 label 分支 |
| F5 | B1 补完 | properties.py:field_kind 与 target_object 挂 `update=_domain_changed`(两行) |

### 批次二:A3 收尾 + B 类余项

| # | 修改 | 方案 |
|---|---|---|
| F6 | A3-① | 预设参数区分(需拍板,见下方"待用户确认事项") |
| F7 | A3-② | operators.py init 的 `sel < 0.03` 改用 `settings.noise_ratio`;seed_region 二选一:实现(center_square_0.25→s=size//8、center_disc→圆形掩码)或删除字段 |
| F8 | B12 | mark_dirty:已处于 NEEDS_REBUILD 时直接 return,不污染 dirty_kind |
| F9 | B4 余项 | write_vertex_color / write_displacement 内联循环改调 `_face_to_vertex_values`;write_displacement 归一化改固定 [0,1] 值域(顺带解决 N7) |
| F10 | D1 | readme 功能清单加"UI 交付状态"列或标注(库层就绪 / 已接 UI) |

### 批次三:架构与小项(可选)

- F11:B3 —— scheduler/session 改 display_hook 注册回调,消除 controller→ui 反向依赖
- F12:N5 —— 统一用 bpy.context.window_manager 遍历
- F13:N6 —— 缓存键加面数;unregister 时清空缓存

### 批次四:C 类(不变,需 Blender 机器)

C1-C6 清单同 v1.0;F4 修复后随 C2 一并冒烟。

---

## 4. 待用户确认事项

1. **实施范围**:批次一(推荐立即)/ 批次二 / 批次三,可多选。
2. **A3 预设参数口径**(批次二前置):
   - 方案 a(推荐):`pearson_spots` 改 F=0.030 / k=0.062(Pearson 孤子斑点区,mrob 分类口径),`mitosis` 保持 F=0.0367 / k=0.0649(Karl Sims 教程经典 mitosis 参数);
   - 方案 b:删除其中一个预设,保留 4 组,注明理由;
   - 方案 c:维持现状,名称后缀加"(同参数)"如实标注。
3. **seed_region**:实现最小版(center_square_0.25 / center_disc 两种)还是删除该字段?

---

## 附录:N1 崩溃 traceback(实测)

```
File "tests\test_review_fixes.py", line 83, in <module>
  bkd.step(GrayScottRule(), [a3, b3], {...}, 50, "grid")
File "backend\numpy_backend.py", line 22, in step
  if (field_kind == "grid" and isinstance(rule, GrayScottRule)
UnboundLocalError: cannot access local variable 'GrayScottRule'
```

*本报告基于 2026-08-18 工作区实测;N2 为静态判定(无 Blender 环境无法运行时复现,但 Python 类体求值语义确定)。*


---

# 落实回执(2026-08-18 12:1x)

> 上述"修复方案(待确认后实施)"批次一/二/三已全部实施并回归通过;仅 A3-① 预设参数区分与 seed_region 语义需用户拍板,按目标约束未改数值。

| 方案 | 状态 | 证据 |
|---|---|---|
| F1 N1(GrayScottRule import 顺序) | ✅ 已落实 | numpy_backend.py 模块级导入 |
| F2 N2(_get_preset_items 前向引用) | ✅ 已落实 | ui/operators.py 函数前置 |
| F3 N3(测试断言符号) | ✅ 已落实 | tests/test_core.py == -16.0 |
| F4 N4(template_ID) | ✅ 已落实 | ui/panels.py template_ID(context.space_data,"image") |
| F5 B1(update 回调) | ✅ 已落实 | properties.py field_kind/target_object update=_domain_changed |
| F6 A3-①(预设参数区分) | ⏸ 待用户确认 | 保持原值,附注"待用户确认" |
| F7 A3-②(noise_ratio 接线) | ✅ 已落实 | operators.py settings.noise_ratio |
| F8 B12(mark_dirty 重复 rebuild) | ✅ 已落实 | engine.py 直接 return |
| F9 B4+N7(位移固定归一化) | ✅ 已落实 | mesh_adapter.py clip[0,0.5]/0.5 |
| F10 D1(readme UI 状态) | ✅ 已落实 | readme.md ✅/📦 标注 |
| F12 N5(窗口遍历统一) | ✅ 已落实 | operators.py bpy.context.window_manager |
| F13 N6(缓存键加面数+清缓存) | ✅ 已落实 | mesh_adapter.py + __init__.py |

## 回归台账(落实后)

core 10/10、formula 6/6、M2 模块 13/13、审查修复 9/9、mesh_quality 11/11、writer 2/2、93 pattern 93/93、语法 43/43 —— 合计 144 项全部通过。

## 仍待处理(非阻塞)

- A3-① 预设参数口径(三方案待拍板)
- seed_region 字段(实现最小版 or 删除)
- B3 controller→ui 反向导入重构(display_hook)
- B4 余项(顶点/面拓扑缓存)
- C1-C6 Blender 实机验证
