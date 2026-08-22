# Ready→Blender 评估报告 v1.6(核实 + 三项实施 + N13 修复)

> 日期:2026-08-18 ｜ 对象:上轮报告后的工作区
> 本轮:① 核实 numba 窗口落实情况 ② 实施用户确认项(防1/V2-V6/细分上限) ③ 核实中发现并修复 N13(扩展模式包名 bug)

---

## 第一部分:numba 配置窗口核实(用户告知已落实)

**核实结论:窗口本体完整且质量良好,但发现 1 个扩展模式致命 bug(N13,已修复)。**

| 组件 | 状态 | 详情 |
|---|---|---|
| 偏好窗口 [ui/preferences.py](../ui/preferences.py) | ✅ | 镜像源枚举(官方/清华/阿里)+自定义 URL+use_numba 开关+安装/自检按钮+状态显示("不装也能用,自动回退 numpy"提示) |
| JIT 内核 [backend/numba_backend.py](../backend/numba_backend.py) | ✅ | njit 边循环标量内核,与 core/vertex_rd 数值同源;`NUMBA_AVAILABLE` 探测;无 numba 时 njit 透传装饰器(优雅回退) |
| 算子接线 operators.py:1060-1076 | ✅ | `use_numba` 读场景设置,已装走 JIT、未装自动回退 numpy 路径 |
| 安装算子改良 | ✅ | `sys.executable -m pip` + `--no-warn-script-location`;**装后 import 自检**(v1.4 报告建议的改良点,Pro v6 的盲点已补) |
| V5 顺带核实 | ✅ | `rng_seed`/`vertex_seed_ratio` 已接 settings(可复现),种子读 settings 不再硬编码 |

**数值同源实测**:新增 [tests/test_numba_backend.py](../tests/test_numba_backend.py)——numpy 路径与 numba_backend 50 步 max|dU|=2.4e-07(浮点求和顺序差异级),边界 Dirichlet 保持一致。

**N13(核实中发现,已修复)**:[preferences.py](../ui/preferences.py) `bl_idname = "ready_blender"` 硬编码——**扩展安装时真实包名是 `bl_ext.user_default.ready_blender`**(用户上轮 traceback 路径证实其以扩展模式运行),AddonPreferences 注册必失败且被 `_safe_register` 静默吞掉 → **numba 窗口在扩展模式下不可见**,`context.preferences.addons["ready_blender"]` 也会 KeyError。修复:`_addon_pkg()` 按包前缀动态解析(bl_ext.* → 去掉末段;否则 "ready_blender"),bl_idname 与 addons[...] 键统一使用;面板自检提示的根包导入同步修正。4 种包名形态的解析用例全部通过。

## 第二部分:本轮实施项(用户确认)

| # | 实施 | 详情 |
|---|---|---|
| 防1 启动自检 | ✅ | [__init__.py](../__init__.py) `_self_check()`:register 时包模式验证 7 个关键子模块(core.rule/core.vertex_rd/presets.presets/backend.numba_backend/adapters.mesh_adapter/controller.engine/fileio.vtk_xml)相对导入可达;失败不阻断注册,收集到 `SELF_CHECK_ERRORS` 并 print;[panels.py](../ui/panels.py) 主面板顶部显示"插件安装损坏"警告。此类缺陷(如 v1.5 的 fhn_spiral)从此安装即可见 |
| V2/V3/V4 口径文档 | ✅ | readme 新增"两条求解路径与口径说明"对照表:求解域(面域面积加权 vs 顶点域 1:1)、拉普拉斯(1/度归一化 vs 非归一化 Σ邻居−deg·U)、位移归一化(固定值域 [0,0.5] vs min-max)、迭代方式(timers 播放 vs 一次性阻塞);使用节补 GN 凹凸/顶点凹凸/numba 安装三条 |
| 细分上限 4→7 | ✅ | properties.py:239 `max=7`,描述注明"7 级约 ×16k 面,谨防内存不足" |

## 第三部分:测试复验

**158 项断言全绿,0 失败**:
ext_mode 11(原 7+新增 4 包名解析)｜ numba_backend 3(新)｜ run.py 10｜ vertex_rd 11｜ review_fixes 9｜ formula 6｜ m2_modules 13｜ writer 2｜ vtk_io 93
py_compile 全部改动文件(6 个)通过。

## 第四部分:遗留与建议

| 项 | 状态 |
|---|---|
| C 类 Blender 运行时冒烟 | **优先级上升**:N13 修复后需用户机器重装扩展确认——①偏好在在设置→插件→Ready 出现 numba 窗口 ②"螺旋波"预设正常 ③面板无"安装损坏"警告 ④细分滑块可到 7 ⑤一键顶点凹凸走 numba(装后) |
| compute shader | 用户指示暂缓 ✓(readme 已标注"暂缓") |
| pip 安装阻塞 UI | 安装算子 subprocess.check_call 同步阻塞(numba+llvmlite ~100MB 下载)。可接受的已知限制,记录备查;后续可改后台线程+进度 |
| 遗留小项 | O3 类卫生项已清;v1.3 N12(GN 手动指向已有树被清空)仍为边缘场景备查 |

**总评**:numba 路线按 v1.4 报告 2.3 方案完整落地(窗口+内核+回退+自检改良),V5 顺带完成;N13 是本轮最有价值的发现——它与 fhn_spiral 同属"dev/安装态分叉"家族,但更隐蔽(注册失败被吞,窗口静默消失)。防1 自检上线后,此类问题在安装损坏场景将直接可见。
