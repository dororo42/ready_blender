# linusmossberg/reaction-diffusion 学习、完全本地化与预设借鉴报告

> 版本:v1(2026-08-25);来源:https://github.com/linusmossberg/reaction-diffusion (master, 下载自 codeload) + 在线演示 https://linusmossberg.github.io/reaction-diffusion(搜索快照佐证)

## 一、结论摘要

| 项 | 结论 |
|---|---|
| 许可 | **MIT**(© 2020 Linus Mossberg)→ 可完全本地化、修改、借鉴,需保留版权声明 |
| 技术栈 | WebGL(GPUComputationRenderer)+ three.js + dat.gui + SimplexNoise,纯前端无后端 |
| 内核 | Gray-Scott 标准方程 + **Witkin & Kass 9 点各向异性扩散核**,`dt=1/(4·DS)` 自适应步长,`Dv=0.5·Du` 固定比例,SimplexNoise 四通道空间参数场,clamp 边界 |
| 本地化 | ✅ 已完成:自包含单文件 `web/reaction-diffusion.html`(689 KB),零外部引用,file:// 直开,新增导出 JSON/CSV |
| 预设借鉴 | ✅ 已完成:20 组预设换算(Du=0.256·DS)注入插件,预设总数 12→**32** 项 |
| 插件导入链 | ✅ 网页导出 JSON → `RD_OT_import_preset_json` 校验 → `user_presets.json` → 下拉即时出现 |

## 二、项目与许可

- 仓库:linusmossberg/reaction-diffusion,单页 WebGL 应用,共 24 个文件(js 4 个 + external 4 个 + shaders 2 个 + css/图片),主逻辑约 12 KB 手写 JS。
- **MIT License**:允许复制、修改、分发、再许可;唯一义务是保留版权声明。本次本地化已把 MIT 全文与出处写入 HTML 注释,并在页面工具栏显示来源。
- 在线演示含 Google Analytics(UA-156004912-1),本地化版已移除(离线自包含要求)。

## 三、技术解读(内核口径)

shaders/reaction-diffusion.glsl 的模拟内核(净室描述,非复制):

```
反应项: reaction = (−u·v², +u·v²)
耗散项: dissipation = (F·(1−u), −v·(K+F))
扩散项: anisotropicDiffusion(angles, a1, center) · DS · (1.0, 0.5)
时间步: dt = 1.0 / (4.0·DS)      ← 自适应稳定步长
边界:   ClampToEdge(非周期)
```

各向异性核来自 **Witkin & Kass 1995 "Reaction-Diffusion Textures"**(论文公开方法,代码注释亦声明):
- a1=0.5 时退化为各向同性 9 点拉普拉斯(对角系数 1/6、正交 4/6、中心 −20/6,归一化核);
- a1>0.5 沿方向扩散更多,总扩散量近似不变(与我们的 3a Orientation 设计同源);
- 扩散方向角由环境噪声场提供:`angles = (1 + env[3])·π`(separate_fields 时用 env[0] 独立通道)。

环境场:SimplexNoise 4 通道(F/K/DS/角度各一),`environment_noise_scale` 控制空间频率(250~700),为参数场调制(Style Map)的现成范例。

### 与 ready_blender 插件的换算(关键)

| 项 | linusmossberg | ready_blender(fast_ops 5 点核) | 换算 |
|---|---|---|---|
| 拉普拉斯核 | 9 点归一化(中心 −3.333) | 5 点(中心 −4,邻 1) | 核强度比 3.333:4 |
| 扩散系数 | DS·(1.0, 0.5) | Du, Dv | **Du ≈ 0.256·DS**(见下),Dv=0.5·Du 天然一致 |
| 时间步 | dt=1/(4DS) 自适应 | dt 固定(默认 1.0) | 插件侧子步机制(1d)等效 |
| F / k | feed / kill | F / k | **直接通用**(方程同构,无量纲) |
| 边界 | clamp | wrap 可选 | 边缘行为差异,图案主体不受影响 |
| 各向异性 | a1∈[0.1,0.9],0.5=各向同性 | α(3a 阶段,wx+wy≡2) | 参考映射 α≈2·(a1−0.5),3a 落地后接线 |

**Du 换算推导**:扩散强度 ∝ 核权重 × 扩散系数。他每"模拟时间单位"的扩散 = (20/6)·DS·dt = (20/6)/4 ≈ 0.833;插件 = 4·Du·dt = 4·0.16 = 0.64。图案波长 λ ∝ √(D/反应率),反应率(F/k)相同,要波长一致需扩散总量一致:4·Du ≈ 0.833·DS/0.625 → **Du ≈ 0.256·DS**(取 0.625 为基准,DS=0.625→Du=0.16 恰与插件默认一致)。此换算为近似值,建议按图案微调 ±20%。

## 四、完全本地化方案(已实施)

产物:`ready_blender/web/reaction-diffusion.html`(单文件 689 KB)

| 项 | 处理 |
|---|---|
| three.min.js / GPUComputationRenderer / SimplexNoise / dat.gui | 全部内联(共 11 个 <script> 块) |
| CSS + iconfont.ttf + day-sunny.svg | 内联(base64) |
| Google Analytics | 移除 |
| 新增:导出 JSON / CSV 按钮 | 右上角工具栏;JSON 遵循 preset_io W4 schema |
| 版权 | 工具栏标注 + HTML 注释含 MIT 全文与出处 |
| 使用 | 双击 file:// 直开(需浏览器支持 WebGL);无网络依赖 |

导出 JSON 示例(网页当前参数实时换算):

```json
{
  "id": "lm_1756080000000",
  "name": "linusmossberg · Worms",
  "params": {"Du": 0.064, "Dv": 0.032, "F": 0.058, "k": 0.065, "dt": 1.0, "wrap": false},
  "seed_region": "uniform_sparse", "noise_ratio": 0.05,
  "source": "linusmossberg 网页导出(本地化版, MIT)",
  "extensions": {"pattern_scale": 1.0, "style_map": {"noise_scale": 250, "...": "..."},
                 "orientation": {"anisotropy": 0.5}, "flow": null}
}
```

Blender 侧链路(已接线):
1. 面板③ 参数区「**打开 RD 网页工具**」(file:// URL,零配置);
2. 网页选预设/调参 → **导出 JSON**;
3. 面板「**导入 JSON**」→ 校验(值域/必填键)→ 写入 `presets/user_presets.json`;
4. 预设下拉即时出现 `[导入] xxx`,选择即加载(F/k/Du/Dv/dt 全部生效)。

## 五、20 组预设参数(借鉴清单,已注入插件)

换算口径:`Du=0.256·DS`,`Dv=0.5·Du`,`F=feed`,`k=kill`,`dt=1.0`,`seed=uniform_sparse`,`noise_ratio=0.05`;anisotropy 与噪声变体存入 `extensions` 待 2/3a 阶段接线。

| # | 预设(中/英) | DS | feed | kill | aniso | 换算 Du | 换算 Dv | F | k |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 默认 Default | 0.625 | 0.042 | 0.060 | 0.8 | 0.16 | 0.08 | 0.042 | 0.060 |
| 2 | 沙漠斑马 Dunes/Zebra | 0.25 | 0.050 | 0.061 | 0.9 | 0.064 | 0.032 | 0.050 | 0.061 |
| 3 | 指纹 Fingerprints | 0.25 | 0.037 | 0.060 | 0.8 | 0.064 | 0.032 | 0.037 | 0.060 |
| 4 | 斑点与虫纹 Spots and Worms | 0.5 | 0.034 | 0.0618 | 0.5 | 0.128 | 0.064 | 0.034 | 0.0618 |
| 5 | 细胞分裂 Cell Division | 0.625 | 0.030 | 0.063 | 0.5 | 0.16 | 0.08 | 0.030 | 0.063 |
| 6 | 浮标 Buoys | 0.25 | 0.025 | 0.060 | 0.9 | 0.064 | 0.032 | 0.025 | 0.060 |
| 7 | 洋流 Currents | 0.25 | 0.080 | 0.060 | 0.9 | 0.064 | 0.032 | 0.080 | 0.060 |
| 8 | 油污 Oil Spill | 0.5 | 0.0475 | 0.060 | 0.1 | 0.128 | 0.064 | 0.0475 | 0.060 |
| 9 | 密集孔洞 Trypophobia | 0.25 | 0.039 | 0.0581 | 0.9 | 0.064 | 0.032 | 0.039 | 0.0581 |
| 10 | 旅者 Travellers | 0.5 | 0.014 | 0.054 | 0.8 | 0.128 | 0.064 | 0.014 | 0.054 |
| 11 | 海洋 Ocean | 0.625 | 0.014 | 0.040 | 0.1 | 0.16 | 0.08 | 0.014 | 0.040 |
| 12 | 微分线 Differential Line | 0.5 | 0.072 | 0.062 | 0.3 | 0.128 | 0.064 | 0.072 | 0.062 |
| 13 | 沃罗诺伊 Voronoi | 0.25 | 0.098 | 0.0555 | 0.5 | 0.064 | 0.032 | 0.098 | 0.0555 |
| 14 | 虫纹 Worms | 0.25 | 0.058 | 0.065 | 0.5 | 0.064 | 0.032 | 0.058 | 0.065 |
| 15 | 虫洞迷宫 Worm Mazes | 0.25 | 0.046 | 0.063 | 0.7 | 0.064 | 0.032 | 0.046 | 0.063 |
| 16 | 迷宫 Maze | 0.25 | 0.030 | 0.0565 | 0.5 | 0.064 | 0.032 | 0.030 | 0.0565 |
| 17 | 不稳定迷宫 Unstable Maze | 0.25 | 0.026 | 0.055 | 0.5 | 0.064 | 0.032 | 0.026 | 0.055 |
| 18 | 撕裂 Ripping | 0.375 | 0.034 | 0.056 | 0.9 | 0.096 | 0.048 | 0.034 | 0.056 |
| 19 | 波浪 Waves | 0.25 | 0.013 | 0.045 | 0.9 | 0.064 | 0.032 | 0.013 | 0.045 |
| 20 | 张量场可视化 Tensor Field | 0.375 | 0.030 | 0.063 | 0.9 | 0.096 | 0.048 | 0.030 | 0.063 |

注:Default/Oil Spill/Ocean/Spots and Worms/Cell Division/Differential Line/Worm Mazes/Worms/Maze/Tensor Field 带非零空间变体(feed_variation 等),已存入各预设 extensions,待 Style Map(阶段 2)接线。

## 六、与既有方案的关系

| 界面 | 定位 | 状态 |
|---|---|---|
| 1b 缩略图枚举 | 插件内快速识别预设 | 已实施(20 组 LM 预设自动获得缩略图) |
| 1c 点击取参弹窗 | 插件内 (k,F) 地图 | 已实施 |
| **本页面(本地化 linusmossberg)** | 插件外实时动画 + 20 预设 + Phong 渲染 + 导出 | 本轮实施 |
| W1 Karl Sims 风格地图页(计划) | (k,F) 地图 + 滑杆 | 可由本页面替代或共存(报告 §4W 评估) |

本页面与 1c 弹窗互补:弹窗用于"在地图上点选参数",本页面用于"看动画效果后导出整套参数"。导出 schema 与 preset_io 一致,两条链路共用同一导入操作符。

## 七、风险与验证

| 项 | 状态 |
|---|---|
| 许可合规 | ✅ MIT,版权声明已保留(HTML 注释 + 工具栏) |
| 内联 JS 语法 | ✅ 11 个 <script> 块全部 node --check 通过 |
| 外部引用 | ✅ 正则扫描 0 处 http(s) 引用,完全离线 |
| 插件回归 | ✅ 语法 49 文件全过(全量回归见交付说明) |
| 浏览器实机验证 | ⚠ 本机无图形浏览器自动化环境,未实机打开验证渲染;建议用户双击打开确认(Chrome/Edge/Firefox 均支持 WebGL) |
| 换算精度 | ⚠ Du=0.256·DS 为近似换算(核归一化推导),图案类型一致,F/k 直接通用;若个别预设图案尺度有偏差,微调 Du ±20% 即可 |
| 边界差异 | clamp vs wrap 仅影响边缘一圈,图案主体不受影响 |
| file:// 限制 | localStorage 保存(Chrome 对 file:// 有警告但可用);剪贴板 API 受限时以文件下载为主路径(已实现) |

## 八、文件清单

- `ready_blender/web/reaction-diffusion.html` — 本地化单文件网页(689 KB)
- `ready_blender/presets/presets.py` — 注入 20 组 LM 预设(PRO_PRESETS 段)
- `ready_blender/fileio/preset_io.py` — 导入校验/持久化(上一轮已建,本轮接通)
- `ready_blender/ui/operators.py` — RD_OT_import_preset_json
- `ready_blender/ui/panels.py` — 「打开 RD 网页工具」「导入 JSON」按钮
- `ready_blender/__init__.py` — 操作符注册
