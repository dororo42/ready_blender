# ready_blender 项目评估报告(2026-09-06)

> 评估对象:`dororo42/ready_blender` 工作区(含 517 行未提交改动);
> 方法:全库通读、`git diff` 逐行审阅、全量测试执行(本机 numpy 环境)。

## 一、项目定位

Blender 4.2/4.5 LTS 扩展,在网格体与规则网格上做反应扩散(RD)与元胞自动机模拟。
**净室实现**(不含 GPL Ready 源码翻译),GPL-3.0-or-later,面向 extensions.blender.org 合规上架。
生态整合思路清晰:VTI/VTU 兼容 Ready 93 个 pattern、移植 Karl Sims RD 网页选参工具、
移植 linusmossberg/reaction-diffusion(MIT)预设组,三条外部生态互相打通。

## 二、架构评价:整体优秀

分层干净、依赖单向:`core(算法) → backend(内核) → controller(状态机) → ui / adapters / fileio`。

- **engine.py 五状态机**(IDLE/RUNNING/PAUSED/NEEDS_REBUILD/STEPPING)设计克制:
  模块级单例刻意不挂 Scene 以避开 undo 副作用(engine.py:17);hot/rebuild 双级脏标记
  区分滑块热更与拓扑重建(engine.py:69);画笔 undo 用场快照栈(深度 20,engine.py:104)。
- **双求解路径口径差异有文档**(readme「两条求解路径」表):面域归一化拉普拉斯(稳定优先)
  vs 顶点域非归一化拉普拉斯(min-max 拉满对比度),这是合理的工程取舍并写清楚了。
- **防呆成体系**:`__init__.py` 启动自检(SELF_CHECK_ERRORS 面板提示)、
  `_safe_register` 幂等注册防崩溃残留、F11 回调解耦 controller→ui 反向依赖。
- **blender_manifest.toml** 与 bl_info 双轨齐备,build 排除 tests/benchmark,平台声明完整。

## 三、测试:全绿(本机实测)

`tests/run.py`(核心 10 例)+ 18 个独立测试脚本逐个运行,全部通过,包括:
公式系统 6、M2 模块 13、网格质量 11、顶点域 11、系统 8、回归修复 9、
Oil-Water、3D 生长管道、Numba 后端边界、pattern_map、preset_io、
**VTK IO 对 93 个真实 Ready pattern 的回归**(ImageData 81 / UnstructuredGrid 12,规则分布 formula 67 / inbuilt 3 / kernel 23)。

⚠ 测试形态不统一:模块级脚本(部分在 import 时 `sys.exit`,pytest 全量收集会
INTERNALERROR)、函数式(新 test_preset_io.py)、自研 run.py 三种并存。建议逐步统一为
pytest 兼容函数式(新改动已经在这么做了)。

## 四、未提交改动(工作树)的主题与问题

### 主题 A:Karl Sims 扩展参数接入 3D 网格(core/rule.py + core/vertex_rd.py)
- `orientation_*`:各向异性边权重 `w'=w·(1+α(2cos²θ−1))`,行归一化保持谱有界,实现严谨;
- `flow_*`:半拉格朗日最近邻平流(顶点粒度近似,常数场恒等);
- `GrayScottRule._mesh_ext` 类级缓存(key 含 `id(verts)`)。

### 主题 B:linusmossberg 预设移植 + 预设 IO 加固
- 新增 20 组 `lm_*` 预设(MIT,含 anisotropy/noise 等 extensions 键,换算 Du=0.256·DS);
- `import_preset_file/text`:UTF-8(±BOM)/GBK 兼容、剪贴板导入、只读目录回退
  `~/.ready_blender_user_presets.json`;`write_user_preset` 改为返回实际写入路径。

### 发现的问题

| 级别 | 问题 | 位置 |
|---|---|---|
| **P1 必修** | 新操作符 `RD_OT_paste_preset_json`(粘贴导入)只加了类(ui/operators.py:1758)与面板按钮(ui/panels.py:189),**没有加进 `__init__.py` 的 register/unregister 类列表** → 面板按钮点击必报“未定义操作符” | `__init__.py:88-102 / 158-173` |
| P2 性能 | `init_engine_from_settings` 用 Python 列表推导逐顶点取 `v.co` 建 (N,3) 坐标数组,大网格初始化会秒级卡顿;应改 `vertices.foreach_get("co", arr).reshape(N,3)` | `ui/operators.py:159-161` |
| P2 兼容疑点 | 3D 取向场以 **Y 轴为上**(linear=竖直 Y,vertex_rd.py:104),而 Blender 世界是 Z-up;与网页工具的 y-up 约定对齐是刻意还是疏漏,需在 Blender 内实测确认 | `core/vertex_rd.py:95-124` |
| P2 | `write_user_preset` 文档串仍写“返回 True”,实际已改返回路径 | `fileio/preset_io.py` |
| P2 | `advect_mesh`/`_mesh_ext` 内层 `except: pass` 静默吞错,远端排障时无日志线索 | `core/rule.py:67-72` |
| P3 | `_mesh_ext_cache` key 用 `id(verts)` 有理论上的 id 复用碰撞风险 | `core/rule.py:25` |
| P3 卫生 | 两条历史提交信息本身已乱码(提交对象中即 `?` 字节);根目录草稿 `_scratch_check.py`/`benchmark_m0.py`/`save_pearson.py` 未清理;`web/simplehttpserver.exe`(6 MB)已被追踪而 `.gitignore` 的 `*.exe` 不溯及;`build_rdtool_lm.py` 硬编码本机绝对路径 | git log / 根目录 / web |

## 五、Blender 4.5 兼容性

- 声明 4.2+ 扩展形态,API 用法(面域命名属性、color_attributes、timers、PointerProperty、
  幂等注册)在 4.5 无已知阻断点;
- `ui/previews.py` 本次改动新增了 `bpy.utils.previews` 缺失降级(退化为纯文本枚举),
  属防御性正确;
- 真机 4.5 验证尚未进行——本报告发出时,远程 4.5 主机的 MCP 调试链路正在搭建
  (见 `_tools/rd_debug/README.md`),这是下一步的自然验证场。

## 六、结论

净室流程、文档密度、测试纪律明显高于同类个人插件项目;架构分层与状态机是教科书式的。
当前工作树的 A/B 两个主题方向正确,合入前修掉 P1 注册遗漏与 P2 顶点循环即可。

> **2026-09-06 修复记录**:P1 注册遗漏(RD_OT_paste_preset_json 补入 register/unregister)、
> P2 顶点循环改 `foreach_get`、`write_user_preset` 文档串、平流静默吞错改为留痕打印
> 已全部修复并经本地回归 + 远端 Blender 4.5.12 真机验证;P2 Y-up/Z-up 约定保留待
> 远端视觉实测;P3 项维持记录不改。
