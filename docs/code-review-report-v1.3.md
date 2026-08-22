# Ready→Blender 优化落实核查报告(v1.3)

> 日期:2026-08-18 ｜ 对象:针对 v1.2 报告(docs/code-review-report-v1.2.md)F6/F7/F9/F11/O3/O4 及新增 GN 置换功能后的工作区
> 方法:逐项源码比对 + 全量测试复跑 + py_compile + GN 节点连线索引逐一比对(用户提供的几何节点索引规格)
> 结论先行:**v1.2 待办全部主体落实且无 P0 回归,133 项测试断言全绿;新增"一键凹凸修改器(GN)"的 7 条节点连线与您提供的索引规格完全一致;但发现 2 项 P1(N8 GN 默认模式陷阱、N9 预设字段未同步)+ 2 项 P2 卫生问题。**

---

## 0. 测试复验记录

| 套件 | 结果 |
|---|---|
| tests/run.py(core) | 10/10 ✅ |
| tests/test_m2_modules.py | 13/13 ✅ |
| tests/test_formula.py | 6/6 ✅ |
| tests/test_writer.py | 2/2 ✅ |
| tests/test_review_fixes.py | 9/9 ✅ |
| tests/test_vtk_io.py | 93/93 ✅ |
| py_compile(10 个改动文件) | ✅ |

合计 **133 项断言全绿,0 失败**。

---

## 1. v1.2 待办落实核对

| # | 状态 | 核查详情 |
|---|---|---|
| F6 预设区分 | ✅ 已修 | spots 改 **F=0.030 / k=0.062**(孤子斑点区,mrob 口径),mitosis 保持 0.0367/0.0649;presets.py 与 presets.json 双同步,source 注明"用户已确认方案 a" |
| F7-① grid 初始条件 | ✅ 已修 | [operators.py:82-95](../ui/operators.py) 支持 seed_region 三模式:center_square(s=size//8 方形)/ center_disc(半径 s×1.4 圆盘)/ global(稀疏,密度=noise_ratio);属性+面板均已接线 |
| F7-② 预设字段同步 | ❌ 未完 | preset_load 仍只同步 Du/Dv/F/k/dt 五参数(operators.py:544-548),预设的 seed_region/noise_ratio 未应用到 settings;且预设值 `center_square_0.25` 与枚举 `center_square` 命名不一致,需映射(→N9) |
| F9 适配层收敛 | ✅ 已修 | write_vertex_color:76 与 write_displacement:167 均改调 `_face_to_vertex_values`,内联加权循环消除(→但引入 N10 残留) |
| F11 controller→ui 解耦 | ✅ 已修 | engine 增加 display_hook/rebuild_hook(由 __init__.py:74-76 注册);scheduler._tick:47-51 经 hook 调显示;session.on_load_post:26-31 经 hook 调重建;**controller 层零 ui 导入**,架构方向修正完成 |
| O3 重复 import | ✅ 已修 | scheduler.py 仅保留一处 `import time` |
| O4 侥幸写法 | ✅ 已修 | fallback 用 `len(engine.fields[0])`(operators.py:138) |

---

## 2. 新增功能审查:一键凹凸修改器(GN)

**RD_OT_add_displacement_gn**(operators.py:796-890,已注册,面板入口 panels.py:130)

### 2.1 节点连线与您提供索引的比对

| 您提供的索引 | 代码实现 | 一致性 |
|---|---|---|
| 组输入[0](Geometry) → 设置位置[0](Geometry) | operators.py:884 | ✅ |
| 已命名属性[0](RD_disp) → 乘法[0](A) | operators.py:885(attr.data_type="FLOAT", Name="RD_disp") | ✅ |
| 组输入[1](强度) → 乘法[1](B) | operators.py:886(接口 socket 顺序:Geometry→强度,861 行在 Geometry 之后创建) | ✅ |
| 法线[0] → 缩放[0](Vector) | operators.py:887(VectorMath SCALE) | ✅ |
| 乘法[0] → 缩放[1](Scale) | operators.py:888 | ✅ |
| 缩放[0] → 设置位置[3](Offset) | operators.py:889 | ✅ |
| 设置位置[0] → 组输出[0](Geometry) | operators.py:890 | ✅ |

**七条连线全部一致**,纯索引访问(不受 socket 命名/版本差异影响)的写法正确;接口显式创建 Geometry IN/OUT + 强度(min=0, default=0.1)符合 Blender 4.x 要求;幂等复用(已存在 Ready_SetPosition 则跳过)。

### 2.2 GN 功能新发现问题

| # | 级别 | 问题 | 详情 |
|---|---|---|---|
| **N8** | **P1** | 默认输出模式陷阱 | execute 调 `RD_OT_update_display.run(context)` 写属性,但该函数按**当前 output_mode** 分发——output_mode 默认值是 `vertex_color`(properties.py:184),用户未切到"置换属性"就点"一键添加凹凸修改器"时 **RD_disp 根本不会被写入**,GN 读命名属性得全 0:无凹凸、无报错、无提示。新用户大概率踩中 |
| N12 | P2 | 破坏性边缘场景 | 若用户手动把 Ready_Displace 修改器指向自己已有的节点树,_build_tree 的 `ng.nodes.clear()`(841 行)会清空用户的树。概率低,记录备查 |

---

## 3. 其他新发现问题

| # | 级别 | 位置 | 问题 |
|---|---|---|---|
| **N9** | **P1** | operators.py:544-548 | preset_load 不同步预设的 seed_region/noise_ratio 到 settings → 预设五组里这两个字段仍是死数据(F7 残留);且需做值映射(center_square_0.25→center_square) |
| N10 | P2 | mesh_adapter.py:73-75 | F9 收敛不彻底:write_vertex_color 外层仍构建 bmesh+三角化(仅 83-85 行遍历顶点用),而 `_face_to_vertex_values` 内部又建一次 → **每帧两次 bmesh 构建**,较收敛前反而多一次;可改用 `mesh.vertices` 遍历彻底去掉外层 bmesh |
| N11 | P2 | session.py:18 | `from ..engine import` 相对导入层级错误(controller 包内应为 `.engine` 一个点),当前靠 fallback `from controller.engine import` 兜底生效;功能正确但包模式下首次 ImportError 被吞,写法应修正 |
| O6 | 观察 | operators.py:486-501 | 画笔退出语义变更:右键=撤销退出、ESC=保留退出、回车=保留确认(v1.2 为 ESC/右键均撤销)。更符合 Blender 惯例,属正向改进;readme 未记载,C 类冒烟时确认体验 |

---

## 4. 总体评估

- **回归面**:零 P0/P1 回归;上轮全部 6 项待办(F6/F7①/F9/F11/O3/O4)主体落实,落实质量整体良好。
- **架构**:F11 完成后 controller→ui 反向依赖彻底消除,五层依赖方向首次完全干净;注册/注销升级为幂等(_safe_register),抗"上次启用中途崩溃残留"。
- **功能面**:新增 GN 一键凹凸是与 M1"输出→GN 消费"闭环的关键一步,节点树搭建正确(索引比对 7/7);但 N8 使其在默认设置下静默失效,是当前**最高优先级待修项**。
- **测试**:133 项断言全绿;GN 路径无单测覆盖(需 bpy,归 C 类运行时验证)。

**剩余缺口优先序**:N8(GN 陷阱)> N9(预设字段死数据)> N10(双 bmesh)> N11(导入层级)> N12/O6(记录备查)。

---

## 5. 待确认实施项

| # | 修改 | 方案 | 规模 |
|---|---|---|---|
| **F14** | N8 修复 | add_displacement_gn.execute 不依赖 output_mode:直接调 `write_displacement(obj, data)` 写一次 RD_disp(取 engine.fields[active_chemical]);engine 未初始化时先 init | ~10 行 |
| **F15** | N9 修复 | preset_load 同步 seed_region/noise_ratio 到 settings(值映射:center_square_0.25→center_square、center_disc→center_disc) | ~12 行 |
| F16 | N10 修复 | write_vertex_color 去掉外层 bmesh,顶点色写入改遍历 `mesh.vertices`(顶点数与三角化无关,安全) | ~10 行 |
| F17 | N11 修复 | session.py `from ..engine import` → `from .engine import` | 1 行 |
| F18 | O6 | readme 使用节补画笔退出语义一行 | 1 行 |
| C 类 | 运行时冒烟 | Blender 机器执行:GN 修改器实际凹凸效果、默认模式点击、画笔退出语义、C1-C6 原清单 | 文档 |

*建议 F14+F15 一批(同属预设/GN 语义闭环),F16/F17/F18 顺手批。*
