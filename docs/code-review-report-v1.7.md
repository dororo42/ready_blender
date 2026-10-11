# ready_blender 独立代码审查报告 v1.7(2026-10-11)

> 审查方式:四路独立并行审查(core 求解核心 / adapters+fileio+backend / tests+CI+工程化+web / ui+controller),
> 交叉验证后合并;全部结论以代码证据为准,数值结论经手工推演与本地复现(65 项 pytest 全绿基线上实施)。
> 本报告同时是 v0.1.2 修复的实施记录:标注【已修复】的条目均已落码并有回归测试或编译验证;标注【建议】的为遗留项。

## 总体评估

**风险等级:中。** 数值核心(laplacian 族、Oil-Water 守恒、meshgen 焊接、numba 双核、preset_io 校验)质量扎实,
历史审查修复均有测试锚定;主要风险集中在:

1. **测试真实性问题(最严重)**:约半数测试文件"只打印不断言",pytest 下永不可能失败——CI 绿是假象;
2. **不可信输入无资源上限**:.vti 解析可被解压炸弹打爆 Blender 主进程;
3. **官方扩展加载路径上的潜伏炸弹**:两处包内相对导入写错,测试的顶层加载模式完全掩盖;
4. **跨路径口径不一致**:2D/3D 平流强度差约 180 倍、Orientation"竖直"实际沿水平、图案缩放在 mesh 路径不生效——
   直接伤害"同一参数两条路径等价"的产品承诺。

## 一、安全(不可信输入)

### 🔴 A1【已修复】vti 解压炸弹 / 无输入上限 — fileio/vtk_xml.py
- 证据:原 `_decode_streams` 直接 `zlib.decompress(raw[pos:pos+sz])`,块尺寸来自攻击者可控头部 uint32,
  全链路无输出上限;实测 265KB base64 文本可解出 200MB(≈780:1),约 10MB 恶意 .vti 即可让 Blender OOM。
- 修复:`zlib.decompressobj()` 分块解压 + 单文件累计输出上限 256MB(超限抛 `VTKError`);
  入口 `read_file` 限制文件 ≤512MB;`decode_inline` 头部 nblocks 合法性校验。
- 回归:`tests/test_vtk_hardening.py::test_decompress_bomb_capped`。

### 🟡 A2【已修复】byte_order 只作用于头部,数据数组按本机序解码 — fileio/vtk_xml.py
- BigEndian 文件头部解析正确、数据全部按小端错读(静默数据损坏)。修复:数据 dtype 按 `.newbyteorder(endian)`
  解码后转本机序。回归:BE 浮点/整型 round-trip 两例。

### 🟡 A3【已修复】畸形输入鲁棒性 — fileio/vtk_xml.py
- ascii 空元素 `da.text is None` → AttributeError;`WholeExtent` 数量/负维不校验(报错位置远离根因);
  数据长度从不与 dims 对账;`read_vti` 逐数组无错误包装(裸 struct.error/KeyError);`read_file` 双重解析。
- 修复:全维度校验(ext==6、dims≥1、PointData 长度=域点数×分量数)、统一 `VTKError` 包装、单次解析、
  dtype 表补 `UInt32` 并包装 KeyError。回归:test_vtk_hardening 后三例。

### 🟡 A4【已修复】用户预设加载无校验,损坏 JSON 直通 UI — fileio/preset_io.py
- `load_user_presets` 只检查 `d.get("params")`,字符串数值/NaN 会经 `RD_OT_preset_load` 赋给
  FloatProperty 抛 TypeError 崩操作符(与导入路径双口径)。修复:逐项过 `import_preset_dict`,非法项丢弃;
  `wrap` 仅接受真布尔。验证过正确:XML 实体炸弹被现代 expat 放大防护拦截;RD 段绝不执行 IPG 脚本。

### 🟢 A5【建议】numba 安装走用户自定义镜像,无完整性校验 — ui/preferences.py
- `subprocess.check_call`(无 shell=True,无命令注入)但 `custom_mirror` 任意 URL 无摘要校验;属用户自担风险的
  自助安装,建议文档标注"仅使用可信镜像"。已修复项:host 提取对畸形 URL 不再 IndexError。

## 二、正确性

### 🔴 B1【已修复】官方扩展加载模式下参数地图功能损坏 — presets/pattern_map.py:17
- `from .fast_ops import ...` 写错(fast_ops 在 core/ 包),包模式主导入必失败、fallback 绝对导入同样失败:
  预设缩略图静默失效、`RD_OT_pattern_map_pick` 直接报错。测试的顶层加载模式完全掩盖。
- 修复:`from ..core.fast_ops import`;同类 `adapters/uv_bake_blender.py` 的 `..uv_raster`→`.uv_raster`;
  两者纳入启动自检清单(`__init__._self_check`)。

### 🔴 B2【已修复】网页导出 Du/Dv 映射与实际动力学不符,DS>1 时导出数值不稳定 — web
- 网页着色器 `dt=1/(4DS)`、扩散项 `*DS*vec2(1,0.5)` → 有效扩散恒为 Du=0.25/Dv=0.125,diffusion_scale 只改
  播放速度;原导出 `0.256*DS/0.128*DS` 把速度滑块映射成扩散系数:DS≠0.625 时 Blender 端图案偏离预览
  2.5~8 倍,DS>0.98 时 Du·dt 越出显式欧拉稳定域(插件自己的 scale_params 都以 0.2 为安全上限)。
- 修复(发布版 HTML 与 build 模板同步):`Du=0.25, Dv=0.125, dt=min(1/(4DS), 0.8)`(dt 钳制保 Du·dt≤0.2,
  图案类型只取决于 F/k/Du/Dv 比值,不受影响);CSV 同步;构建脚本模板的 orientation 也同步为已发布的
  kind/strength IIFE(原模板会静默重置为 none)。

### 🔴 B3【已修复】web/rdtool.html 启动脚本引用未定义的 `refact()`,页面黑屏不可用
- 顶层同步脚本抛 ReferenceError,后续播种/动画循环/地图渲染全部不执行。修复:`refact()`→`rebuildExt()`;
  全部内联 JS 过 `node --check`。

### 🟡 B4【已修复】2D Orientation 均匀模式的角度约定与 Flow/mesh 路径/显示轴向相反 — core/ops.py
- 四条独立证据(meshgen axis-0→世界 Y、image_adapter 行主序、flow_field"vertical"=axis-0、mesh 路径
  linear=局部 Y)指向 axis-0=竖直;原实现 linear→90°(axis-1)使用户选"竖直"得到水平主扩散。
- 修复:linear/vert/vertical→0°(axis-0)、horizontal→90°(axis-1),docstring 显式声明角度约定
  (0°=axis-0 起测);测试未锁定旧约定(仅 fast==reference 与防塌缩),零破坏。

### 🟡 B5【已修复】Flow 速度按半对角归一化与注释矛盾,2D/3D 平流强度差 ~180 倍 — core/flow_field.py
- 原 `/half_diag` 使 256² 网格上 strength=1 的实际位移 ~0.005 格/步(预览不可见),而 3D mesh 路径同滑杆
  位移 ~1 世界单位;docstring 自称"∥v∥max ≈ strength"。修复:去掉归一化(各类型模长本就 ≤1),
  vortex 包络加非负钳制(偏心 center 防反向)。副作用(预期内):强平流(≥0.25)可在图灵不稳定性建立前
  剪切稀释中心种子致图案灭绝——真实物理行为,`test_both_combined_finite` 重新标定至 0.15 并注释依据。

### 🟡 B6【已修复】scale_params 子步只按 Du 计算,Dv>Du 时稳定保护失效 — core/parameter.py
- Du=0.05/Dv=1.0/dt=2 时 n_sub=1,dt·Dv·8=16≫2,b 场失稳被 clip 成噪声块。修复:D_max=max(Du,Dv)。
  s=1 典型参数零回归(test_scale 全绿)。

### 🟡 B7【已修复】图案缩放在 mesh 路径不生效 + steps_done 口径不一 — backend/numpy_backend.py
- 通用 grid/mesh 分支均不放大 `_n_sub`(s=2.5 时 mesh 演化慢 5 倍,两条路径行为分叉);
  fast 路径 `steps_done += n` 不含子步。修复:三分支统一 `n_eff = n·_n_sub`,计数含子步(真实推进量)。

### 🟡 B8【已修复】mesh 路径每步 `dict(params)` 拷贝使取向/流动缓存整体失效 — backend/numpy_backend.py + core/rule.py
- `_mesh_ext` 缓存挂在 params 上,后端每步浅拷贝 → 每 tick 重算 orientation_vectors_3d +
  aniso_edge_weights + velocity_field_3d(O(N·K) 级)。修复:mesh 分支直接传 params(规则层仅经
  setdefault 写缓存键);缓存命中增加 `centers` 同一性校验(id 地址被 GC 复用时防陈旧命中)。

### 🟡 B9【已修复】rhombille 生成器每六角发射成对重合菱形面 — core/meshgen.py
- 相邻六角各发一次同顶点集菱形(6 发,应为 3):单元翻倍、edge 邻接退化、z-fighting。
  修复:只发 k∈{0,2,4}(k+3 方向由邻居补全,每边恰一次);回归:4x4 期望 96 三角形。

### 🟡 B10【已修复】半拉格朗日 wrap 模式最后一格带不满足周期插值 — core/ops.py
- x0=n0-1 时 x1 应回绕到 0,原 clamp 截断致跨缝平流停滞。修复:wrap 分支 `(x0+1)%n0`。

### 🟡 B11【已修复】顶点凹凸无度数相关稳定防护 — ui/operators.py
- 非归一化图拉普拉斯要求 dt·D·2·deg_max ≤ 1,真实网格 deg 8~20 时默认参数即超限,局部失稳被 clip 成饱和块。
- 修复:入口按 `2·D_max·dt·deg_max/0.9` 自动子步(numpy 与 numba 路径同口径,子步数入报告文案);
  顺带 foreach_get/set 替换逐顶点 Python 循环(10 万顶点级从秒级到毫秒级)。

### 🟢 B12【已修复】杂项正确性
- `field3d.GrayScottRule3D`:补浓度 clip(与 2D 同口径)+ wrap 读 params;volume_adapter 调用侧双 clip 无害。
- `vertex_rd.faces_to_edges`:空 faces 返回 (0,2) 防下游 IndexError。
- `formula.py`:重复 delta 左值解析期拒绝(原静默覆盖);`describe_parameters` 补齐 4 元组契约。
- `fast_ops.py`:缓冲区别名检查 `is` → `np.shares_memory`(可发现视图共享)。
- `vtk_writer.py`:write_vti 数组尺寸≠nx·ny·nz 抛错(原静默写出非法文件),支持 (nx,ny,nz);
  vtu 化学量计数优先取 rd_meta。测试参数名 `tmpdir` 撞 pytest fixture 改名;oil_water 断言风格修正。

## 三、性能

### 🟡 C1【已修复】mesh_adapter 写路径每帧重建 bmesh + 逐元素写属性 — adapters/mesh_adapter.py
- 原 `write_named_attribute`/`_face_to_vertex_values` 每次显示更新各建一次 bmesh+三角化
  (每帧 ≥2 次全网格三角化)+ face×loop 双层 Python 循环 + 逐元素 bpy 属性赋值——RD 预览的主要 CPU 瓶颈。
- 修复:`_tri_topo` 拓扑快照缓存((mesh 名, 顶点数, 面数) 失效;纯拓扑量与场数据无关),面积由顶点坐标
  现算(雕塑移动顶点自动跟随),`np.add.at` 散射聚合,`foreach_set` 批量写属性/颜色。
- 顺带修复一个潜伏缺陷:原 `index_update()` 会重编全部活面索引,混合多边形网格(含四边/n-gon)下
  face_map 原面索引被覆盖导致映射错位;现改为在 index_update 前取原面索引。
- 另:`mesh_to_field` 经 `MeshField(adjacency=...)` 注入预计算邻接(原构建两遍,O(F) 纯 Python)。

### 🟡 C2【已修复】面板 draw() 每帧 O(F) 求和 + Voxel Remesh 作用对象错误 — ui/panels.py
- 面数/面积估算逐面 Python 求和跑在每次 UI 重绘;`box.operator("object.voxel_remesh")` 作用于**活动物体**
  而非①区目标对象——活动物体不是目标网格时会把无关对象不可逆重网格化。
- 修复:估算结果按拓扑键缓存;"一键 Voxel Remesh" 改用 `ready.remesh_copy`(目标对象、非破坏副本)。

### 🟡 C3【已修复】画笔 grid 模式忽略 Image Editor 缩放/平移 — ui/operators.py
- 鼠标→场坐标按区域线性映射,缩放视图后落笔错位。修复:优先 `view2d.region_to_view`(越界不落笔),
  无 view2d 时退回旧映射。

### 🟢 C4【已修复】零散性能项
- `RD_OT_update_display` 全部区域 tag_redraw → 限定 VIEW_3D/IMAGE_EDITOR;
- pattern_map 图像写入 `img.pixels.foreach_set`(原切片赋值走 Python 列表);
- bmesh 顶点坐标提取(画笔/网格预处理/顶点凹凸)统一 `foreach_get`;
- `_show_map` 尺寸一致时不再 `img.scale`;
- 路径:vtk_xml 单次解析(原 read_file 整树解析两遍)。

## 四、测试与工程化

### 🔴 D1【已修复】约半数测试"只打印不断言",pytest 下永不可能失败
- 波及:test_formula / test_m2_modules / test_mesh_quality / test_review_fixes / test_systems /
  test_vertex_rd(check() 模式)、test_numba_backend / test_pattern_import(打印 PASS/FAIL)、
  test_vtk_io(93 文件回归只打印)。readme"测试统一接入 Actions"对这半数是绿洗。
- 修复:全部补真断言(`assert fail == 0` / 逐检查 assert);新增 `tests/test_vtk_hardening.py`
  (5 例)锚定安全修复。全套 65 passed / 2 skipped(无 Ready patterns 目录时按设计跳过)。

### 🟡 D2【已修复】run.py 与 pytest 双轨断言已实质漂移
- run.py 内联 t1~t10 与 test_core.py 各自演化(容差/断言强度已分叉)。修复:run.py 重写为薄运行器
  (优先 pytest 同口径,无 pytest 时退化为逐模块调用,不再复制断言)。

### 🟡 D3【已修复】CI 依赖不钉扎、单平台单版本、无缓存
- 三次"依赖失败"的故障模式未被结构性消除;numpy 测试跑在 py3.12 与目标运行时(3.11)不一致;
  manifest 声明 4.2 最低支持但 bpy 只测 4.5。修复:`tests/constraints.txt` 钉扎(numpy/pytest)、
  `cache: pip`、bpy 4.2.*+4.5.* 矩阵、py3.11 对齐、concurrency + timeout-minutes。
  (CI 两个 job 均为真跑无空转——这点原实现就是对的。)

### 🟡 D4【已修复】打包与仓库卫生
- manifest 增排 `docs/`(19 份内部报告进用户扩展包)、`web/_orig/`、`web/_orig_rdtool.html`(死副本,
  ~1MB 死重);保留 `web/reaction-diffusion.html`(面板按钮运行时引用)与 `web/rdtool.html`(已修复)。
- `.gitignore` 增 `dist/`、`*.zip`(本地打包产物)。
- `build_rdtool_lm.py`:Windows 绝对路径参数化为 `--src/--out`(原脚本在 Linux 上会创建名为
  `C:\Users\...` 的垃圾目录),模板与已发布 HTML 同步(见 B2)。

### 🟢 D5【已修复】测试卫生
- test_grow3d 恒真断言删除(`X or True` 永真)、numba 计时断言放宽 1.5 倍容差(CI 共享 runner 易碎)。

## 五、遗留建议(本次不实施,理由附)

| 项 | 位置 | 建议 | 不实施理由 |
|---|---|---|---|
| E1 OilWater 网格版忽略 `wrap` | core/rule.py | 实现 clamp 版邻域或 UI 禁用开关 | 触碰守恒算法,需真机验证;行为变化应独立提交 |
| E2 空间变系数各向异性 collocated 格式 α>0.707 局部反扩散 | core/ops.py | 改通量形式(面权平均) | 数学等价改写需数值对照实验;已修正 docstring 声明并注明适用条件,clip 兜底 |
| E3 `laplacian_9`、`compute_backend._probe_available` 假探测、`uv_bake` FragmentRDBackend 着色器不可编译、Recorder/fragment 死代码 | core / backend / adapters | 真实探测(最小 compute shader)或删除 | GPU 路径无法在本环境验证,盲改风险大于收益 |
| E4 `rdtool.html`(W1 插件同口径工具)为孤儿文件 | web | 二选一:修好并让操作符指向它,或删除 | 产品决策(操作符现指向 rdtool-orig,与 readme 一致);refact bug 已修,文件可用 |
| E5 `style_map` 导出键 Blender 端无消费者 | build_rdtool_lm.py | 导出注释明示"仅记录"或实现空间调制 | 依赖 E2/新能力,属功能演进 |
| E6 SmoothLife FFT 内核与 Rafler 语义不符(死代码) | core/fast_ops.py | 修正或删除 | 无调用方,修改无验证手段 |
| E7 pattern_map 缓存文件名用 str() 拼接 | presets/pattern_map.py | 改 hashlib 摘要 | 仅影响文件名美观,功能正确 |
| E8 密度缓存不感知顶点位置编辑 | adapters/mesh_adapter.py | 缓存键加入坐标指纹 | 诊断性提示,低危 |

## 六、验证记录

- `pytest tests -q`:**65 passed, 2 skipped**(skip=本机无 Ready patterns 目录,CI 有)。
- 全部改动文件 `py_compile` 通过;两个网页工具全部内联 JS 过 `node --check`。
- 行为变更对照:new flow 语义下 `test_flow_velocity_bounded_and_advects`(模长<1)、
  `test_flow_genuinely_alters_field`(平流生效)、前后端一致性测试均绿;
  `test_both_combined_finite` 参数重标定过程与依据见 B5。
- 版本:bl_info 与 manifest 同步升至 **0.1.2**。
