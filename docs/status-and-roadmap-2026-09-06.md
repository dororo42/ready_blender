# 状态报告与后续优化路线图(2026-09-06)

## 一、当前状态

### 代码与发布
- 工作树干净,本地 main 与 origin/main 完全同步(GitHub HEAD `ab93db6`)。
- 本轮落地的三个提交:
  - `6b3b3ba` feat:Orientation/Flow 接入 3D 网格;linusmossberg 预设移植;预设导入加固;
    previews 兼容降级;网页选参工具单文件化。
  - `ef6a796` fix:P1 操作符注册遗漏;顶点坐标 `foreach_get` 批量取;平流吞错留痕;
    文档串对齐;`.gitignore` 治理。
  - `ab93db6` docs:项目评估报告(见 `docs/project-evaluation-2026-09-06.md`)。
- 测试基线:核心 10/10 + 18 个独立测试文件全部通过(含 93 个 Ready pattern 的 VTK 回归)。

### 远程调试基础设施(全部验证通过)
| 组件 | 状态 |
|---|---|
| LAN 主机 Blender 4.5.12 | 在线;MCP 桥监听 0.0.0.0:9876,随 Blender 自启 |
| ready_blender(远端安装) | 与 GitHub HEAD 逐文件一致(40 文件整体同步),自检 `[]`,面板/操作符注册真机确认 |
| ZCode MCP 配置 | 工作区 `.zcode/config.json`(不入库),下个会话自动连接 `blender` 服务器 |
| 快速通道 `push_addon.py` | push(整体同步)/ reload(清 `__pycache__`)/ exec / ping,演练通过 |
| 安装器 | `rd_mcp_installer.zip`(补丁插件 + 自启脚本 + 一键安装),可重复用于新主机 |

### 遗留疑点(未改,待实测)
- 3D 取向场以 Y 轴为"竖直"(Blender 世界为 Z-up):需视觉实测确认是刻意对齐网页工具还是疏漏。
- `_mesh_ext_cache` 以 `id(verts)` 为 key 的理论碰撞风险(类级缓存)。

## 二、后续优化路线图

> **落地记录(2026-09-06 同日晚)**:近期①②与中期④-⑧已全部完成——
> ①判定实验揪出真 P1(取向/平流在面域路径用面索引取顶点数组,F≠N 必崩),
> 修复为面中心口径并回归;保留局部 Y 约定(3D 张量构造与 2D orientation_weights
> 同构;顶视图=网页工具竖直)。三角网格条纹相对取向轴与 2D 方格路径相反
> (mesh ∥ 轴 vs grid ⊥ 轴)记为基底差异,视觉终校准留待 rdtool 对照。
> ②面板真机冒烟 9/10 过(播放实测 ~800 步/秒 @960 面球体)。
> ④13 个模块级测试机械转为 pytest 函数式(62/62 绿)+ GitHub Actions
> (numpy 全量 + bpy4.5 无头冒烟)。⑤扩展缓存移入 params(热更存活/重建失效)。
> ⑥manifest maintainer=dororo42、构建排除 tools/.github、草稿归档 tools/dev。
> ⑦新增 4 项性质/稳定性测试。⑧粘贴导入 poll(剪贴板非 JSON 置灰,真机验证)。

### 近期(下一工作日)
1. **取向轴向真机判定**:用调试链路在远端跑 Orientation 各 kind,截图比对 2D 网页工具口径,决定 linear/circles 是否改 Z-up(改的话 vertex_rd.py 一处 + 文档)。
2. **面板全流程真机冒烟**:初始化 → 播放/步进 → 烘焙 → 导入/粘贴 JSON → 一键凹凸(GN/顶点),盯 4.5 的 deprecated 警告。
3. **凭据轮换**:本轮使用过的 GitHub PAT 建议撤销重建;git 身份已固定为仓库级配置。

### 中期(插件本体)
4. **测试统一**:迁移为 pytest 兼容函数式(消除模块级 `sys.exit` 导致的收集中断),`tests/run.py` 退化为薄包装;加 GitHub Actions:ubuntu 上 numpy 全量 + `blender -b --python` 启动自检冒烟。
5. **性能**:大网格 profile 面域→顶点映射与 graph_laplacian;`_mesh_ext_cache` 从类属性移到 engine 实例(消 id 复用碰撞);Numba 后端覆盖 aniso/advect 路径。
6. **发布合规**:manifest `maintainer = "TBD"` 补齐;移除已入库的 `web/simplehttpserver.exe`(6MB);根目录草稿脚本(`_scratch_check.py`/`benchmark_m0.py`/`save_pearson.py`)归档。
7. **3D 扩展数值验证**:aniso α∈[0,0.95] × dt × 网格质量的稳定性边界,补单测固定行为。
8. **UX 细节**:粘贴导入加 poll(剪贴板非 JSON 时禁用);report 信息统一双语。

### 长期
9. compute shader(GPU)后端重启(原计划暂缓项)。
10. extensions.blender.org 上架:净室声明材料化、审核口径截图与 tagline。
11. 调试链路产品化:上游贡献 blender-mcp 的 LAN 绑定开关(本项目的 0.0.0.0 补丁通用化);`push_addon.py` 与 MCP 工具整合。

## 三、调试链路使用速查
- 新会话:MCP 工具(`get_scene_info` / `execute_blender_code` 等,需带 `user_prompt` 参数)。
- 会话内快速通道:`uv run _tools/rd_debug/push_addon.py --host <LAN-IP> push|reload|exec|ping`。
- 新主机安装:拷 `rd_mcp_installer.zip` → 双击 `install_remote.bat` → 启动 Blender。
- 卸载:删远端 `scripts/addons/blender_mcp_lan.py` 与 `scripts/startup/blender_mcp_autostart.py`。
