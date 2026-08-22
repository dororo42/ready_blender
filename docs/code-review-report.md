# Ready→Blender 插件代码审查报告(v1.0)

> 日期:2026-08-18 ｜ 对象:`ready_blender/`(manifest 版本 0.1.1)
> 依据:ready2blender-evaluation-report.md v1.0、ready2blender-project-plan.md v1.0
> 方法:全量源码逐文件审查(22 个 .py + manifest + presets,约 4,300 行)+ 本机实测复验(6 个测试套件全跑、93 pattern 解析、fast_ops 等价性与加速比 A/B 复测)
> 结论先行:**总体质量良好,可进入 M1 验收阶段;发现 5 项确定性缺陷(A 类)、12 项改进建议(B 类)、6 项待 Blender 运行时验证项(C 类)、3 项文档口径问题(D 类),无阻断性架构问题。M2 功能存在"库层完成、UI 零接线"的口径偏差,需产品决策。**

---

## 0. 审查范围与实测记录

| 验证项 | 结果 |
|---|---|
| tests/run.py(核心数值 10 项) | 10/10 通过 |
| tests/test_review_fixes.py(历史修复回归 9 项) | 9/9 通过 |
| tests/test_m2_modules.py(CA/网格生成器/3D,13 项) | 13/13 通过 |
| tests/test_formula.py(公式系统 6 项) | 6/6 通过 |
| tests/test_writer.py(vti/vtu 写出往返 2 项) | 2/2 通过 |
| tests/test_vtk_io.py(**93 个真实 pattern 解析**) | **93/93 通过**(81 vti + 12 vtu;formula 67 / inbuilt 3 / kernel 23——与评估报告口径完全一致) |
| fast_ops 与 GrayScottRule 等价性(50 步,atol=1e-5) | 复验通过(docstring 声明"已验证等价"属实,但此前无测试背书,本次人工补验) |
| fast_ops 加速比(256²,同进程 A/B,两次) | 1.91x / 2.46x——readme 声明 1.9-2.3x 成立 |
| FFT SmoothLife(64²,20 步) | 有限值、值域 [0.05, 0.78] 稳定 |
| 基线性能(256² rule.update,本 VM) | 108-244 steps/s(跨进程噪声大;VM 环境,仅量级参考) |

测试环境:Python 3.12 + numpy 2.5.2(本机无 Blender,所有 bpy 依赖路径的运行时行为无法冒烟,列入 C 类)。

---

## 1. 总体评估

### 1.1 与计划书的符合度

| 计划里程碑 | 完成度 | 说明 |
|---|---|---|
| M0 原型验证 | ✅ 完成 | benchmark_m0.py、save_pearson.py、Pearson 图案验证齐全;P0-4 邻接构建实测有数据(avg_k/max_k 落档) |
| M1 MVP | ✅ 基本完成 | mesh 直跑 + 参数面板 + 播放/步进/烘焙(modal 分片可取消)+ 画笔(防御式)+ 密度检测/Remesh 引导 + 5 组预设 + manifest。**缺口:P1-8 的 4.2/4.5 双版本冒烟未做(本机无 Blender);预设的 seed_region/noise_ratio 字段未实现** |
| M2 功能扩展 | ⚠️ **库层完成、UI 层零接线** | FormulaRule / CA 规则 / 网格生成器 / UV 烘焙 / vti/vtu 读取 / 3D 体素 / 录制——core 与 fileio 层实现且测试通过,但 `ui/` 目录对上述模块**零引用**(grep 复核):无"导入 pattern"操作符、无公式编辑面板、无 CA 选择入口、录制器未注册 handler、bake_uv_texture 无调用方 |
| M3 发布准备 | 🔶 骨架 | compute_backend(step 直接 raise NotImplementedError)、fragment 后端同为骨架(计划允许);发布检查清单全部未勾选,manifest maintainer="TBD" |

### 1.2 架构红线核查

| 计划红线 | 实际 | 判定 |
|---|---|---|
| core/backend/io 零 bpy 依赖 | 全部通过(bpy 导入仅在函数内或声明为运行时层文件) | ✅ |
| 依赖方向 ui → controller → core 单向 | **违约 2 处**:scheduler._tick 与 session.on_load_post 反向导入 ui.operators(运行期延迟导入,无循环,但违反计划书"严格单向") | ⚠️ B3 |
| 引擎模块级单例 + load_post 重建 | 实现(session.py),异常场景有降级处理(reset→IDLE) | ✅ |
| Rule 可插拔多变量 | Rule 接口 + FormulaRule(n 化学)+ 3 个 CA 规则 + 3D 规则均按接口接入,扩展性验证达成 | ✅ |
| 净室纪律 | 每文件标注文献来源;参数取自公开图例;无 Ready 代码痕迹;D5 不继承 ×4 标定(拉普拉斯为标准 5 点/graph 定义) | ✅ |
| 双模式交互 | 预览(timers + 0.1s 显示节流)+ 烘焙(modal TIMER 分片、进度条、ESC/按钮取消、重入前复位取消标志) | ✅ |

### 1.3 亮点

1. **93/93 pattern 二进制解析全通过**——appended base64+zlib 解码器按文件观察独立实现,正面命中并解决评估报告最高互操作风险 R9。
2. fast_ops 优化内核数学等价(本次补验属实)+ 实测加速 ~2x,且做了缓冲区别名自毁防护。
3. 画笔 modal 防御式设计:视口外点击自动退出放行、异常自愈退出、状态栏守卫写法。
4. 此前审查修复(空 mesh 守卫、双重 rebuild 卡死、wrap 传参、邻接权重归一化)均有回归测试锁定。
5. 测试为纯 Python 可运行(不依赖 bpy/pytest),CI 友好。

---

## 2. 缺陷清单

### A 类:确定性缺陷(建议修复,均已定位到行)

| # | 位置 | 问题 | 建议 |
|---|---|---|---|
| A1 | tests/test_core.py:28-30 | 使用 `pytest.approx` 但全文件未 `import pytest`;且文件头写"运行:python -m pytest tests/ -q"与实际支持的"纯 Python 运行器"口径矛盾(pytest 收集还会把 test_writer/test_vtk_io 的模块级执行脚本误当用例) | 补 import 并改普通 abs() 断言双轨兼容;统一文档口径为脚本式运行 |
| A2 | ui/panels.py:117 | `template_ID_preview(img, show_buttons=False, open="IMAGE_EDITOR")` 签名误用:`property` 为必填参数(指向 data 上的指针属性名),直接传 Image 对象缺 property,draw 时抛 TypeError → Image Editor 面板无法绘制 | 改用 layout.template_image 或正确的 template_ID 用法(随 C2 一并运行时确认) |
| A3 | presets/presets.json | ①"pearson_spots"与"mitosis"参数完全相同(F=0.0367/k=0.0649),名不副实;②seed_region/noise_ratio 字段被 RD_OT_preset_load 忽略(死数据);③init 噪声比例硬编码 0.03,UI 的 noise_ratio 属性同样未接线 | 核对论文图例区分 spots/mitosis 参数;实现或删除未用字段 |
| A4 | adapters/mesh_adapter.py:198-200 | write_displacement 每次 remove+重建属性,与 write_named_attribute 已修复的"复用不重建"原则冲突 → 每 tick 断开 GN 引用 + 无谓开销 | 改为与 write_named_attribute 相同的复用逻辑 |
| A5 | ui/panels.py:94 | Mesh Health 区块在**每次面板 draw**调用 suggest_remesh(from_mesh+triangulate+calc_area 全量)——50k 面网格鼠标划过面板即卡顿数百 ms | 缓存检测结果(手动刷新按钮 / depsgraph 变更检测 / init 时计算一次) |

### B 类:设计与健壮性改进

| # | 位置 | 问题 | 建议 |
|---|---|---|---|
| B1 | controller/engine.py | 五状态机部分空转:NEEDS_REBUILD 无任何 UI 触发路径(field_kind/target_object 变更不标 rebuild);dirty 热更新机制实际 no-op(params 原地更新已即时生效) | 给 target_object/field_kind 加 update 回调标 rebuild 并在下一 tick 重建;或简化状态机并文档声明现状 |
| B2 | ui/operators.py | 网格拓扑变更无防护:init 后用户编辑/删除 mesh → face_values 长度错位 → 属性静默写脏数据 | init 时记录顶点/面计数,显示写入前校验不匹配则提示重 init |
| B3 | controller/scheduler.py:45、controller/session.py:26 | controller 反向导入 ui.operators,违反计划书单向依赖红线(延迟导入避开了循环) | controller 暴露 display_hook 注册点,ui 侧注入回调 |
| B4 | adapters/mesh_adapter.py | 面积加权平均循环在 write_vertex_color/_face_to_vertex_values/write_displacement 三处复制粘贴;且每次显示更新都 from_mesh+triangulate 重建 bmesh | 提取公共函数;缓存拓扑(面→顶点映射、面积),tick 只写数值 |
| B5 | adapters/mesh_adapter.py:127 | triangulate 后未 `bm.faces.index_update()`,依赖 face_map 的 .index 有错位风险(Blender 文档要求拓扑修改后重算索引) | 映射前调用 index_update() 加固 |
| B6 | core/initial.py:23、core/boundary.py | ParameterSet 与 parameter.ParameterTable 重复实现;boundary.py 三个类零引用(死代码) | 合并删除 |
| B7 | backend/numpy_backend.py:23 | 用类名字符串 `rule.__class__.__name__ == "GrayScottRule"` 判型走快路径,脆弱 | 改 isinstance |
| B8 | tests/test_vtk_io.py:8 | 硬编码本机绝对路径;且 glob 为空时 exit 0(假绿) | 路径参数化(环境变量/参数);空列表显式 fail |
| B9 | 各显示路径 | colormap 每帧按 min/max 自适应归一化,演化过程颜色漂移闪烁 | b 场固定 [0,0.5] 或提供范围锁定 |
| B10 | __init__.py:19 vs blender_manifest.toml | bl_info (0,1,0) 与 manifest 0.1.1 不一致;maintainer="TBD" 待填 | 同步版本号;发布前补 maintainer |
| B11 | scheduler.py BakeScheduler / uv_bake_blender.py Recorder / compute_backend / FragmentRDBackend | BakeScheduler 与 RD_OT_bake modal 双实现(后者才是实际路径);Recorder 与两个 GPU 后端为无调用方骨架 | 删 BakeScheduler(留 modal 版);骨架按计划保留但 readme 标注状态 |
| B12 | controller/engine.py:65-73 | mark_dirty 在"rebuild 且已处于 NEEDS_REBUILD"分支落入 else,dirty_kind 被置 'rebuild',与首分支行为不一致(标志位语义混乱,当前因 B1 无实际触发而未暴露) | 随 B1 一并理顺 |

### C 类:待 Blender 运行时验证(本机无 Blender)

| # | 验证项 | 风险 |
|---|---|---|
| C1 | `object.voxel_remesh` 操作符在 4.2/4.5 是否存在(若不存在,Mesh Health 面板 draw 报错) | 中 |
| C2 | 4.2 LTS 与 4.5 LTS 干净环境安装冒烟(register/unregister/面板/operator 全链路),含 A2 修复验证 | 高(发布前置) |
| C3 | write_vertex_color(POINT 域)、write_named_attribute(FACE 域 face_map 映射)在真实含 ngon 网格上的正确性 | 中 |
| C4 | vtk_writer 输出能否被 Ready 读回(化学场写在 PointData 而 Ready ImageRD 语义倾向 CellData;RD format_version="2" 兼容性) | 中 |
| C5 | 画笔 ray_cast 在修改器/多对象/编辑模式下的行为 | 低 |
| C6 | `blender --command extension validate/build` 通过性 | 发布前置 |

### D 类:文档与口径

| # | 问题 | 建议 |
|---|---|---|
| D1 | readme 将 M2 库层能力(公式系统/CA/网格生成器/vti-vtu IO/3D 体素/UV 烘焙)列为"功能",但 UI 无入口,用户安装后找不到——**口径夸大,本次审查最重要的产品层发现** | 二选一:①readme 如实标注"库层就绪、UI 分批交付";②优先把价值最高的 2 项(vti/vtu 图案导入、UV 烘焙)接入 UI(约 2-4 人日),其余后置 |
| D2 | 性能表未标注测试环境 CPU;本 VM 复测量级一致但绝对值差异大 | 标注环境;声明相对加速比比绝对值更可靠 |
| D3 | 已知限制章节诚实(GPU 骨架、SmoothLife 近似、5.x 未验证)——保持 | 无 |

---

## 3. 优化路线建议(分四批,待用户逐批确认后实施)

1. **第一批(A 类 5 项)**:A1 测试修复 → A2 Image 面板 → A3 预设数据与接线 → A4 置换属性复用 → A5 密度检测缓存。改动小、风险低,均可本地验证。
2. **第二批(B 类精选)**:B1+B12 状态机理顺与 rebuild 触发 → B2 拓扑校验 → B4+B5 适配层重构与索引加固 → B6/B7/B8 清理与判型。改动面较大,伴随回归测试。
3. **第三批(产品口径,需拍板)**:D1 二选一——是否现在把"vti/vtu 导入 + UV 烘焙"接进 UI,还是 readme 降级声明。
4. **第四批(C 类)**:在装有 Blender 4.2/4.5 的机器上执行发布检查清单(C1-C6)。

---

## 附录:实测复验命令(供追溯)

```
py tests\run.py                    # 10/10
py tests\test_review_fixes.py      # 9/9
py tests\test_m2_modules.py        # 13/13
py tests\test_formula.py           # 6/6
py tests\test_writer.py            # 2/2
py tests\test_vtk_io.py            # 93/93
# fast_ops 等价性:50 步 allclose(atol=1e-5) = True
# fast_ops 加速比(256²,同进程 A/B):1.91x / 2.46x
# FFT SmoothLife(64²,20 步):有限,值域 [0.05, 0.78]
```

*本报告由全量源码审查 + 本机实测复验产出;行号引用基于 2026-08-18 工作区版本。*


---

# 附录 v1.1:目标模式修复轮(2026-08-18)

> 依据本报告 A/B/C/D 类缺陷清单与用户目标(预设乱码/Image Editor 显示/摄像机与对象选择/网格预处理/复现示例)执行修复。

## 本报告缺陷处置台账

| 编号 | 原结论 | 本轮处置 | 证据 |
|---|---|---|---|
| A2 | template_ID_preview 签名误用 | ✅ 已修:RD_PT_image 改用 layout.template_image | ui/panels.py |
| A3① | mitosis 与 spots 参数相同,名不副实 | ⚠️ 保持原值,标注"待用户确认后区分"(目标约束:预设数值修改需逐组确认) | presets/presets.py 注释 |
| A3② | seed_region/noise_ratio 字段被忽略(死数据) | 保留在数据层,UI 未接线;列为已知边界 | verification-report.md |
| A5 | Mesh Health 每次 draw 重建 bmesh | ✅ 已修:suggest_remesh_cached 按(对象名+顶点数+阈值)缓存 | adapters/mesh_adapter.py |
| B3 | controller 反向导入 ui | 未改(运行期延迟导入,无循环;列入后续重构) | — |
| D1 | readme 把 M2 库层能力列为"功能"但 UI 零接线 | 部分推进:预设 UI 已接、网格预处理 UI 已接;其余保持"库层完成"口径 | repro-examples.md |

## 新增能力(本轮)

1. **预设嵌入模块** `presets/presets.py`:下拉数据不再经文件读取,消除乱码风险;与 presets.json 逐组同源核对(5/5)。
2. **Image Editor 自动显示**:显示更新时自动把 RD_preview 设为所有打开的 Image Editor 当前图像;无需摄像机(面板已提示)。
3. **默认对象选择**:网格模式未选目标时默认当前活动对象,面板提示规则。
4. **网格预处理**:`core/mesh_quality.py`(顶点/面数、边长极差、狭长占比、面积CV、面密度=面数/包围盒对角线、均匀性与数量双判定)+ `RD_OT_mesh_prep`(只读报告)+ `RD_OT_mesh_triangulate_copy`(非破坏副本)。
5. **复现示例**:docs/repro-examples.md 5 案例(C1 预设/C2 出图/C3 摄像机与对象/C4 预处理/C5 数量不足)。
6. **回归测试**:tests/test_mesh_quality.py(11 项)加入回归台账。

## 回归台账更新(2026-08-18)

core 10/10、formula 6/6、M2 模块 13/13、审查修复 9/9、writer 2/2、93 pattern 93/93、mesh_quality 11/11、预设同源 5/5、语法 43/43、包模式导入通过。
