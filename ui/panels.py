# -*- coding: utf-8 -*-
"""N 侧栏面板:按操作逻辑分步(模式→预处理→参数→运行→输出),2D/3D 分离。"""
import bpy


def _lang_is_zh():
    """按 Blender 界面语言判断是否为中文。"""
    try:
        prefs = bpy.context.preferences.view
        lang = getattr(prefs, "language", "en_US")
        if isinstance(lang, str):
            return lang.startswith("zh")
        return lang == "zh_CN"
    except Exception:
        try:
            locale = bpy.app.translations.locale or ""
            return locale.startswith("zh")
        except Exception:
            return False


def _L(zh, en):
    """中英双语标签:跟随 Blender 界面语言。"""
    return zh if _lang_is_zh() else en


import bpy


class RD_PT_main(bpy.types.Panel):
    bl_label = "Ready RD"
    bl_idname = "RD_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Ready"

    @staticmethod
    def _draw_accel(layout, settings):
        """加速区(grow3d 工作流与主流程共用)。"""
        box = layout.box()
        box.label(text=_L("加速", "Acceleration"), icon="TIME")
        box.prop(settings, "use_numba")
        try:
            from ..backend.numba_backend import numba_status
        except ImportError:
            from backend.numba_backend import numba_status
        available, msg = numba_status()
        icon = "CHECKMARK" if available else "ERROR"
        box.label(text=msg, icon=icon)
        if not available:
            box.label(text=_L("不勾选/未安装时自动用 numpy(结果一致,速度较慢)",
                              "Falls back to numpy (identical results)"), icon="INFO")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.ready_settings
        # 防1:启动自检失败时面板顶部提示(安装损坏早发现)
        try:
            _pkg = __package__ or ""
            _root = _pkg.rsplit(".", 1)[0] if _pkg.startswith("bl_ext.") else "ready_blender"
            _rb = __import__(_root, fromlist=["SELF_CHECK_ERRORS"])
            if _rb.SELF_CHECK_ERRORS:
                box = layout.box()
                box.label(text="插件安装损坏,部分功能不可用", icon="ERROR")
                box.label(text="请在偏好设置→扩展中重装 ready_blender")
        except Exception:
            pass
        try:
            from ..controller.engine import get_engine, EngineState
        except ImportError:
            from controller.engine import get_engine, EngineState
        engine = get_engine()

        # ── 步骤① 模式与对象 ──────────────────────────────
        box = layout.box()
        box.label(text=_L("① 模式", "① Domain"), icon="SCENE_DATA")
        box.prop(settings, "field_kind", expand=True)
        if settings.field_kind == "grow3d":
            # 3D 生长管道独立工作流:①模式(含管道参数)→②参数(自动填预设)→③生成
            # ②网格预处理/④初始条件画笔/⑤交互运行/⑥输出均不适用(一次性生成)
            box.label(text=_L("── 3D 生长(体素→等值面)──", "-- 3D Growth --"))
            box.prop(settings, "target_object")
            if settings.target_object is None:
                box.label(text=_L("未选网格时用活动物体;无网格则自由盒模式",
                                  "Uses active object; free-box if none"), icon="INFO")
            _row = box.row(align=True)
            _row.prop(settings, "grow3d_size")
            _row.prop(settings, "grow3d_steps")
            box.prop(settings, "grow3d_threshold")
            box.prop(settings, "rng_seed")
            box.label(text=_L("选中网格体为生长边界(内部求解,输出对齐原网格);"
                              "无网格时自由盒居中输出",
                              "Selected mesh = growth boundary; free-box if none"),
                      icon="INFO")
            # ── grow3d 参数(切换模式时已自动填入文献口径) ──
            box = layout.box()
            box.label(text=_L("② 参数(Gray-Scott)", "② Parameters"), icon="OPTIONS")
            _row = box.row(align=True)
            _row.prop(settings, "param_Du")
            _row.prop(settings, "param_Dv")
            _row = box.row(align=True)
            _row.prop(settings, "param_F")
            _row.prop(settings, "param_k")
            box.prop(settings, "param_dt")
            box.label(text=_L("预设已自动填入:Du=0.082 Dv=0.041 F=0.035 k=0.064"
                              "(grayscott_3D 文献口径)",
                              "Preset auto-filled: Du=0.082 Dv=0.041 F=0.035 k=0.064"),
                      icon="INFO")
            # ── grow3d 生成 ──
            box = layout.box()
            box.label(text=_L("③ 生成", "③ Generate"), icon="PLAY")
            box.operator("ready.grow3d_pipeline",
                         text=_L("生成 3D 生长网格", "Generate 3D Growth Mesh"),
                         icon="MESH_CUBE")
            box.label(text=_L("等值面为 Surface Nets 光滑提取",
                              "Smooth Surface Nets extraction"), icon="INFO")
            self._draw_accel(layout, settings)
            return
        box.prop(settings, "system_enum")
        if settings.field_kind == "grid":
            box.label(text=_L("── 2D 规则网格 ──", "-- 2D Grid --"))
            box.prop(settings, "grid_size")
            box.prop(settings, "grid_wrap")
            box.label(text=_L("结果显示在 Image Editor(无需摄像机)", "Shown in Image Editor (no camera needed)"), icon="INFO")
        else:
            box.label(text=_L("── 3D 网格 ──", "-- 3D Mesh --"))
            box.prop(settings, "target_object")
            if settings.target_object is None:
                box.label(text=_L("未选目标时默认使用当前活动物体", "Uses active object when unset"), icon="INFO")

        # ── 步骤② 网格预处理(仅 3D)────────────────────────
        if settings.field_kind == "mesh":
            box = layout.box()
            box.label(text=_L("② 网格预处理", "② Mesh Prep"), icon="MOD_BUILD")
            box.prop(settings, "mesh_min_angle")
            box.prop(settings, "mesh_target_density")
            row = box.row(align=True)
            row.operator("ready.mesh_prep", text=_L("质量检查", "Quality Check"))
            row.operator("ready.mesh_triangulate_copy", text=_L("三角化副本", "Triangulate Copy"))
            row2 = box.row(align=True)
            row2.prop(settings, "use_subdivide", text=_L("细分网格", "Subdivide"))
            row2.prop(settings, "subdivide_levels", text=_L("级别", "Levels"))
            if settings.target_object is not None:
                _mesh = settings.target_object.data
                _cur_tri = sum(max(len(p.vertices) - 2, 1) for p in _mesh.polygons)
                _est = _cur_tri * (4 ** settings.subdivide_levels)
                box.label(text=_L(f"当前面数 {_cur_tri} → 预估细分后 {_est}", f"Faces {_cur_tri} → est. after subdiv {_est}"))
                if settings.use_subdivide:
                    box.operator("ready.subdivide_copy", text=_L("生成细分副本", "Subdivide Copy"), icon="MOD_SUBSURF")
            box.separator()
            row3 = box.row(align=True)
            row3.prop(settings, "use_remesh", text=_L("Remesh 网格", "Remesh Mesh"))
            row3.prop(settings, "remesh_target_faces", text=_L("目标面数", "Target Faces"))
            if settings.target_object is not None and settings.use_remesh:
                _area = sum(poly.area for poly in settings.target_object.data.polygons)
                _vox = (_area / max(settings.remesh_target_faces, 1)) ** 0.5 * 1.2
                box.label(text=_L(f"预估 voxel 尺寸 {_vox:.4f}", f"Est. voxel size {_vox:.4f}"))
                box.operator("ready.remesh_copy", text=_L("生成 Remesh 副本", "Remesh Copy"), icon="MOD_REMESH")
            try:
                from ..adapters.mesh_adapter import suggest_remesh_cached
            except ImportError:
                from adapters.mesh_adapter import suggest_remesh_cached
            if settings.target_object is not None:
                need, msg = suggest_remesh_cached(settings.target_object, settings.cv_threshold)
                if need:
                    box.alert = True
                    box.label(text=msg[:60], icon="ERROR")
                    if len(msg) > 60:
                        box.label(text=msg[60:])
                    box.operator("object.voxel_remesh", text=_L("一键 Voxel Remesh", "Voxel Remesh"))
            if settings.mesh_report_text:
                box.separator()
                sub = box.box()
                sub.label(text=f"类别 {settings.mesh_report_category}")
                sub.label(text=f"顶点 {settings.mesh_report_n_verts} | 面 {settings.mesh_report_n_faces}")
                sub.label(text=f"边长极差 {settings.mesh_report_edge_ratio:.1f} | 狭长 {settings.mesh_report_sliver*100:.1f}% | 面积CV {settings.mesh_report_cv:.2f}")
                sub.label(text=f"面密度 {settings.mesh_report_density:.1f}(目标≥{settings.mesh_target_density:.0f})")
                sub.label(text=f"均匀性 {'✓' if settings.mesh_report_uniform_ok else '✗'} | 数量 {'✓' if settings.mesh_report_quantity_ok else '✗'}")
                sub.label(text=settings.mesh_report_text[:80])
                if len(settings.mesh_report_text) > 80:
                    sub.label(text=settings.mesh_report_text[80:])

        # ── 步骤③ 参数 → 初始化 ────────────────────────────
        box = layout.box()
        box.label(text=_L("③ 参数", "③ Parameters"), icon="OPTIONS")
        _row = box.row(align=True)
        _row.operator("ready.preset_load", text=_L("加载预设 / 参数变体", "Load Preset / Variant"))
        _row.operator("ready.import_preset_json", text=_L("导入 JSON", "Import JSON"), icon="IMPORT")
        _row.operator("ready.paste_preset_json", text=_L("粘贴导入", "Paste JSON"), icon="PASTEDOWN")
        try:
            import urllib.parse
            import os as _os
            _page = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                                  "web", "reaction-diffusion.html")
            if _os.path.exists(_page):
                _url = "file:///" + urllib.parse.quote(_page.replace("\\", "/"))
                _op = box.operator("wm.url_open", text=_L("打开 RD 网页工具", "Open RD Web Tool"), icon="URL")
                _op.url = _url
        except Exception:
            pass
        if settings.system_enum == "gray_scott" and settings.field_kind == "grid":
            # W1:RD 网页工具链路(浏览器选参 → 导出 JSON → 导入为用户预设)
            _row = box.row(align=True)
            _row.operator("ready.open_rdtool_web",
                          text=_L("RD 网页选参", "RD Web Tool"), icon="WORLD")
            _row.operator("ready.import_preset_json",
                          text=_L("导入 JSON 预设", "Import JSON Preset"), icon="IMPORT")
        if settings.system_enum == "gray_scott":
            _row = box.row(align=True)
            _row.prop(settings, "param_Du")
            _row.prop(settings, "param_Dv")
            _row = box.row(align=True)
            _row.prop(settings, "param_F")
            _row.prop(settings, "param_k")
            box.prop(settings, "param_dt")
            # 扩展参数(2D 与 3D 网格均生效;图案地图仅 2D)
            box.prop(settings, "pattern_scale")
            if settings.field_kind == "mesh":
                box.label(text=_L("图案缩放同样作用于网格(Du/Dv×s²,子步保护)",
                                  "Scale applies to mesh too (Du/Dv×s²)"), icon="INFO")
            else:
                box.label(text=_L("放大>1.25 时自动子步,耗时按比例增加",
                                  "Substeps auto-enabled above 1.25x"), icon="INFO")
            # W1 扩展参数:Orientation(各向异性扩散) + Flow(空间平流)
            _r = box.row(align=True)
            _r.prop(settings, "orientation_kind", text="Orientation")
            _r.prop(settings, "orientation_strength", text="强度")
            _r = box.row(align=True)
            _r.prop(settings, "flow_kind", text="Flow")
            _r.prop(settings, "flow_strength", text="强度")
            if settings.field_kind == "mesh":
                box.label(text=_L("网格上:取向=边方向投影权重,流动=顶点最近邻平流",
                                  "Mesh: orientation = edge weights, flow = vertex advection"), icon="INFO")
            if settings.field_kind == "grid":
                box.operator("ready.pattern_map_pick",
                             text=_L("从图案地图选择 (k,F)", "Pick (k,F) from Pattern Map"),
                             icon="IMAGE_REFERENCE")
        elif settings.system_enum == "oil_water":
            box.label(text=_L("参数固定(文献值): 排斥常数 0.7 · 时间步 0.05",
                              "Fixed (literature): repulsion 0.7, dt 0.05"), icon="INFO")
            if settings.field_kind == "mesh":
                box.label(text=_L("3D 网格:图邻域版(对称权重,质量守恒);"
                                  "纹理经⑥输出写顶点色/属性",
                                  "3D mesh: graph version; texture via ⑥ output"),
                          icon="INFO")
        else:
            box.prop(settings, "formula_variant")
            box.label(text=_L("变体为文献典型值", "Literature-typical variants"), icon="INFO")
        box.operator("ready.init", text=_L("初始化模拟", "Initialize"), icon="FILE_REFRESH")

        # ── 步骤④ 初始条件 / 画笔 ──────────────────────────
        box = layout.box()
        box.label(text=_L("④ 初始条件", "④ Initial"), icon="BRUSH_DATA")
        if settings.system_enum == "oil_water":
            # oil-water:初始化自动双场白噪声,种子/噪声比例不被读取 → 仅画笔相关
            box.label(text=_L("白噪声初始化(种子=⑥ 区随机种子);画笔可手动涂抹两相",
                              "White-noise init (seed = ⑥ RNG); brush paints either phase"),
                      icon="INFO")
        else:
            box.prop(settings, "seed_region")
            box.prop(settings, "noise_ratio")
        _row = box.row(align=True)
        _row.prop(settings, "brush_radius")
        _row.prop(settings, "brush_value")
        _row = box.row(align=True)
        _row.prop(settings, "brush_chemical", expand=True)
        box.operator("ready.brush", text=_L("画笔涂抹(需物体模式)", "Paint (Object Mode)"), icon="BRUSHES_ALL")
        box.operator("ready.reset", text=_L("重置初始条件", "Reset Initial"))
        if settings.field_kind == "grid":
            box.operator("ready.import_pattern", text=_L("导入 Pattern 为初始条件(.vti)",
                                                        "Import Pattern (.vti)"), icon="FILE_FOLDER")

        # ── 步骤⑤ 运行 ──────────────────────────────────────
        box = layout.box()
        box.label(text=_L("⑤ 运行", "⑤ Run"), icon="PLAY")
        state = engine.state
        state_label = {
            EngineState.IDLE: "IDLE", EngineState.RUNNING: "RUNNING",
            EngineState.PAUSED: "PAUSED", EngineState.NEEDS_REBUILD: "NEEDS_REBUILD",
            EngineState.STEPPING: "STEPPING",
        }.get(state, "?")
        box.label(text=f"状态 {state_label} | 步数 {engine.steps_done} | 实测 {engine.measured_speed:.0f} 步/秒")
        row = box.row(align=True)
        row.operator("ready.play", text=_L("播放", "Play"), icon="PLAY")
        row.operator("ready.pause", text=_L("暂停", "Pause"), icon="PAUSE")
        row.operator("ready.step", text=_L("步进", "Step"), icon="FF")
        box.prop(settings, "speed_steps_per_sec")
        box.prop(settings, "tick_steps")
        box.prop(settings, "tick_interval")
        box.prop(settings, "bake_steps")
        if settings.is_baking:
            box.prop(settings, "progress", text=_L("烘焙进度", "Bake Progress"))
            box.operator("ready.cancel_bake", text=_L("取消烘焙", "Cancel Bake"))
        else:
            box.operator("ready.bake", text=_L("烘焙 (全分辨率)", "Bake (Full Res)"))

        # ── 步骤⑥ 输出 / 显示 ──────────────────────────────
        box = layout.box()
        box.label(text=_L("⑥ 输出", "⑥ Output"), icon="IMAGE_DATA")
        box.prop(settings, "active_chemical")
        box.prop(settings, "colormap")
        box.prop(settings, "colormap_range")
        if settings.field_kind == "mesh":
            box.prop(settings, "output_mode")
            box.label(text=_L("顶点色/属性需视口着色切到顶点色或属性才可见", "Vertex color/attr visible in viewport shading"), icon="INFO")
            box.operator("ready.add_displacement_gn", text=_L("一键凹凸(几何节点修改器,非破坏)", "Add Bump (Geometry Nodes Modifier)"), icon="MOD_DISPLACE")
            box.prop(settings, "mesh_displacement_strength")
            if settings.system_enum != "oil_water":
                # 种子密度对 oil-water 无效(白噪声初始化不读取)
                box.prop(settings, "vertex_seed_ratio")
            box.prop(settings, "rng_seed")
            box.operator("ready.apply_vertex_displacement", text=_L("一键顶点凹凸(直接几何,可 Ctrl+Z)", "Vertex Displacement (Ctrl+Z undo)"), icon="MESH_DATA")
        # 加速选项(参考 Pro v6:面板底部可选,不勾选则 numpy;grow3d 工作流内亦复用)
        self._draw_accel(layout, settings)
        if engine.last_error:
            box.alert = True
            box.label(text=engine.last_error, icon="ERROR")
        box.operator("ready.update_display", text=_L("刷新显示", "Refresh Display"))


class RD_PT_image(bpy.types.Panel):
    """Image Editor 侧栏:2D 规则网格模式的完整工作区(模式/参数/初始化/运行/画笔/输出)。"""
    bl_label = "Ready RD (2D)"
    bl_idname = "RD_PT_image"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Ready"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.ready_settings
        try:
            from ..controller.engine import get_engine, EngineState
        except ImportError:
            from controller.engine import get_engine, EngineState
        engine = get_engine()

        box = layout.box()
        box.label(text=_L("2D 规则网格", "2D Grid"), icon="SCENE_DATA")
        box.prop(settings, "grid_size")
        box.prop(settings, "grid_wrap")

        box = layout.box()
        box.label(text=_L("参数", "Parameters"), icon="OPTIONS")
        box.operator("ready.preset_load", text=_L("加载预设 / 参数变体", "Load Preset / Variant"))
        box.prop(settings, "param_Du")
        box.prop(settings, "param_Dv")
        box.prop(settings, "param_F")
        box.prop(settings, "param_k")
        box.prop(settings, "param_dt")
        if settings.system_enum == "gray_scott":
            box.prop(settings, "pattern_scale")
            box.operator("ready.pattern_map_pick",
                         text=_L("从图案地图选择 (k,F)", "Pick (k,F) from Pattern Map"),
                         icon="IMAGE_REFERENCE")
        box.operator("ready.init", text=_L("初始化模拟", "Initialize"), icon="FILE_REFRESH")

        box = layout.box()
        box.label(text=_L("初始条件", "Initial"), icon="BRUSH_DATA")
        row = box.row(align=True)
        row.prop(settings, "brush_chemical", expand=True)
        box.prop(settings, "brush_radius")
        box.prop(settings, "brush_value")
        box.operator("ready.brush", text=_L("画笔涂抹(在本 Image Editor 直接画)", "Paint (in this Image Editor)"), icon="BRUSHES_ALL")
        box.operator("ready.reset", text=_L("重置初始条件", "Reset Initial"))

        box = layout.box()
        box.label(text=_L("运行", "Run"), icon="PLAY")
        state_label = {
            EngineState.IDLE: "IDLE", EngineState.RUNNING: "RUNNING",
            EngineState.PAUSED: "PAUSED", EngineState.NEEDS_REBUILD: "NEEDS_REBUILD",
            EngineState.STEPPING: "STEPPING",
        }.get(engine.state, "?")
        box.label(text=f"状态 {state_label} | 步数 {engine.steps_done} | 实测 {engine.measured_speed:.0f} 步/秒")
        row = box.row(align=True)
        row.operator("ready.play", text=_L("播放", "Play"), icon="PLAY")
        row.operator("ready.pause", text=_L("暂停", "Pause"), icon="PAUSE")
        row.operator("ready.step", text=_L("步进", "Step"), icon="FF")
        box.prop(settings, "speed_steps_per_sec")
        box.prop(settings, "bake_steps")
        if settings.is_baking:
            box.prop(settings, "progress", text=_L("烘焙进度", "Bake Progress"))
            box.operator("ready.cancel_bake", text=_L("取消烘焙", "Cancel Bake"))
        else:
            box.operator("ready.bake", text=_L("烘焙 (全分辨率)", "Bake (Full Res)"))

        box = layout.box()
        box.label(text=_L("输出", "Output"), icon="IMAGE_DATA")
        img = bpy.data.images.get("RD_preview")
        if img:
            layout.template_ID(context.space_data, "image")
            sp = getattr(context.space_data, "image", None)
            if sp is None or sp.name != "RD_preview":
                layout.label(text=_L("当前显示的不是 RD_preview", "Not RD_preview"), icon="INFO")
                box.operator("ready.update_display", text=_L("点此把 RD_preview 设为当前图像", "Set RD_preview as current image"))
        else:
            box.label(text=_L("尚无模拟图像:先初始化并播放", "No image: initialize & play first"), icon="INFO")
        box.prop(settings, "active_chemical")
        box.prop(settings, "colormap")
        box.prop(settings, "colormap_range")
        box.operator("ready.update_display", text=_L("刷新显示", "Refresh Display"))
        box.operator("ready.material_from_rd", text=_L("把 RD_preview 接到活动物体材质", "Apply RD texture to material"))
