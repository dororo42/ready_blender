# Karl Sims RD 扩展选项与 Pattern Map 借鉴评估报告(实施交接版)

> 版本:v5(2026-08-22,W2/W3 决定不执行;核实其他团队已实施的 1a/1b/1c/1d 与 W1 部分;修复各向异性内核缺陷并验证 Orientation/Flow 参数见 §九)
> 状态:**阶段 1(1a-1d)已实施并通过回归;W1 已实施并收尾;W2/W3 不执行;阶段 3a(Orientation)/3b(Flow) 已实施并通过回归(含内核缺陷修复,见 §九);阶段 2(Style Map)未实施**
> 上一版:v4(2026-08-22,实施状态核实);v3(2026-08-20,网页本地化方案);v2(2026-08-20,实施交接版);v1(2026-08-19,纯评估)

---

## 〇、需求与学习来源

| 来源 | 内容 | 提取要点 |
|---|---|---|
| [Reaction-Diffusion Tutorial](https://www.karlsims.com/rd.html)(访问于 2026-08-19) | Gray-Scott 教程:方程、参数、mitosis 机理、四个扩展选项、(k,F) 参数地图原理 | ① 四选项定义(见 §1.1);② 其内核口径:拉普拉斯 = 3×3 卷积(中心 −1,邻边 0.2,对角 0.05),典型值 DA=1.0, DB=0.5, f=0.055, k=0.062, Δt=1.0;③ 地图:x 轴 k∈[0.045, 0.07],y 轴 F∈[0.01, 0.1],逐参数点微型模拟;④ 扭曲版:月牙形活跃区带展开为矩形,作点击选参 UI;⑤ mitosis 视频 (f=.0367, k=.0649)、coral 视频 (f=.0545, k=.062) 与现有预设一致 |
| [RD Tool](https://www.karlsims.com/rdtool.html)(访问于 2026-08-19) | 交互式 JS 网页应用 | 页面为前端应用,源码 JS 不可直接读取;从页面控件清单提取:Vary Pattern(=Style Map)、Flow 7 种(Radial/Rotate/Swirl/Bubble/Ring/Vortex/Vertical)、Orientation 5 种(Linear/Radial/Circles/Swirl/Bubble)、Scale 4 种(Scale/Radial/Random/Ring)、Color map/Emboss、pattern 点击读参("Select Pattern k=0.06264 f=0.06100") |
| 用户需求(2026-08-20) | **RD_Tool 网页本地化**:本地页面直接选取想要的效果,页面提供导出参数方式(CSV / JSON),方便在 Blender 中直接调取 | 新增"阶段 W"方案(见 §4W):本地网页工具 + 参数导出 + Blender 导入/回传。要求与既有方案(阶段 1a-3b)相匹配、不冲突 |
| 本仓库代码勘察(2026-08-20) | 实施接入点核对 | 见 §2 现状;**修正 v1 两处**:grid 2D 仅 fast_ops + rule.py 两条内核路径(numba 无 2D grid 内核);Flow 为 7 种非 6 种 |

**净室声明**:Karl Sims 网站的地图图片与 rdtool 代码均有版权,**不可下载/反编译/复刻使用**。本方案所有地图/缩略图一律用本插件自身求解内核渲染(网页版用 JS 重写同一数学),公式为公开数学构造。

---

## 一、技术解读

### 1.1 四个扩展选项的本质

**四个选项都不是 (F,k) 预设,而是求解器能力扩展**——需要把标量参数升级为逐单元格的空间参数场。统一架构:**"空间场 → 参数调制"**,一套参数场基建可驱动全部四项。

| 选项 | 技术本质 | rdtool 变体 |
|---|---|---|
| Orientation | 各向异性扩散:拉普拉斯 x/y 轴向权重不同 | Linear/Radial/Circles/Swirl/Bubble(仅均一 Linear 属阶段 3,其余为空间变体,暂缓) |
| Style Map | F/k 随空间变化:标量 → 2D 参数场 | Vary Pattern |
| Flow | 平流:半拉格朗日回溯 `u(x) ← u(x − v·dt)` | Radial/Rotate/Swirl/Bubble/Ring/Vortex/Vertical 共 7 种 |
| Scale | 图案波长:D 与反应速率的相对比例 | Scale(均一,阶段 1);Radial/Random/Ring 为空间变体,暂缓 |

### 1.2 Pattern Map 原理

x 轴 k∈[0.045, 0.07]、y 轴 F∈[0.01, 0.1],每个采样点跑一次微型 GS 模拟,整个参数空间可视化为一幅"图案地图":部分区域退化为纯 A(白)/纯 B(黑),月牙形区带产生斑点/条纹/蠕虫等复杂行为。用户在图上点击 → 直接得到 (k,F),比滑杆试错直观得多。扭曲版(可选打磨)把月牙区带展开为矩形提高可点面积;**初版用原始矩形即可,不必扭曲**。

### 1.3 RD_Tool 网页本地化的本质

**不是新求解能力,而是新的"参数探索与交付"界面**:把 rdtool 的浏览器交互体验(实时动画预览 + 地图点选 + 扩展选项)在本地复刻为一个**自包含 HTML 页面**,并以 **CSV/JSON 导出**作为与 Blender 的参数传递通道。它与插件内 UI(阶段 1b 缩略图 / 1c 弹窗)是**互补关系**:

| 界面 | 定位 | 优势 | 局限 |
|---|---|---|---|
| 1b 缩略图枚举 | 插件内·预设快速识别 | 零离开 Blender | 只有预设,不能自由探索 |
| 1c 点击取参弹窗 | 插件内·地图快速选参 | 不出 Blender,即点即用 | 无实时动画、无扩展选项预览 |
| **W 网页工具** | **插件外·完整探索工作台** | 实时动画、滑杆微调、扩展选项、导出存档 | 需切换到浏览器;参数需经文件/回传进入 Blender |

---

## 二、现状与差距(实施接入点勘察)

### 2.1 求解器路径(v1 修正:grid 2D 只有两处内核)

| 路径 | 文件 | 内核函数 | 与本方案关系 |
|---|---|---|---|
| grid 2D 优化路径(实际运行) | `core/fast_ops.py` | `laplacian_5_fast`(L11)、`gray_scott_step_opt`(L31) | **Style Map / Orientation 必改** |
| grid 2D 参考路径 | `core/rule.py` | `GrayScottRule.update`(L35) | **同步必改**(数值一致性基准) |
| mesh 顶点域 | `core/vertex_rd.py` + `backend/numba_backend.py` `_rd_step_numba`(L29) | 图拉普拉斯 | 不涉及(本方案均为 grid 专用) |
| 3D 体素/grow3d | `core/field3d.py`、`adapters/volume_adapter.py` + `_gs3d_kernel` | 7 点内核 | 不涉及 |

> **重要**:`backend/numpy_backend.py` 的 `step()`(L24)对 grid GS 走 fast_ops 分派(L27-47),F/k 从 `params` 字典原样透传——**Style Map 的 F/k 场经 params 字典传入即可直达内核,后端无需改动**。

### 2.2 UI/参数装配接入点

| 接入点 | 位置 | 说明 |
|---|---|---|
| 参数热更新 | `ui/properties.py` `_param_changed`(L98-117) | 直接写 `eng.params`,Scale 在此乘 s² |
| 参数属性 | `ui/properties.py` L181-184(`param_Du/Dv/F/k/dt`) | 新属性加在同区域 |
| 预设枚举 | `ui/operators.py` `_get_preset_items`(L702-724)、`RD_OT_preset_load`(L730-773) | 缩略图枚举改 5 元组(icon_value);**每次调用动态取 items → 用户预设导入后即现,零刷新障碍** |
| 面板分步 | `ui/panels.py` ③参数/④初始条件区,`_L(zh,en)` 双语 | 新 UI 按 grid+GS 条件显隐(参照 oil_water ④ 区先例) |
| 图像编辑器复用 | `ui/properties.py` `_ensure_image_editor`(L58) | 点击取参弹窗复用此模式显示地图 |
| 预览基建 | 无(`bpy.utils.previews` 未使用) | 需新建 `ui/previews.py` |

### 2.3 数值口径对照(关键!实施者必读)

| 项 | Karl Sims | 本项目 | 换算 |
|---|---|---|---|
| 拉普拉斯 | 3×3 卷积:中心 −1,邻边 0.2,对角 0.05(正权和=1) | 5 点:中心 −4,邻边 1(正权和=4) | 他的 D ≈ 我们的 D×4(核归一化差 4 倍) |
| 典型 D | DA=1.0, DB=0.5 | Du=0.16, Dv=0.08 | 1.0≈0.25(核换算后同数量级,略高) |
| (F,k) | f=.0367/k=.0649;f=.0545/k=.062 | mitosis/coral 预设同值 | **F/k 跨内核直接通用**(已验证:现有预设即来自该教程) |
| 稳定性 | — | 显式欧拉 5 点:λ∈[−8,0],需 **dt·Du ≤ 0.25** | 默认 0.16×1.0=0.16 ✓;Scale 放大 D 时是硬约束(见 §4.1d) |

**跨语言一致性契约(W 阶段新增)**:网页 JS 内核必须实现与 `fast_ops` 相同的数学——**5 点拉普拉斯、默认 Du=0.16/Dv=0.08/dt=1.0、相同的浓度裁剪、地图格子统一 wrap=True**。这是"网页所见 = Blender 所得"的保证。浮点实现细节(JS double vs numpy float32)允许图案级一致而非逐位一致。

### 2.4 可复用的既有资产(W 阶段勘察)

| 资产 | 位置 | 复用方式 |
|---|---|---|
| 文件导入操作符先例 | `ui/operators.py` `RD_OT_import_pattern`(L300:`filepath: StringProperty(subtype="FILE_PATH")` + L313 read_file) | W1 的 JSON 预设导入操作符直接参照此模式 |
| 插件注册/注销挂点 | 根 `__init__.py` `register()`(L64)/`unregister()`(L114) | W2 本地 HTTP 服务的启停挂这里 |
| 预设合并点 | `presets/presets.py` `get_items()`/`get_preset()`(L55-65,遍历 `PRESETS + PRO_PRESETS`) | 用户预设列表 `USER_PRESETS` 并入遍历序列即可 |
| 预设文件 schema | `presets/presets.json` | 网页导出 JSON 直接采用同 schema(见 §4W.4) |

### 2.5 测试红线

- 全量回归须过(当前含 93 vtk 断言在内的既有测试集);
- 运行方式:`py tests\run.py` 或逐文件 `py tests\test_xxx.py`;**禁止 pytest 直接收集 `tests/`**(双轨设计会 INTERNALERROR——既有教训);
- 每个新特性 = 新增独立测试文件 + fast_ops/rule.py 数值一致性断言(参照 test_grow3d 先例)。

---

## 三、实施阶段总览

| 阶段 | 内容 | 新文件 | 改动文件 | 预估代码量 | 风险 |
|---|---|---|---|---|---|
| 1a | Pattern Map 渲染器(纯 numpy) | `presets/pattern_map.py` | 无 | ~150 行 | ✅ **已实施**(2026-08-22 核实,见 §8.1) |
| 1b | 预设缩略图枚举 | `ui/previews.py` | `ui/operators.py`、`ui/__init__.py` | ~120 行 | ✅ **已实施** |
| 1c | 点击取参弹窗(模态操作符) | 无(并入 operators) | `ui/operators.py`、`ui/panels.py`、`ui/properties.py` | ~200 行 | ✅ **已实施** |
| 1d | Scale 滑杆 | 无 | `ui/properties.py`、`ui/operators.py`(init_engine)、`ui/panels.py` | ~60 行 | ✅ **已实施**(含子步保护) |
| **W1** | **网页本地化·静态版**(模拟+地图+滑杆+导出 CSV/JSON+Blender 导入) | `web/rdtool.html`(自包含单文件)、`fileio/preset_io.py` | `ui/operators.py`(导入操作符)、`presets/presets.py`(用户预设合并)、`ui/panels.py`(入口按钮) | ~650 行 | ✅ **已完成**(2026-08-22 收尾,见 §8.3) |
| **W2** | **网页本地化·回传版**(本地 HTTP 服务,网页一键"送回 Blender"直写属性) | `web/server.py` | 根 `__init__.py`(生命周期)、`web/rdtool.html`(发送按钮) | ~150 行 | ❌ **不执行**(2026-08-22 用户决定) |
| **W3**(可选) | 网页扩展选项预览(Vary Pattern/Orientation/Flow/Scale 的 JS 版) | 并入 `web/rdtool.html` | — | 每项 ~80-120 行 JS | ❌ **不执行**(2026-08-22 用户决定) |
| 2 | Style Map 参数场 | `core/param_field.py` | `core/fast_ops.py`、`core/rule.py`、UI 三件 | ~300 行 | 未实施 |
| 3a | Orientation 均一版(含空间模式内核) | `core/ops.py`、`core/fast_ops.py`、`core/rule.py`、UI 三件 | ~160 行 | ✅ **已实施并通过回归**(2026-08-22,内核缺陷修复见 §九) |
| 3b | Flow 平流 | `core/flow_field.py`、`core/ops.py`、`controller/engine.py`、UI 三件 | ~230 行 | ✅ **已实施并通过回归**(2026-08-22,见 §九) |
| 暂缓 | 空间变体(Scale Radial/Swirl、Orientation Radial 等) | — | — | — | 依赖阶段 2 参数场基建,性价比最低 |

**实施顺序(v5 修订)**:1a → 1b → 1c → 1d(**✅ 已完成**)→ W1(**✅ 已完成收尾**,2026-08-22)→ 3a → 3b(**✅ 已完成**,2026-08-22,含各向异性内核缺陷修复)→ 2(**未实施,Style Map 仍待办**)。**W2/W3 从计划中移除**。

---

## 四、分阶段实施步骤

### 阶段 1a:Pattern Map 渲染器(纯 numpy,无 bpy)

**新文件 `presets/pattern_map.py`**:

```python
def render_pattern_map(cols=24, rows=18, cell=24, steps=400, seed=42,
                       k_range=(0.045, 0.07), f_range=(0.01, 0.1),
                       Du=0.16, Dv=0.08, dt=1.0) -> np.ndarray:
    """渲染 (k,F) 参数地图。返回 (rows, cols) 灰度图(uint8),
    每像素 = 该 (k,F) 处微型 GS 模拟的 b 场均值。
    内核:本插件 5 点拉普拉斯(fast_ops 口径),保证与实际输出一致。
    x 轴(列)= k, y 轴(行)= F。地图格子统一 wrap=True(无边框伪影,
    且与 W 阶段网页地图口径一致)。"""

def render_pattern_thumbnail(F, k, size=24, steps=300, seed=42,
                             Du=0.16, Dv=0.08, dt=1.0) -> np.ndarray:
    """单个 (F,k) 的图案缩略图(用于预设枚举),中心种子初始化。"""
```

要点:
- 每格微型模拟:cell×cell 网格(建议 24),中心 4×4 种子 b=1,跑 steps 步(建议 300-500,可调),输出 `b.mean()` 或 `b` 下采样均值 → 灰度;纯 A 区≈0(白),纯 B 区≈1(黑),活跃区呈现中间纹理;
- 性能与缓存:全图 24×18=432 次微型模拟,单次 ~毫秒级(numpy 小数组),总耗时秒级——**结果缓存为 npy 到插件 `presets/` 目录**(文件名含参数指纹),二次加载即时;
- 测试 `tests/test_pattern_map.py`:① 输出形状/值域 [0,255];② 已知参数点断言——mitosis (0.0367,0.0649) 与 chaos (0.026,0.051) 格子灰度差异 > 阈值;③ 确定性同 seed 双跑一致;④ 缓存命中路径。

### 阶段 1b:预设缩略图枚举

**新文件 `ui/previews.py`**(bpy 胶水层):

```python
import bpy.utils.previews
_pc = None  # preview collection

def register():        # 在插件 register() 中调用
    global _pc; _pc = bpy.utils.previews.new()

def unregister():      # 在插件 unregister() 中调用
    global _pc; bpy.utils.previews.remove(_pc); _pc = None

def preset_icon(preset_id, thumb_array) -> int:
    """ndarray → 临时 PNG → _pc.load() → 返回 icon_id。
    PNG 写入:借 bpy.image 或最小 zlib+struct 编码器(~30 行,无 PIL 依赖)。
    缓存键:preset_id + 参数指纹,重复调用不重复生成。"""
```

**改动 `ui/operators.py` `_get_preset_items`(L702-724)**:返回值从 3 元组改 5 元组 `(id, name, desc, icon_value, 0)`——Blender EnumProperty 标准用法,icon_value 来自 `preset_icon()`。

**改动 `ui/__init__.py`(插件注册入口)**:register/unregister 挂 `ui.previews` 生命周期。

验收:预设下拉每项左侧出现实时渲染的图案缩略图;unregister 后无残留句柄(Blender 关闭无警告)。

### 阶段 1c:点击取参弹窗(模态操作符)

**改动 `ui/operators.py` 新增 `RD_OT_pattern_map_pick`**:

```
invoke():
  1. arr = render_pattern_map()(带缓存)
  2. arr → bpy.data.images.new("RD_PatternMap", W, H) + pixels(RGB,行序=底到顶)
  3. 复用 _ensure_image_editor 模式(ui/properties.py L58)显示地图
  4. context.window_manager.modal_handler_add(self)
  5. 在 IMAGE_EDITOR 区域挂 gpu draw_handler(十字准线 + blf 读数)

modal(event):
  - mousemove: event.mouse_region_x/y → region.view2d.region_to_view()
    → (u,v)∈[0,1] → k = k_min+u·Δk, F = f_min+v·ΔF(注意图像 v 轴翻转)
    → blf 实时显示 "k=%.5f F=%.5f"(模仿 rdtool "Select Pattern k=… f=…")
  - LEFTMOUSE: 写 s.param_F/param_k(_param_changed 自动热更新引擎)→ 收尾
  - ESC/RIGHTMOUSE: 取消 → 收尾(移除 draw_handler)
```

要点与坑:
- **像素行序**:Blender 图像 buffer 第 0 行在底部,UV v=0 也在底部——两者一致,但 numpy 数组第 0 行在顶部,写入前需 `[::-1]` 翻转;
- 缩放/平移后鼠标坐标必须经 `region.view2d.region_to_view` 换算(勿直接除以宽高);
- draw_handler 记得 `store()`,操作符收尾与插件卸载双路径移除;
- **改动 `ui/panels.py`**:③ 参数区加"从图案地图选择 (k,F)"按钮(仅 grid+GS 显示)。

测试(无 bpy 层):坐标映射纯函数抽出(uv→(k,F) 反算往返一致)单测;模态交互在 Blender 内人工验收。

### 阶段 1d:Scale 滑杆(含稳定性子步保护)

**数学**:图案波长 λ ∝ √(D/反应速率)。保 (F,k) 图案类型不变的前提下缩放:**Du/Dv 同乘 s²**。
- s<1(更小图案):D 变小,更稳定,零成本;
- s>1(更大图案):D 变大,**受显式欧拉稳定域 dt·Du ≤ 0.25 硬约束**——默认 Du=0.16 时 s>1.25 即越界。

**实施**:
1. `ui/properties.py` 新属性:
   ```python
   pattern_scale: FloatProperty(name="图案缩放", default=1.0, min=0.25, max=2.5,
                                update=_param_changed)  # max=2.5:Du=0.16·6.25=1.0,子步 5 次封顶
   ```
2. `_param_changed`(L98-117)与 `init_engine_from_settings`(operators.py)中,装配 params 时:
   ```python
   s = settings.pattern_scale
   Du_eff = settings.param_Du * s * s
   Dv_eff = settings.param_Dv * s * s
   n_sub = max(1, ceil(Du_eff * dt / 0.20))       # 安全系数 0.8
   params = {"Du": Du_eff, "Dv": Dv_eff, "dt": dt / n_sub, ...}
   # 并把 n_sub 透传给运行循环:每 tick 实际步数 = tick_steps × n_sub
   ```
3. `ui/panels.py` ③ 区滑杆(仅 grid+GS;提示"放大>1.25 时自动子步,耗时按比例增加")。

**已否决的替代方案**(记录理由):F/k 除以 s² 同样能改波长,但会移动 (F,k) 在参数空间的位置,mitosis 等预设会漂出自己的活跃区带,图案类型失真——不采用。

测试:① s=1 → 逐位等于现行输出(零回归断言);② s=0.5(无子步)2000 步无 NaN;③ s=2.5(子步激活)无 NaN 且图案特征尺度 > s=1(自相关长度比较);④ n_sub 计算函数单测。

---

## 4W. 阶段 W:RD_Tool 网页本地化(新增需求)

### W0. 方案评估:三种交付形态对比

| 形态 | 原理 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| **A. 静态单文件 HTML**(W1) | 页面随插件分发,浏览器 `file://` 直接打开;JS 本地跑 GS 模拟;导出走**文件下载**(JSON/CSV);Blender 端用**导入操作符**读取 | 零服务器、零端口、完全离线;无线程安全问题;实现最简 | 参数传递是"下载→导入"两步,不是"一键直达" | **先行实施** |
| **B. 本地 HTTP 服务**(W2) | 插件 register 时在守护线程起 `http.server`(绑 127.0.0.1,端口 8765 起自增);页面从 `localhost` 打开;网页按钮"送回 Blender"→ POST `/apply` → 服务端入 `queue.Queue` → `bpy.app.timers` 主线程轮询写入场景属性 | **一键直达**(浏览器点选→Blender 属性立即更新);体验最接近 rdtool | 线程安全纪律(bpy 仅主线程)、端口冲突处理、生命周期管理 | **A 之上增强,可选** |
| C. Blender 内嵌浏览器 | Blender 无内嵌浏览器控件 | — | 不可行 | 否决 |

**推荐:A 先行(W1),B 作为可选增强(W2)**。W1 的导出/导入链路本身就是 W2 的回传数据格式,先做 A 不浪费任何工作。

**与既有方案的匹配关系**(关键设计决策):
1. **内核契约共享**:网页 JS 内核 = fast_ops 数学(5 点核 + 默认参数 + 同裁剪 + 地图 wrap=True),与 §2.3 契约一致 → 网页地图/预览与 1a numpy 地图、Blender 实际输出三者图案级一致;
2. **导出 schema = presets.json schema + 前瞻扩展键** → 导入侧零转换,W 阶段不侵入预设体系;
3. **三个选参界面共存互补**(§1.3):1b 缩略图(快)、1c 弹窗(轻)、W 网页(全功能探索+存档),不互相替代;
4. **W3 扩展选项预览的公式以阶段 2/3 落地版为准** → 避免网页与插件两头漂移。

### W1. 静态网页 + 导出/导入(核心交付)

**新文件 `web/rdtool.html`**(自包含单文件,内联 JS/CSS,无任何 CDN 依赖,~50-80KB):

```
页面布局(参照 rdtool 控件清单,净室自实现):
┌────────────────────────────────────────────┐
│  主画布:实时动画 GS 模拟(256×256,       │
│  requestAnimationFrame,每帧 N 步)         │
│  左上角叠加 (k,F) 读数                      │
├──────────────┬─────────────────────────────┤
│ (k,F) 地图    │ 控件区:                     │
│ (canvas,点击 │  F / k / Du / Dv / dt 滑杆  │
│  选参;悬停   │  种子:中心方块/圆盘/随机    │
│  显示读数)   │  边界:wrap 开关             │
│              │  预设快选(mitosis/coral/…)  │
│              │  ── 导出 ──                  │
│              │  [导出 JSON] [导出 CSV]      │
│              │  [复制到剪贴板]              │
└──────────────┴─────────────────────────────┘
```

JS 内核(与 fast_ops 同数学,~120 行):
```javascript
// Float32Array 双缓冲 a/b;5 点拉普拉斯(clamp/wrap 可选);
// 反应步与 fast_ops 逐行对应:a = a + (Du·∇²a − a·b² + F·(1−a))·dt
//                          b = b + (Dv·∇²b + a·b² − (F+k)·b)·dt
// 裁剪:a∈[0,2], b∈[0,1](与 fast_ops L64-65 同口径)
// 默认:Du=0.16, Dv=0.08, dt=1.0;地图范围 k∈[0.045,0.07], F∈[0.01,0.1]
```

地图渲染(页面加载时一次性,~80 行):24×18 格、每格 24×24 微型模拟、wrap=True——与 `render_pattern_map`(阶段 1a)同参数,渲染进 offscreen canvas 作地图底图;点击 → 反算 (k,F) → 更新滑杆 + 主画布参数。

导出(~60 行):
- **JSON**(主):见 §4W.4 schema;`Blob` + `URL.createObjectURL` + `a.download`;
- **CSV**(辅):两列键值(`parameter,value` 逐行:Du/Dv/F/k/dt/seed_region/noise_ratio);
- 复制到剪贴板:JSON 文本 `navigator.clipboard`(file:// 下浏览器受限时降级为选中文本提示,不作为主路径)。

**新文件 `fileio/preset_io.py`**(纯 Python,无 bpy,可独立测试,~60 行):

```python
def export_preset_dict(params, name, seed_region, noise_ratio, source="RD_Tool 本地网页导出") -> dict
    # 组装 §4W.4 schema dict(含 id 时间戳、exported_at)

def import_preset_dict(d: dict) -> dict
    # 校验:id/name/params 必填;params 五键齐全且数值合法;
    # 未知键(如 extensions)原样保留;返回规范化 dict,非法抛 ValueError

def write_user_preset(d: dict, user_file: str) -> None
    # 追加进 user_presets.json(已存在则按 id 去重覆盖)

def load_user_presets(user_file: str) -> list
    # 读用户预设列表(文件不存在返回 [])
```

**Blender 端改动**:
- `ui/operators.py` 新增 `RD_OT_import_preset_json`(参照 `RD_OT_import_pattern` L300 模式:`filepath: StringProperty(subtype="FILE_PATH")` + 文件浏览器调用):读 JSON → `import_preset_dict` 校验 → `write_user_preset` 持久化 → report 成功;
- `presets/presets.py`:`get_items()`/`get_preset()` 遍历序列改为 `PRESETS + PRO_PRESETS + USER_PRESETS`(USER_PRESETS 模块级缓存,`load_user_presets()` 惰性加载;名字加"📌"前缀或"[导入]"区分)——**枚举是每次调用动态求值,导入后下拉立即出现,零刷新障碍**;
- `ui/panels.py`:①区预设枚举旁加"导入 JSON 预设"按钮 + "打开 RD 网页工具"按钮(`bpy.ops.wm.url_open` → `file://` 页面路径,仅提示用途)。

**测试 `tests/test_preset_io.py`**:① export → import 往返一致;② 非法 JSON/缺键/超范围值 → ValueError;③ user_presets.json 去重覆盖语义;④ load 空文件/不存在文件容错;⑤ presets.get_items 合并用户预设后 id 唯一。

**跨语言一致性验收(人工黄金样点,一次性)**:选 5 个 (F,k)(mitosis/coral/worms/chaos/pro_maze),并排对比——网页地图格 vs `render_pattern_map` numpy 地图格灰度差 < 12/255;网页主画布定态图案 vs Blender 同参数跑 1000 步图案(视觉核对,允许浮点细节差异)。结果记录进 `docs/` 验收笔记。

### W2. 本地服务回传(可选增强)

**新文件 `web/server.py`**(~90 行):

```python
# ThreadingHTTPServer + BaseHTTPRequestHandler,绑 ("127.0.0.1", port)
# port 探测:8765 起,bind 失败自增(上限 +10),全部占用则报错禁用 W2
# 路由:
#   GET  /          → 返回 rdtool.html(读插件目录文件)
#   POST /apply     → body JSON → import_preset_dict 校验 → _QUEUE.put(d) → 200
#   POST /shutdown  → 服务自毁(可选)
# 线程模型:daemon 线程 serve_forever;_QUEUE = queue.Queue()

# Blender 主线程消费(挂根 __init__.py register/unregister):
# bpy.app.timers.register(_poll_queue, first_interval=0.5)
# def _poll_queue():
#     while not _QUEUE.empty():
#         d = _QUEUE.get()
#         s = bpy.context.scene.ready_rd_settings
#         s.param_Du/Dv/F/k/dt = d["params"][...]   # _param_changed 自动热更新引擎
#     return 0.5    # 继续轮询;返回 None 则注销
```

要点与坑:
- **bpy 线程红线**:HTTP 线程绝不触碰 bpy——只做校验与入队,所有属性写入在 timers 主线程回调;
- `unregister()` 必须 `bpy.app.timers.unregister(_poll_queue)` + `server.shutdown()`(注意 timers 注销在 unregister 期可能已被 Blender 清理,需 try/except);
- 页面侧"送回 Blender"按钮:POST `localhost:{port}/apply`;页面需探测服务是否在线(启动时 GET `/ping`,离线则隐藏回传按钮、只留导出——**W1 页面与 W2 服务同一份 HTML,能力自适应**);
- 安全:仅绑 127.0.0.1(本机回环),不接受外网;无鉴权需求。

测试:① server 单元(ping/apply 路由,monkeypatch queue);② 队列→属性写入的纯逻辑(不依赖真实 bpy,用 stub settings);③ 端口冲突自增逻辑;④ 线程启停(启动 2 次/关闭后再启)。

### W3. 网页扩展选项预览(可选,跟随阶段 2/3)

在 `web/rdtool.html` 控件区追加(公式以阶段 2/3 落地版为准移植到 JS):
- Vary Pattern(Style Map):F/k 渐变/噪声混合,主画布实时预览;
- Orientation:各向异性拉普拉斯(wx/wy 权重,§阶段 3a 公式);
- Flow:7 种速度场 + 半拉格朗日平流(§阶段 3b 公式);
- Scale:s² 缩放 D(§阶段 1d 公式);
- 导出 JSON 的 `extensions` 键随选项填充——**schema 已在 W1 前瞻定义,此处零 schema 变更**。

### W4. 导出数据 schema(v1,Blender 导入侧的契约)

```json
{
  "id": "web_20260820_153000",
  "name": "网页拣选 · F=0.0367 k=0.0649",
  "rule": "Gray-Scott",
  "params": {"Du": 0.16, "Dv": 0.08, "F": 0.0367, "k": 0.0649, "dt": 1.0, "wrap": true},
  "seed_region": "center_disc",
  "noise_ratio": 0.3,
  "source": "RD_Tool 本地网页导出",
  "exported_at": "2026-08-20T15:30:00",
  "extensions": {
    "pattern_scale": 1.0,
    "style_map": null,
    "orientation": null,
    "flow": null
  }
}
```

设计原则:
- **顶层键与 presets.json 条目完全同构** → `RD_OT_preset_load`(operators.py L730-773)加载用户预设时走既有键读取路径,零适配;
- `params.wrap` 是网页模拟时用的边界,导入后由 Blender 的 `grid_wrap` 属性接管(schema 仅作记录);
- `extensions` 为前瞻键:W1 阶段恒为默认值/null,Blender 导入侧**读但暂不消费**,阶段 1d/2/3 落地后逐一接线——**schema 一次定稿,后续免迁移**;
- CSV 为人读/Excel 辅助格式,不参与 Blender 导入(JSON 为唯一机器通道)。

---

### 阶段 2:Style Map(F/k 参数场)

**新文件 `core/param_field.py`**(纯 numpy,无 bpy,可独立测试):

```python
def gradient_field(shape, axis=0, lo=None, hi=None) -> ndarray     # 线性渐变
def noise_field(shape, seed, octaves=3, lo=None, hi=None) -> ndarray  # 值噪声(粗随机网格上采样叠加,纯 numpy ~20 行)
def image_field(shape, gray01: ndarray, lo=None, hi=None) -> ndarray  # 灰度图 [0,1] → 参数映射
def blend(scalar, field, strength) -> ndarray   # (1-t)·scalar + t·field
```

约定:`lo/hi` 默认 = 地图活跃区(k∈[0.051,0.066]、F∈[0.026,0.056] 经验窗),输出 float32,值域钳制。

**内核改动(最小化——numpy 广播已天然支持)**:
- `core/fast_ops.py` `gray_scott_step_opt`:F/k 形参注释改为"标量或与 a 同形 ndarray",数学体零改动(`a *= (1.0 - F*dt)` 对数组 F 广播成立);**加一行防御**:`if isinstance(F, np.ndarray): assert F.shape == a.shape`;
- `core/rule.py` `GrayScottRule.update`:同理,零数学改动。

**装配链**:`params["F"] = F_array` → `NumpyBackend.step` L34-38 原样透传 → 内核广播。**后端零改动**。

**UI 三件**:
- `ui/properties.py`:`style_map_source`(枚举:无/梯度/噪声/图像)、`style_map_image`(PointerProperty→bpy.types.Image,参照 template_ID 教训)、`style_map_strength` [0,1]、`style_map_axis`、`style_map_noise_scale`;
- `ui/operators.py` init 路径:bpy 图像 → pixels(RGBA)→ 灰度 → resize 到网格形状(纯 numpy 最近邻)→ `image_field(...)` → 写入 params;
- `ui/panels.py`:③ 区条件显示(仅 grid+GS;参照 oil_water ④ 区显隐先例)。

**与 W 阶段的衔接**:Style Map 落地后,W3 网页 Vary Pattern 用同一公式;导出 JSON 的 `extensions.style_map` 填 `{source, strength, axis, noise_scale}`(图像源不含像素,仅记配置)。

测试 `tests/test_param_field.py`:① 三种源的形状/值域/钳制;② **strength=0 → 与标量运行逐位一致**(零回归);③ strength=1 → 等于纯场参数运行;④ fast_ops vs rule.py 数值一致性 max|Δ|<1e-6;⑤ 图像源:棋盘灰度 → F 场呈两值分布。

### 阶段 3a:Orientation(均一各向异性)

**数学**(保持总扩散量不变 → 稳定域不变):
```
w1 = 1+α(主轴), w2 = 1−α(副轴), α∈[0, 0.95], θ∈[0, π)
wx = w1·cos²θ + w2·sin²θ
wy = w1·sin²θ + w2·cos²θ          # wx+wy ≡ 2,谱半径仍为 8 → dt·Du≤0.25 不变
∇²u ≈ wx·(u[i−1,j]+u[i+1,j]−2u) + wy·(u[i,j−1]+u[i,j+1]−2u)
```

**内核**:
- `core/fast_ops.py` 新增 `laplacian_aniso_5_fast(u, wx, wy, wrap, out)`;`gray_scott_step_opt` 加 kwargs `wx=1.0, wy=1.0`——**默认值走原 isotropic 快路径(零回归),非默认才进 aniso 分支**;
- `core/rule.py` 同步 kwargs(参考路径)。

**UI**:`orient_enable/angle/strength` 三属性 + ③ 区条件显示(grid+GS)。

**与 W 阶段的衔接**:W3 网页 Orientation 控件用同一 wx/wy 公式;导出 `extensions.orientation = {enable, angle, strength}`。

测试:① α=0 → 逐位等于 isotropic;② θ=0 vs θ=π/2 → 图案统计旋转 90°(与其转置的相关系数显著高于未转置);③ α=0.9、dt·Du=0.24 边界 2000 步无 NaN。

### 阶段 3b:Flow(半拉格朗日平流)

**新文件 `core/flow_field.py`**(纯 numpy):

```python
def velocity_field(shape, kind, strength, center=None) -> (vx, vy)
    # 7 种(rdtool 实测清单,v1 误写 6 种,已修正):
    # vertical: v=(0,s)
    # radial:   v=s·ê_r                     rotate: v=s·ê_θ
    # swirl:    v=s·(|r|/R)·ê_θ             vortex: v=s·(ê_θ − 0.3·ê_r)
    # bubble:   v=s·ê_r·exp(−(|r|/R)²)      ring:   v=s·ê_r·exp(−((|r|−0.5R)/(0.15R))²)
    # R=网格半对角;ê_r=r/|r|, ê_θ=垂直单位向量;衰减形状可调,无版权公式

def advect(u, vx, vy, dt, wrap=False) -> ndarray
    # 半拉格朗日回溯 + 双线性采样(~25 行纯 numpy:floor/frac + np.take 平坦索引,
    # 越界 wrap 模取模 / clamp 模截断);常数场恒等;每步质量近似守恒(双线性不严格)
```

**集成**:`controller/engine.py` tick 循环——GS 步进后若 `params.get("flow_kind","none")!="none"` 则对 a、b 各 advect 一次;速度场构建缓存于引擎(参数变更时重建)。

**UI**:`flow_kind`(无+7 种枚举)、`flow_strength`,grid+GS 条件显示。

**与 W 阶段的衔接**:W3 网页 Flow 控件(7 种场)用同一公式;导出 `extensions.flow = {kind, strength}`。

测试 `tests/test_flow.py`:① advect 常数场 → 逐位不变;② 高斯斑 + vertical 流 → 质心位移 ≈ v·dt·步数(双线性扩散容差内);③ 7 种场在定义域内模长有界无 NaN;④ 质量 100 步漂移 <1%。

---

## 五、约束与风险(汇总)

1. **测试红线**:全量回归(`py tests\run.py` + 逐文件);**禁 pytest 直收 tests/**(INTERNALERROR 既有教训);
2. **净室**:地图/缩略图/网页一律自实现(Karl Sims 图片与 rdtool.js 有版权),恰与"所见=所得"的正确性要求一致;
3. **双内核同步**:fast_ops 与 rule.py 数值一致是硬断言(每阶段必带);W 阶段 JS 内核按 §2.3 契约对齐(图案级一致,黄金样点人工核对);
4. **稳定性**:`dt·Du ≤ 0.25` 是 Scale/Orientation 共同的硬边界(各阶段自带防护与测试);
5. **模式显隐**:Scale/Style Map/Orientation/Flow 全部仅 grid+GS 显示(mesh/grow3d 隐藏,参照 oil_water 先例);
6. **生命周期**:previews 集合、draw_handler、W2 的 HTTP 服务与 timers 必须 register/unregister 成对,防 Blender 关闭告警;
7. **线程安全(W2 特有)**:bpy 调用仅限主线程;HTTP 线程只做校验+入队;服务仅绑 127.0.0.1;
8. **离线自包含(W 特有)**:网页单文件、无 CDN 依赖;file:// 下剪贴板 API 受限时降级(下载为主路径)。

---

## 六、用户决策记录

| 日期 | 事项 | 决定 |
|---|---|---|
| 2026-08-19 | 本次实施范围 | 仅报告,不实施 |
| 2026-08-19 | Pattern Map UI 形态 | **两者都要**(缩略图枚举 + 点击取参弹窗) |
| 2026-08-19 | 珊瑚/指纹命名 | 保留"珊瑚生长"现名,source 补 Karl Sims 别名标注(已实施) |
| 2026-08-20 | 文档 | 升级为实施交接版(v2):补学习来源、接入点勘察、逐步实施步骤 |
| 2026-08-20 | **RD_Tool 网页本地化** | **新增需求**:本地网页直接选取效果 + 导出 CSV/JSON 供 Blender 调取;评估为阶段 W(W1 静态版必做,W2 回传版/W3 扩展预览可选),与阶段 1/2/3 经"内核契约 + schema 同构"衔接(见 §4W);文档升级 v3 |
| 2026-08-22 | **W2/W3 取消** | **不执行**:已确认其他团队完成了阶段 1(1a/1b/1c/1d)与 W1 后端部分的项目修改;W2(HTTP 回传)与 W3(网页扩展预览)从计划中移除。核实与质量评估见 §八 |

## 七、版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-08-19 | 初版评估 |
| v2 | 2026-08-20 | 补学习来源(§0);修正 grid 内核为两处非三处、Flow 7 种非 6 种;补数值口径对照(§2.3);分 7 个可独立交付子步骤的实施细节(§4);验收标准与测试计划并入各步 |
| v3 | 2026-08-20 | 新增阶段 W(RD_Tool 网页本地化):§1.3 三界面互补定位;§2.4 可复用资产勘察(导入操作符先例/注册挂点/预设合并点);§4W 三形态评估(静态页/本地服务/内嵌否决)、W1-W4 实施细节、导出 schema 前瞻设计;§五 增补线程安全与离线自包含约束;总览表并入 W1/W2/W3 |
| v4 | 2026-08-22 | W2/W3 决定不执行并移出计划;新增 §八 实施状态核实:其他团队交付的 1a/1b/1c/1d 质量评估(全过回归)、W1 部分实施的三项遗留缺口清单、W1 收尾指引;**同日 W1 四项缺口全部收尾完成**(网页/导入操作符/预设合并/测试),全量回归通过 |
| v5 | 2026-08-22 | 阶段 3a(Orientation)/3b(Flow) 实施完毕并通过回归;**修复各向异性 5 点拉普拉斯内核缺陷**(主对角线系数少乘 2,致 wx=wy=1 不还原标准核、任意 Orientation 压平图案);**新增 §九**记录缺陷细节、修复与 Orientation/Flow/Scale 参数验证结果(配套 test_w1_extensions.py) |

---

## 八、实施状态核实与质量评估(2026-08-22)

> 背景:用户告知"已由其他团队进行项目修改"。本节为逐文件核实结果与质量评估,全量回归由本方独立复跑验证。

### 8.1 已交付内容核实(质量:良好,全部符合 v3 方案)

| 交付物 | 文件 | 核实结论 |
|---|---|---|
| **1a 渲染器** | [pattern_map.py](../presets/pattern_map.py) | ✅ 完整:`kf_from_uv`/`uv_from_kf` 双向映射(v 轴翻转处理正确)、地图+缩略图渲染(与 fast_ops 同 5 点内核口径)、内存+npy 双缓存(64 条上限防膨胀)、自包含 PNG 编码(zlib+struct,无 PIL 依赖) |
| **1b 缩略图** | [previews.py](../ui/previews.py) | ✅ register/unregister 成对挂载于插件 `__init__.py` L70-73;全程异常安全(失败返回 0 显示纯文本项);`_icon_cache` 按 preset_id 缓存 |
| **1c 取参弹窗** | [operators.py](../ui/operators.py) `RD_OT_pattern_map_pick`(L1477) | ✅ 模态操作符:地图渲染进 Image Editor(复用既有区域,记录并还原原 image)、gpu 十字准线 + blf 实时读数 "k=… F=…"(模仿 rdtool 交互)、cleanup 全路径自愈(退出还原 area/image/draw handler);坐标经 view2d 换算(方案要求的坑均已规避) |
| **1d Scale** | [parameter.py](../core/parameter.py) `scale_params` + 三处接线 | ✅ 完整闭环:数学与方案一致(Du/Dv×s²,不移动 F/k);子步保护 `n_sub=ceil(Du_eff·dt/0.2)`(安全系数 0.8);`_n_sub` 键经 params 字典透传,消费点三处齐全(properties L122 热更新 / operators L70 初始化 / numpy_backend L43 运行循环实际子步);属性 min=0.25/max=2.5 与方案一致 |
| **W1 后端** | [preset_io.py](../fileio/preset_io.py) | ✅ 纯 Python 无 bpy 可独立测试;schema 与 §4W.4 完全一致;校验完整(id/name 必填、五参数有限数且物理范围、seed_region 白名单);同 id 去重覆盖;损坏文件容错返回 [] |
| **配套测试** | [test_pattern_map.py](../tests/test_pattern_map.py)(7 项)、[test_scale.py](../tests/test_scale.py)(5 项) | ✅ 覆盖方案要求的全部断言:UV 往返、已知点灰度差异、确定性、像素行序翻转、PNG 编码、缓存命中;s=1 逐位一致(零回归)、子步激活、无 NaN |

### 8.2 回归验证(本方独立复跑,2026-08-22)

| 测试 | 结果 |
|---|---|
| test_core(run.py) | 10/10 ✅ |
| test_pattern_map(新) | 7/7 ✅ |
| test_scale(新) | 5/5 ✅ |
| test_oil_water | 全过(含细分立方体 400 步回归)✅ |
| test_grow3d | 全过(含网格边界模式 numba/numpy 一致 max|Δ|=1.49e-07)✅ |
| test_formula / test_m2_modules / test_systems | 6/6 · 13/13 · 8/8 ✅ |

**结论:其他团队的修改无回归破坏,阶段 1 全部验收通过。**

### 8.3 W1 遗留缺口(2026-08-22 已全部收尾完成)

| # | 缺口 | 收尾结果 |
|---|---|---|
| 1 | `web/rdtool.html` 网页本体 | ✅ **已创建**:自包含单文件(JS 内核=fast_ops 数学/5 点核/同裁剪,主画布 256² 实时动画,(k,F) 地图 24×18 分批异步渲染,滑杆+预设快选+种子/wrap 选项,导出 JSON/CSV/剪贴板)。浏览器实测:无 JS 报错、地图 2 秒就绪、图案正常、点击选参生效、导出提示正确。修复过一个种子 bug(种子区 a=1-v 扣减致 b 衰亡→纯白;改 Pearson 标准 a=1) |
| 2 | `RD_OT_import_preset_json` 导入操作符 | ✅ **已实施**(operators.py 末尾):文件浏览器 → `import_preset_dict` 校验 → `write_user_preset` 持久化 → `refresh_user_presets()` 刷新下拉;附 `RD_OT_open_rdtool_web`(file:// 打开网页工具,受限时降级提示路径)。两类已注册进根 `__init__.py` register/unregister |
| 3 | 用户预设合并进 `get_items()` | ✅ **已应用**:`py wire_w1_merge.py` 执行成功(_load_user/refresh_user_presets/get_preset/get_items 合并版),一次性补丁脚本已删除 |
| 4 | `tests/test_preset_io.py` | ✅ **已创建**:5 项全过(往返一致 / 11 种非法输入 ValueError / 同 id 去重覆盖 / 4 类容错 / 预设合并 [导入] 前缀+id 唯一+refresh) |

**入口 UI**:主面板 ③ 区「加载预设」下新增一行(grid+GS 条件显示):「RD 网页选参」+「导入 JSON 预设」。

**W1 完整链路**:③区「RD 网页选参」→ 浏览器地图/滑杆选参 →「导出 JSON」→ ③区「导入 JSON 预设」→ 预设下拉出现 [导入] 前缀项 → 加载。

### 8.4 W2/W3 不执行的影响评估

- **W2(本地 HTTP 回传)取消**:无功能损失——W1 的"导出 JSON → 导入操作符"链路已覆盖参数传递;仅损失"浏览器一键送回"的便捷性。线程安全风险(方案 §五.7)随之消除,插件生命周期管理简化。
- **W3(网页扩展预览)取消**:网页将保持基础参数探索(F/k/Du/Dv/dt + 地图);扩展选项(Style Map/Orientation/Flow/Scale)的预览与调参由插件内 ③ 区 UI 独立承担(阶段 1d 已交付 Scale 滑杆,阶段 2/3 交付其余)。导出 schema 的 `extensions` 前瞻键**保留不删**:W1 网页照常填写默认值,阶段 2/3 落地后导入侧直接消费,免 schema 迁移。
- **对 §五 约束的影响**:线程安全约束(第 7 条)与 HTTP 生命周期约束(第 6 条中 W2 部分)随之作废;其余约束(测试红线/净室/双内核同步/稳定域/模式显隐/离线自包含)全部保留。

---

## 九、各向异性内核缺陷修复与参数验证结果(2026-08-22)

> 阶段 3a(Orientation)/3b(Flow) 落地时,发现并修复一处**各向异性 5 点拉普拉斯内核缺陷**;随后对 Orientation/Flow/Scale 三类参数做了效果验证。本节省去方案 §阶段 3a/3b 的数学细节(见 §4),只记缺陷、修复与验证数据。配套测试:`tests/test_w1_extensions.py`(6 项全过)。

### 9.1 缺陷现象与根因

| 项 | 内容 |
|---|---|
| **现象** | wx=wy=1(等向)时,各向异性 5 点核**不还原**标准 5 点拉普拉斯(逐位不相等);任何 Orientation kind/strength 都会把活跃图案**压平为均匀场**(b 场标准差趋 0)。 |
| **根因** | 主对角线项系数**少乘 2**。各向异性核应为 `−2·(wx+wy)·u`(对 x、y 两方向各贡献 `−wx·u`、`−wy·u`),实现误写成 `−(wx+wy)·u`。 |
| **影响范围** | 两处同源:`core/ops.py` `laplacian_aniso_5`(L77)与 `core/fast_ops.py` `_laplacian_aniso_5_fast`(L125)。rule.py 走 ops 引用,随修复同步正确。 |

### 9.2 修复内容

```
修复前(两处):  lap = -(wx + wy) * u
修复后(两处):  lap = -2.0 * (wx + wy) * u      # x/y 两方向各计一次 -w·u
```

- 修复后 wx=wy=1 ⇒ `−4u` + 四邻 +u = 标准 5 点拉普拉斯,**逐位一致**;
- 谱半径保持 `2(wx+wy)≡4`(因 `orientation_weights` 保证 wx+wy≡2),稳定域 `dt·Du≤0.25` 不随 Orientation 改变(§阶段 3a 的数值前提未被破坏);
- `orientation_maps(kind,strength)` 已支持均匀模式(返回标量 wx/wy)与空间模式(返回 2D 图),空间模式沿网格派生的角度图构造 `laplacian_aniso_5_fast` 所需的非标量权重,后端 `_weights_are_iso` 仅对 `(1.0,1.0)` 标量走等向快路径,其余进各向异性分支——确保等向时零回归。

### 9.3 Orientation / Flow / Scale 参数验证结果

全部在 `tests/test_w1_extensions.py` 锁定,48² 网格 + Gray-Scott(F=0.0545,k=0.062),`NumpyBackend.step(..., field_kind="grid")` 跑 800 步:

| # | 验证项 | 方法 | 结果 |
|---|---|---|---|
| 1 | **等向还原** | wx=wy=1 ⇒ `laplacian_aniso_5` 与 `laplacian_5` 逐位比较 | `np.allclose(aniso, iso, atol=1e-6)` 通过 |
| 2 | **fast 与 ops 一致** | 对 linear/radial/bubble 空间模式,`_laplacian_aniso_5_fast` vs `laplacian_aniso_5` | `atol=1e-5` 全通过(空间图模式两条核路径一致) |
| 3 | **Orientation 不复现压平** | 6 种 kind(linear/horizontal/radial/circles/swirl/bubble,strength=0.3)各跑 800 步 | b 场 std 均 > 0.5×基线 std;**图案保形**,仅改变走向/形态 |
| 4 | **Flow 确实改变场** | swirl(0.6) vs 基线逐点差异 | `max\|b−baseline\|=0.08 > 1e-3`,确定生效。**注**:平流只搬移分布不改方差,故用逐点差而非方差(方差守恒是早前试错误判"无效果"的根源) |
| 5 | **组合稳定** | Orientation(radial,0.3)+Flow(vortex,0.5) 同时启用 | 全程有限(无 NaN),b 场 std>0.05 |
| 6 | **平流有界且移动图案** | 64² 高斯斑 + swirl 场 advect 300 步 | 速度场模长<1(稳定);图案确实位移(max\|Δu\|>1e-3) |

Scale 验证(承接 §阶段 1d,配套 `tests/test_scale.py` 5 项):s=1 逐位等于现行输出(零回归);s=0.5 无子步、2000 步无 NaN;≥1.25 时子步保护 `n_sub=ceil(Du_eff·dt/0.2)` 激活、无 NaN 且图案特征尺度扩大;n_sub 计算函数单测。

### 9.4 关键教训与后续建议

- **平流效果判别准则**:对流只重新排布场的分布、近似守恒方差,**用方差变化判断"是否生效"会得到假阴性**——须用逐点/特征位移指标。
- **各向异性核自检**:等向退化断言(wx=wy=1 逐位还原标准核)应作为 permanent 回归用例,防止重建内核时丢失 ×2 系数。
- **后续**:阶段 2(Style Map 参数场)仍待办;其 `extensions.style_map` 前瞻键已在 W1 schema 预留,落地后导入侧直接消费。
