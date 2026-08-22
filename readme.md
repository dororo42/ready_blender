# Ready: Reaction-Diffusion for Blender

反应扩散(RD)与元胞自动机(CA)在 Blender 网格体与规则网格上的模拟插件。

**净室实现声明**:本插件依据公开论文(Gray & Scott 1983-84;Pearson 1993;Turing 1952;
FitzHugh-Nagumo;Rafler 2011 等)独立重新实现反应扩散算法,
不含 GollyGang/ready(GPL-3.0)源码的任何翻译或复制。许可:GPL-3.0-or-later
(上 extensions.blender.org 平台要求;自托管分发可另选许可,净室保证切换成本为零)。

## 功能

> **UI 交付状态标注**:以下功能中,标注 ✅ 的已接入 Blender 面板/操作符;标注 📦 的为库层就绪、UI 待后续版本接入(Python API 可用)。

- **Gray-Scott 反应扩散** ✅:规则网格(2D)与任意三角网格(mesh 直跑)双路径
- **输出** ✅(顶点色/命名属性/置换);📦 纹理(UV 烘焙):顶点色 / 命名属性(Geometry Nodes 消费)/ 置换 / 散布密度 / UV 烘焙纹理(M2)
- **双模式** ✅:低分辨率参数预览(bpy.app.timers)+ 全分辨率离线烘焙(进度条,可取消)
- **初始条件** ✅:画笔涂抹 / 噪声 / 预设图案;快照 undo
- **密度治理** ✅:网格面积变异系数检测 + 一键 Voxel Remesh 引导
- **公式系统** ✅:FHN/Brusselator/Schnakenberg/Oregonator 四系统 + 9 组参数变体(螺旋波/靶波/图灵斑图等),面板直接切换;Python API:core.formula.FormulaRule
- **Oil-Water 相分离** ✅:第 6 系统(Agmon et al. 2014, ALife 14 净室实现)——互相排斥流体的偏置扩散,双场白噪声初始,质量守恒;仅 2D 网格;Python API:core.rule.OilWaterRule
- **元胞自动机**(M2) 📦(Python API:core.ca_rules):Conway Life / Larger-than-Life / SmoothLife
- **网格生成器**(M2) 📦(Python API:core.meshgen):三角 / 六角 / rhombille / 测地球面 / 环面
- **vti/vtu IO**(M2) 📦(Python API:fileio.vtk_xml/vtk_writer):读取 Ready 生态的 93 个 pattern 文件(解析层 100% 兼容)
- **3D 体素** ✅ 一键入口:**3D 生长管道**(⑥ 区,体素 Gray-Scott 在 Dirichlet 框架内生长 → 等值面网格新对象;文献口径 Du=0.082/Dv=0.041/F=0.035/k=0.064,参数取 ③ 区可调)+ Python API(core.field3d / adapters.volume_adapter.simulate_growth_3d);切片 / 稀疏体素输出为库层能力
- **性能**(M3) ✅(优化内核已接入):微优化内核(1.9-2.3x)+ FFT SmoothLife;**Numba 可选后端** ✅(偏好设置自助安装,顶点域 JIT 加速,未装自动回退);compute shader 可选加速(Win/Linux,暂缓)

## 安装

### 开发安装

1. 下载 Blender 4.2 LTS 或 4.5 LTS
2. 复制本项目到 Blender 扩展目录,或将仓库根目录打包为 zip:
   ```
   blender --command extension build
   ```
3. Blender 内:编辑 → 偏好设置 → 获取扩展 → 从磁盘安装 → 选择 zip

### 手动安装(开发)

```
blender -b --python-expr "import bpy; bpy.ops.preferences.addon_install(filepath='ready_blender.zip'); bpy.ops.preferences.addon_enable(module='ready_blender')"
```

## 使用

1. 3D 视口 N 侧栏 → Ready 面板
2. 选择"网格(MeshRD)"域 → 指定目标网格对象 → 初始化模拟
3. 调参数(F/k/Du/Dv 滑块)→ 播放/步进/烘焙
4. 输出:命名属性 RD_value(面域)+ 顶点色(GN 可读)
5. 画笔:左键拖动涂抹;右键=撤销退出,ESC/回车=保留退出;切换涂抹化学品(a/b)时显示自动跟随,笔值自动避开"不可见值"(a 场涂 1 / b 场涂 0)
6. 凹凸(几何节点修改器,非破坏):点"一键凹凸(几何节点修改器)"——任意输出模式下都会直写 RD_disp 并自动搭节点树,强度暴露为修改器输入
7. 顶点凹凸(直接几何):点"一键顶点凹凸"——顶点域一次性求解后直接位移顶点(Ctrl+Z 可回退);建议先做质量检查/Voxel Remesh 保证顶点均匀,配合"均匀稀疏种子"出满铺纹理
8. Numba 加速(可选):偏好设置 → 插件 → Ready → 安装 Numba(镜像源可选);已装时顶点凹凸自动走 JIT 加速,未装自动回退 numpy(结果一致)
9. 导入 Pattern:④ 初始条件 → "导入 Pattern 为初始条件(.vti)"——选择 Ready 生态 pattern 文件;Gray-Scott 型自动同步参数,初始场为空的生成器型自动改用基底+中央种子(详见下节)

## Ready Pattern(.vti)是什么

Pattern 是开源软件 **Ready**(GollyGang 项目,GPL)的"模拟档案"格式,类似 Golly 的 .rle 元胞自动机图案文件。每个 .vti 内含:

- **化学品初始场**:两个化学量在网格上的数值分布(a/b 或 u/v)
- **规则定义**:公式型(67 个,如 Brusselator/Oregonator)/ 内置型(3 个 Gray-Scott)/ 内核型(23 个)
- **参数**:该规则的 F/k/扩散率等
- **文献描述**:模型出处与现象说明

官方库共 93 个 pattern,本项目解析层 100% 兼容(回归测试覆盖)。**注意**:
1. 插件不捆绑这些文件(GPL 生态,上架合规),需自行获取 Ready 源码包中的 Patterns 目录
2. 61 个 pattern 初始场为空(靠 Ready 的生成器现场播种)——导入此类时 Gray-Scott 自动改用"基底 a=1/b=0+中央种子",导入即可播放
3. 仅支持 2D 网格型(.vti,Z 维=1);3D 体素与 .vtu 网格型不支持
4. 公式型 pattern 的参数命名与本项目净室实现不同,导入初始场后请在①区手动切换对应系统

## 两条求解路径与口径说明

插件内并存两条路径,**数值口径有三处刻意差异**,列表如下以免混淆:

| 维度 | 播放路径(engine+scheduler, 面域 MeshRD) | 一键顶点凹凸(顶点域 vertex_rd) |
|---|---|---|
| 求解域 | 面域(状态在三角面上),输出经面积加权平均映射到顶点 | 顶点域(状态在顶点上),浓度 1:1 → 位移,无映射模糊 |
| 拉普拉斯 | 面邻接 **1/度归一化**(w=1/k) | 边图 **非归一化**(Σ邻居 − deg·U);顶点度不均时有效扩散率随度变化,故建议先 Voxel Remesh 均匀化 |
| 位移归一化 | 固定值域 [0, 0.5](帧间稳定,无漂移) | **min-max 归一化**(单次流程内对比度拉满) |
| 迭代方式 | timers 实时播放/烘焙(进度条) | 一次性阻塞跑 bake_steps 步(外部 Pro 类插件同款流程) |

## 性能参考(M0/M3 实测,4 核桌面 CPU,无 GPU)

| 场景 | 步/秒(M0) | 步/秒(M3 优化后) |
|---|---|---|
| 256² 规则网格 | 345 | 781 |
| 512² 规则网格 | 67 | 175 |
| 10k 面 mesh | 1,371 | — |
| 50k 面 mesh | 180 | — |
| SmoothLife FFT 128² | — | 330 |

## 目录结构

```
ready_blender/
├── core/          # RD Core:ops/field/rule/formula/ca_rules/meshgen/field3d/fast_ops
├── controller/    # engine(状态机)/scheduler/session
├── backend/       # numpy_backend / numba_backend(可选) / compute_backend(可选)
├── adapters/      # mesh/image/uv_raster/volume 输出适配
├── fileio/        # vtk_xml:vti/vtu 解析(93 pattern 兼容)
├── ui/            # properties/operators/panels/preferences(numba 窗口)
├── presets/       # 12 组 Gray-Scott 预设 + 4 公式系统 9 变体(CC0)
└── tests/         # 单测(纯 Python 运行器)
```

## 发布检查清单(extensions.blender.org)

- [ ] `blender --command extension validate` 通过
- [ ] `blender --command extension build` 产出 zip
- [ ] 干净环境(4.2 LTS + 4.5 LTS)安装冒烟通过
- [ ] 许可:manifest `SPDX:GPL-3.0-or-later`;全部资产 CC0 自制
- [ ] 不捆绑第三方 GPL 资产(pattern/图标)
- [ ] 无原生 wheels(纯 Python + numpy 内置)
- [ ] 只读安装兼容(`bpy.utils.extension_path_user`)

## 净室过程记录

- 技术源:Gray & Scott(1983-84),Pearson(1993),Turing(1952),FitzHugh-Nagumo,
  Rafler(2011),Gardner(1970)等公开文献
- 开发过程未对照/翻译 Ready 源码;vti/vtu 解析按 VTK 公开格式规范 + 文件观察独立实现
- 默认参数集取自论文图例,预设自行确定

## 已知限制

- compute shader 后端仅 Windows/Linux(需 Blender 运行时调试)
- fragment shader offscreen ping-pong 需 Blender 运行时调试
- SmoothLife 完整版为 FFT 近似(M3),参数与 Ready 版无对应关系(净室)
- Blender 5.x(Python 3.13)未验证
