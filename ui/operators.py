# -*- coding: utf-8 -*-
"""操作符:初始化/播放/暂停/步进/重置/烘焙/画笔/预设/导出。净室实现。

导入说明:跨包导入全部用守卫模式(包模式优先,顶层模式兜底)。
"""
import bpy
import numpy as np


def _imp_controller_engine():
    try:
        from ..controller.engine import get_engine
    except ImportError:
        from controller.engine import get_engine
    return get_engine


def _imp_controller_scheduler():
    try:
        from ..controller.scheduler import get_preview
    except ImportError:
        from controller.scheduler import get_preview
    return get_preview


def init_engine_from_settings(context):
    """从 Scene.ready_settings 构建引擎。支持内置 Gray-Scott 与公式系统(净室公式)。"""
    get_engine = _imp_controller_engine()
    try:
        from ..core.rule import GrayScottRule
    except ImportError:
        from core.rule import GrayScottRule
    try:
        from ..core.formula import FormulaRule
    except ImportError:
        from core.formula import FormulaRule
    try:
        from ..presets.presets import get_system
    except ImportError:
        from presets.presets import get_system

    settings = context.scene.ready_settings
    engine = get_engine()
    sys_def = get_system(settings.system_enum) or get_system("gray_scott")

    # ── 规则与参数 ──
    if sys_def["kind"] == "oil_water":
        try:
            from ..core.rule import OilWaterRule
        except ImportError:
            from core.rule import OilWaterRule
        engine.rule = OilWaterRule()
        engine.params = dict(sys_def["params"])
        engine.params["wrap"] = settings.grid_wrap
        chem_base = None  # 白噪声初始化,不用基底
        pulse_idx = None
        pulse_val = None
    elif sys_def["kind"] == "builtin":
        engine.rule = GrayScottRule()
        try:
            from ..core.parameter import scale_params
        except ImportError:
            from core.parameter import scale_params
        Du_eff, Dv_eff, dt_eff, n_sub = scale_params(
            settings.param_Du, settings.param_Dv, settings.param_dt,
            getattr(settings, "pattern_scale", 1.0))
        engine.params = {
            "Du": Du_eff, "Dv": Dv_eff,
            "F": settings.param_F, "k": settings.param_k,
            "dt": dt_eff, "wrap": settings.grid_wrap, "_n_sub": n_sub,
            "orientation_kind": getattr(settings, "orientation_kind", "none"),
            "orientation_strength": getattr(settings, "orientation_strength", 0.0),
            "flow_kind": getattr(settings, "flow_kind", "none"),
            "flow_strength": getattr(settings, "flow_strength", 0.0),
        }
        chem_base = (1.0, 0.0)
        pulse_idx = 1
        pulse_val = 1.0
    else:
        engine.rule = FormulaRule(sys_def["formula"])
        engine.params = dict(sys_def["params"])
        try:
            from ..presets.presets import get_variant
        except ImportError:
            from presets.presets import get_variant
        _v = get_variant(settings.system_enum, settings.formula_variant)
        if _v is not None:
            engine.params.update(_v["params"])
        engine.params["wrap"] = settings.grid_wrap
        chems = sys_def["chemicals"]
        base = sys_def["init"]["base"]
        chem_base = (float(base[chems[0]]), float(base[chems[1]]))
        pulse_idx = chems.index(sys_def["init"]["pulse_chem"])
        pulse_val = float(sys_def["init"]["pulse_value"])
    engine.field_kind = settings.field_kind
    rng = np.random.default_rng(42)

    if settings.field_kind == "grid":
        try:
            from ..core.field import RegularGridField
        except ImportError:
            from core.field import RegularGridField
        engine.fields = [
            RegularGridField((settings.grid_size, settings.grid_size),
                             wrap=settings.grid_wrap).data,
            RegularGridField((settings.grid_size, settings.grid_size),
                             wrap=settings.grid_wrap).data,
        ]
        if chem_base is None:
            # oil-water 初始条件:双场全域白噪声 [0,1](Agmon 2014;
            # 两相随机混合态,相分离由排斥动力学自行演化)
            _rng = np.random.default_rng(getattr(settings, "rng_seed", 42))
            engine.fields[0][:] = _rng.uniform(
                0, 1, engine.fields[0].shape).astype(np.float32)
            engine.fields[1][:] = _rng.uniform(
                0, 1, engine.fields[1].shape).astype(np.float32)
            engine.nbr = None
            engine.reset()
            return engine
        engine.fields[0][:] = chem_base[0]
        engine.fields[1][:] = chem_base[1]
        # F7 修复:初始条件接 seed_region + noise_ratio
        f = engine.fields[pulse_idx]
        if settings.seed_region == "global":
            # 全局稀疏种子:密度=Noise Ratio,满幅种子(与均匀稀疏同口径)
            sel = rng.random(f.shape) < settings.noise_ratio
            f[sel] += pulse_val
        elif settings.seed_region == "uniform_sparse":
            # 均匀稀疏种子:密度=种子密度属性(默认 5%,可调提高覆盖率)
            sel = rng.random(f.shape) < settings.vertex_seed_ratio
            f[sel] = f[sel] + pulse_val
        else:
            cx = settings.grid_size // 2
            s = settings.grid_size // 8
            yy, xx = np.mgrid[0:settings.grid_size, 0:settings.grid_size]
            if settings.seed_region == "center_disc":
                mask = (xx - cx) ** 2 + (yy - cx) ** 2 < (s * 1.4) ** 2
            else:  # center_square
                mask = (np.abs(xx - cx) < s) & (np.abs(yy - cx) < s)
            f[mask] += rng.uniform(0, 1, mask.sum()).astype(np.float32) * pulse_val
        engine.nbr = None
    else:
        obj = settings.target_object
        if obj is None:
            # 审查修复/目标模式:未选对象时默认当前活动物体
            obj = getattr(context.view_layer, "objects", None)
            obj = getattr(obj, "active", None) if obj is not None else None
        if obj is None or obj.type != "MESH":
            raise RuntimeError(
                "网格模式需要一个网格物体:请在 ① 区块选择目标网格,"
                "或先在场景中选中一个网格物体作为活动对象")
        # B2 修复:记录拓扑指纹,显示写入前校验
        topo = (len(obj.data.vertices), len(obj.data.polygons))
        try:
            from ..adapters.mesh_adapter import mesh_to_field
        except ImportError:
            from adapters.mesh_adapter import mesh_to_field
        mf = mesh_to_field(obj, kind="vertex")
        # 3D 扩展:顶点坐标(与 mf 顶点域索引一致)→ Orientation/Flow 用
        _mesh_verts = np.array([[v.co.x, v.co.y, v.co.z]
                                for v in obj.data.vertices], dtype=np.float32)
        if chem_base is None:
            # oil-water mesh 模式:面域双场白噪声(相分离由排斥动力学自行演化;
            # 图邻域版 Agmon 算法,见 core.rule.OilWaterRule._update_mesh)
            _rng = np.random.default_rng(getattr(settings, "rng_seed", 42))
            engine.fields = [
                _rng.uniform(0, 1, mf.data.shape[0]).astype(np.float32),
                _rng.uniform(0, 1, mf.data.shape[0]).astype(np.float32),
            ]
            engine.nbr = (mf.nbr_idx, mf.nbr_w)
            engine.mesh_info = {
                "n_cells": mf.data.shape[0], "max_k": mf.max_k, "avg_k": mf.avg_k,
                "faces": mf.faces, "obj": obj, "topo": topo,
            }
            engine.reset()
            return engine
        engine.fields = [
            np.full(mf.data.shape[0], chem_base[0], dtype=np.float32),
            np.full(mf.data.shape[0], chem_base[1], dtype=np.float32),
        ]
        if hasattr(engine, "params"):
            engine.params["mesh_verts"] = _mesh_verts
        # 初始条件:按 seed_region 选择扰动方式
        try:
            if settings.seed_region in ("uniform_sparse", "global"):
                # 均匀稀疏种子(种子密度属性)或全局稀疏(noise_ratio)
                ratio = (settings.vertex_seed_ratio if settings.seed_region == "uniform_sparse"
                         else settings.noise_ratio)
                _sel = rng.random(len(engine.fields[0])) < ratio
                engine.fields[pulse_idx][_sel] += pulse_val
            else:
                import bmesh as _bm
                _b = _bm.new()
                _b.from_mesh(obj.data)
                _bm.ops.triangulate(_b, faces=_b.faces[:])
                _verts = np.array([[v.co.x, v.co.y, v.co.z] for v in _b.verts],
                                  dtype=np.float32)
                _b.free()
                _centers = _verts[mf.faces].mean(axis=1)
                _c = _centers.mean(axis=0)
                _bb = _centers.max(axis=0) - _centers.min(axis=0)
                _r = max(float(np.linalg.norm(_bb)) * 0.25, 1e-6)
                _sel = ((_centers - _c) ** 2).sum(axis=1) < _r * _r
                if not _sel.any():
                    _sel = rng.random(len(_sel)) < settings.noise_ratio
                engine.fields[pulse_idx][_sel] += (
                    rng.uniform(0, 1, _sel.sum()).astype(np.float32) * pulse_val)
        except Exception:
            # O4 规范:用面数而非布尔数组长度
            n_cells = len(engine.fields[0])
            sel = rng.random(n_cells) < settings.noise_ratio
            engine.fields[pulse_idx][sel] += (
                rng.uniform(0, 1, sel.sum()).astype(np.float32) * pulse_val)
        engine.nbr = (mf.nbr_idx, mf.nbr_w)
        engine.mesh_info = {
            "n_cells": mf.data.shape[0], "max_k": mf.max_k, "avg_k": mf.avg_k,
            "faces": mf.faces, "obj": obj, "topo": topo,
        }
    engine.reset()
    engine.tick_steps = settings.tick_steps
    engine.tick_interval = settings.tick_interval
    return engine


class RD_OT_init(bpy.types.Operator):
    bl_idname = "ready.init"
    bl_label = "Init Simulation"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            init_engine_from_settings(context)
            self.report({"INFO"}, "Ready: 模拟已初始化")
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
        return {"FINISHED"}


class RD_OT_play(bpy.types.Operator):
    bl_idname = "ready.play"
    bl_label = "Play"

    def execute(self, context):
        get_engine = _imp_controller_engine()
        get_preview = _imp_controller_scheduler()
        engine = get_engine()
        if engine.rule is None:
            try:
                init_engine_from_settings(context)
            except RuntimeError as e:
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}
        engine.play()
        get_preview().start()
        return {"FINISHED"}


class RD_OT_pause(bpy.types.Operator):
    bl_idname = "ready.pause"
    bl_label = "Pause"

    def execute(self, context):
        get_engine = _imp_controller_engine()
        get_engine().pause()
        return {"FINISHED"}


class RD_OT_step(bpy.types.Operator):
    bl_idname = "ready.step"
    bl_label = "Step"

    def execute(self, context):
        get_engine = _imp_controller_engine()
        engine = get_engine()
        if engine.rule is None:
            try:
                init_engine_from_settings(context)
            except RuntimeError as e:
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}
        n = context.scene.ready_settings.tick_steps
        engine.step(n)
        RD_OT_update_display.run(context)
        return {"FINISHED"}


class RD_OT_reset(bpy.types.Operator):
    bl_idname = "ready.reset"
    bl_label = "Reset"

    def execute(self, context):
        get_preview = _imp_controller_scheduler()
        get_engine = _imp_controller_engine()
        get_preview().stop()
        try:
            init_engine_from_settings(context)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
        # 修复:重置后立即刷新显示(否则图像停留在旧状态,看起来"重置无效")
        get_engine().last_error = None
        RD_OT_update_display.run(context)
        return {"FINISHED"}


class RD_OT_import_pattern(bpy.types.Operator):
    """导入 Ready pattern(.vti)的化学品场作为 2D 网格初始条件。

    pattern 文件来自 Ready 开源生态(GollyGang/Ready),内含:
    两个化学量的初始场 + 规则类型与参数 + 文献描述。
    本算子只导入初始场;Gray-Scott 型 pattern 附带同步参数。
    """
    bl_idname = "ready.import_pattern"
    bl_label = "Import Pattern as Initial Condition"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.vti;*.vtu", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        try:
            from ..fileio.vtk_xml import read_file
        except ImportError:
            from fileio.vtk_xml import read_file
        try:
            r = read_file(self.filepath)
        except Exception as e:
            self.report({"ERROR"}, f"pattern 解析失败: {e}")
            return {"CANCELLED"}
        # 仅支持 2D ImageData(规则网格);3D/1D/vtu 不支持
        if r["type"] != "ImageData" or r["dimensions"][2] != 1:
            self.report({"ERROR"}, "仅支持 2D 网格型 pattern(.vti, Z 维=1);"
                                   "3D 体素与 .vtu 网格型暂不支持")
            return {"CANCELLED"}
        if r["dimensions"][1] < 2:
            self.report({"ERROR"}, "1D pattern(Y 维=1)不支持——无空间图案意义,已按需舍弃")
            return {"CANCELLED"}
        w, h = int(r["dimensions"][0]), int(r["dimensions"][1])
        pd = r["point_data"]
        # 化学量提取(Ready pattern 两种布局):
        #  A) 两个独立 DataArray(键名 a/b 或 u/v);
        #  B) 单个多列数组(如 'Scalars_' shape=(N,2),列=化学量)
        a_flat = b_flat = None
        for ka, kb in (("a", "b"), ("u", "v")):
            if ka in pd and kb in pd:
                a_flat, b_flat = pd[ka], pd[kb]
                break
        if a_flat is None:
            multi = [v for v in pd.values()
                     if hasattr(v, "ndim") and v.ndim == 2 and v.shape[1] >= 2]
            if multi:
                a_flat, b_flat = multi[0][:, 0], multi[0][:, 1]
        if a_flat is None:
            flat_keys = [k for k in pd if hasattr(pd[k], "ndim") and pd[k].ndim == 1]
            if len(flat_keys) >= 2:
                a_flat, b_flat = pd[flat_keys[0]], pd[flat_keys[1]]
        if a_flat is None:
            self.report({"ERROR"}, f"pattern 缺少两个化学量场(point_data 键: {list(pd.keys())})")
            return {"CANCELLED"}
        a = np.asarray(a_flat, dtype=np.float32).reshape(h, w)
        b = np.asarray(b_flat, dtype=np.float32).reshape(h, w)

        s = context.scene.ready_settings
        # Gray-Scott 标准参数型 pattern:参数同步到 settings(init 会读)。
        # 覆盖两类:内置型(3 个)与公式型 Gray-Scott(13 个,其中五参数齐全
        # 且无调制参数的 5 个)——两者参数命名一致(D_a/D_b/F/k/timestep)。
        rd = r.get("rd", {})
        msgs = []
        p = rd.get("parameters", {})
        is_gs = "Gray" in (rd.get("rule_name") or "") or "grayscott" in self.filepath.lower()
        gs_std = ({"timestep", "D_a", "D_b", "F", "k"} <= set(p.keys())
                  and set(p.keys()) <= {"timestep", "D_a", "D_b", "F", "k"})
        if is_gs and gs_std:
            # 切回 Gray-Scott 系统(防在公式系统下导入 GS pattern 的口径不一致)
            if s.system_enum != "gray_scott":
                s.system_enum = "gray_scott"
                msgs.append("已切换系统为 Gray-Scott")
            if "F" in p: s.param_F = float(p["F"])
            if "k" in p: s.param_k = float(p["k"])
            if "D_a" in p: s.param_Du = float(p["D_a"])
            if "D_b" in p: s.param_Dv = float(p["D_b"])
            if "timestep" in p: s.param_dt = float(p["timestep"])
            msgs.append("Gray-Scott 参数已同步")
        elif rd.get("rule_type"):
            msgs.append(f"规则 {rd.get('rule_name') or rd.get('rule_type')}"
                        f"参数未同步(请手动切换①区系统)")
        # 切到 grid 模式并以 pattern 尺寸重建引擎(随后的场覆盖会替换种子)
        s.field_kind = "grid"
        try:
            init_engine_from_settings(context)
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        get_engine = _imp_controller_engine()
        engine = get_engine()
        try:
            from ..core.field import RegularGridField
        except ImportError:
            from core.field import RegularGridField
        fa = RegularGridField((h, w), wrap=s.grid_wrap)
        fb = RegularGridField((h, w), wrap=s.grid_wrap)
        # 生成器型 pattern(初始场全 0,Ready 靠其内置生成器现场播种):
        # 93 个官方 pattern 中 61 个属此类。全 0 场对 Gray-Scott 是死态
        # (a=0 非有效基底)——GS 型自动回退为基底+中央种子,导入即可播放;
        # 公式型系统基底各异,提示手动处理。
        if float(np.abs(a).max()) == 0.0 and float(np.abs(b).max()) == 0.0:
            if engine.rule is not None and hasattr(engine.rule, "update") and \
                    type(engine.rule).__name__ == "GrayScottRule":
                fa.data[:] = 1.0
                fb.data[:] = 0.0
                _s = max(h, w) // 8
                _cx, _cy = w // 2, h // 2
                fb.data[_cy - _s:_cy + _s, _cx - _s:_cx + _s] = 1.0
                msgs.append("初始场为空(生成器型):已自动改用基底 a=1/b=0 + 中央种子")
            else:
                fa.data[:] = a
                fb.data[:] = b
                msgs.append("初始场为空(生成器型):请画笔涂抹或重置后再播放")
        else:
            fa.data[:] = a
            fb.data[:] = b
        engine.fields = [fa.data, fb.data]
        engine.mesh_info = None
        engine.nbr = None
        engine.reset()
        engine.last_error = None
        RD_OT_update_display.run(context)
        self.report({"INFO"}, f"导入成功 {w}x{h}" + (";".join([""] + msgs) if msgs else ""))
        return {"FINISHED"}


class RD_OT_bake(bpy.types.Operator):
    bl_idname = "ready.bake"
    bl_label = "Bake"
    bl_options = {"REGISTER"}

    _timer = None
    _engine = None
    _n_steps = 0
    _done = 0

    def invoke(self, context, event):
        get_engine = _imp_controller_engine()
        engine = get_engine()
        if engine.rule is None:
            try:
                init_engine_from_settings(context)
            except RuntimeError as e:
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}
        # 审查修复:每次 invoke 复位取消标志,否则取消过一次后所有后续烘焙秒退
        engine._bake_cancel = False
        self._engine = engine
        self._n_steps = context.scene.ready_settings.bake_steps
        self._done = 0
        context.scene.ready_settings.is_baking = True
        context.scene.ready_settings.progress = 0.0
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "TIMER":
            if self._engine._bake_cancel:
                self._finish(context, cancelled=True)
                return {"FINISHED"}
            chunk = max(100, self._n_steps // 100)
            n = min(chunk, self._n_steps - self._done)
            self._engine._do_steps(n)
            self._done += n
            context.scene.ready_settings.progress = self._done / self._n_steps
            if self._done >= self._n_steps:
                self._finish(context, cancelled=False)
                return {"FINISHED"}
        elif event.type == "ESC":
            self._finish(context, cancelled=True)
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    def _finish(self, context, cancelled):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None
        context.scene.ready_settings.is_baking = False
        RD_OT_update_display.run(context)
        self.report({"INFO"}, f"Ready: 烘焙{'已取消' if cancelled else '完成'} ({self._done} 步)")


class RD_OT_cancel_bake(bpy.types.Operator):
    bl_idname = "ready.cancel_bake"
    bl_label = "Cancel Bake"

    def execute(self, context):
        get_engine = _imp_controller_engine()
        get_engine().bake_cancel()
        return {"FINISHED"}


class RD_OT_brush(bpy.types.Operator):
    """画笔:在 3D 视口内左键拖动涂抹。

    防御式设计(2026-08-18 修复):
    - 只在 3D 视口 WINDOW 区域内响应涂抹;点在 UI/面板上自动退出画笔并放行事件;
    - 任何异常自愈退出,绝不留卡死的 modal;
    - 状态栏提示用守卫写法(workspace 缺失不报错)。
    """
    bl_idname = "ready.brush"
    bl_label = "Brush"
    bl_options = {"REGISTER"}

    def _find_paint_region(self, context):
        """确定画笔区域:grid 模式优先 Image Editor WINDOW 区;mesh 模式用 3D 视口。"""
        screen = getattr(context, "screen", None)
        if screen is None:
            screen = getattr(getattr(context, "window", None), "screen", None)
        if screen is None:
            return None, None, None
        get_engine = _imp_controller_engine()
        engine = get_engine()
        editor_region = None
        view_region = None
        rv3d = None
        for area in screen.areas:
            if area.type == "IMAGE_EDITOR":
                for region in area.regions:
                    if region.type == "WINDOW":
                        editor_region = region
            if area.type == "VIEW_3D":
                rv3d = getattr(getattr(area.spaces, "active", None), "region_3d", None)
                for region in area.regions:
                    if region.type == "WINDOW":
                        view_region = region
        if engine.field_kind == "grid" and editor_region is not None:
            return editor_region, None, "image"
        return view_region, rv3d, "view3d"

    def invoke(self, context, event):
        get_engine = _imp_controller_engine()
        try:
            # 限定:仅对象模式可用(编辑模式/权重绘制等下 ray_cast 与拓扑不稳定)
            if getattr(context, "mode", None) not in ("OBJECT", None):
                self.report({"ERROR"}, f"画笔需在对象模式(当前 {getattr(context, 'mode', '?')}),请先切到对象模式")
                return {"CANCELLED"}
            engine = get_engine()
            if engine.rule is None:
                try:
                    init_engine_from_settings(context)
                except RuntimeError as e:
                    self.report({"ERROR"}, str(e))
                    return {"CANCELLED"}
            # 画笔 a 反馈修复:进画笔时显示化学品同步为涂抹化学品
            # (兜底 update 回调覆盖不到的程序性修改,如预设加载)
            try:
                _s = context.scene.ready_settings
                if _s.brush_chemical != _s.active_chemical:
                    _s.active_chemical = _s.brush_chemical
            except Exception:
                pass
            self._region, self._rv3d, self._paint_kind = self._find_paint_region(context)
            if self._region is None:
                self.report({"ERROR"}, "未找到可涂抹区域(3D 视口或 Image Editor)")
                return {"CANCELLED"}
            # mesh 模式:预计算面中心与世界半径(失败不影响进入画笔)
            self._face_centers = None
            self._brush_world_r = None
            try:
                if engine.field_kind == "mesh" and engine.mesh_info:
                    obj = engine.mesh_info.get("obj")
                    faces = engine.mesh_info.get("faces")
                    if obj is not None and faces is not None:
                        import bmesh as _bmesh
                        _bm = _bmesh.new()
                        _bm.from_mesh(obj.data)
                        verts = np.array([[v.co.x, v.co.y, v.co.z] for v in _bm.verts],
                                         dtype=np.float32)
                        _bm.free()
                        self._face_centers = verts[faces].mean(axis=1)
                        bb = verts.max(axis=0) - verts.min(axis=0)
                        self._brush_world_r = (context.scene.ready_settings.brush_radius
                                               * 0.01 * float(bb.max() or 1.0))
            except Exception:
                pass
            engine.pause()  # 进入画笔自动暂停模拟
            engine.save_snapshot()
            self._painting = False
            self._last_paint = None
            # 进入画笔前刷新显示(修复:重置后直接进画笔时画面与场不一致)
            try:
                RD_OT_update_display.run(context)
            except Exception:
                pass
            # 状态栏提示(守卫写法,按模式给明确指引)
            try:
                ws = getattr(context, "workspace", None)
                if ws is not None:
                    if engine.field_kind == "grid":
                        hint = "Ready 画笔:图像区左键拖动涂抹 | 右键撤销退出 | ESC/回车保留退出"
                    else:
                        hint = "Ready 画笔:3D视图 左键拖动涂抹 | 右键撤销退出 | ESC/回车保留退出"
                    ws.status_text_set(hint)
            except Exception:
                pass
            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        except Exception as e:
            self.report({"ERROR"}, f"画笔启动失败: {e}")
            return {"CANCELLED"}

    def _mouse_in_viewport(self, event):
        r = self._region
        if r is None:
            return False
        return (0 <= event.mouse_region_x < r.width
                and 0 <= event.mouse_region_y < r.height)

    def _cleanup(self, context):
        try:
            ws = getattr(context, "workspace", None)
            if ws is not None:
                ws.status_text_set(None)
        except Exception:
            pass
        self._painting = False
        self._last_paint = None

    def _paint_at(self, context, event):
        """在当前鼠标位置落笔一次。返回 True 表示已涂。"""
        get_engine = _imp_controller_engine()
        engine = get_engine()
        settings = context.scene.ready_settings
        chem_idx = 0 if settings.brush_chemical == "a" else 1
        radius = settings.brush_radius
        value = settings.brush_value
        if engine.field_kind == "grid":
            f = engine.fields[chem_idx]
            h, w = f.shape
            x = int(event.mouse_region_x / max(self._region.width, 1) * w)
            y = int(event.mouse_region_y / max(self._region.height, 1) * h)
            x0, x1 = max(0, x - radius), min(w, x + radius)
            y0, y1 = max(0, y - radius), min(h, y + radius)
            f[y0:y1, x0:x1] = value
            return True
        if engine.field_kind == "mesh" and self._face_centers is not None:
            try:
                from bpy_extras import view3d_utils
                coord = (event.mouse_region_x, event.mouse_region_y)
                origin = view3d_utils.region_2d_to_origin_3d(self._region, self._rv3d, coord)
                direction = view3d_utils.region_2d_to_vector_3d(self._region, self._rv3d, coord)
                obj = engine.mesh_info["obj"]
                matrix = obj.matrix_world
                deps = context.evaluated_depsgraph_get()
                hit, loc, _, _, _, _ = context.scene.ray_cast(deps, origin, direction)
                if not hit:
                    return False
                loc_l = matrix.inverted() @ loc
                d2 = ((self._face_centers - loc_l) ** 2).sum(axis=1)
                r = self._brush_world_r or (radius * 0.01)
                sel = d2 < r * r
                if sel.any():
                    engine.fields[chem_idx][sel] = value
                    return True
            except Exception:
                return False
        return False

    def modal(self, context, event):
        get_engine = _imp_controller_engine()
        try:
            engine = get_engine()
            if event.type == "LEFTMOUSE" and event.value == "PRESS":
                if self._mouse_in_viewport(event):
                    self._painting = True
                    self._last_paint = None
                    if self._paint_at(context, event):
                        self._last_paint = (event.mouse_region_x, event.mouse_region_y)
                    RD_OT_update_display.run(context)
                    return {"RUNNING_MODAL"}
                # 点击在落笔区域外:不退出,放行事件(只有 ESC/右键/回车退出)
                return {"PASS_THROUGH"}
            if event.type == "LEFTMOUSE" and event.value == "RELEASE":
                self._painting = False
                self._last_paint = None
                return {"RUNNING_MODAL"}
            if self._painting and event.type == "MOUSEMOVE":
                if self._mouse_in_viewport(event):
                    if self._last_paint != (event.mouse_region_x, event.mouse_region_y):
                        if self._paint_at(context, event):
                            self._last_paint = (event.mouse_region_x, event.mouse_region_y)
                        RD_OT_update_display.run(context)
                return {"RUNNING_MODAL"}
            if event.type in {"RIGHTMOUSE"}:
                # 右键:撤销本次涂抹并退出
                engine.undo()
                RD_OT_update_display.run(context)
                self._cleanup(context)
                return {"CANCELLED"}
            if event.type == "ESC":
                # ESC:保留涂抹直接退出(不撤销)
                RD_OT_update_display.run(context)
                self._cleanup(context)
                return {"CANCELLED"}
            if event.type == "RET":
                # 回车:保留涂抹确认退出
                RD_OT_update_display.run(context)
                self._cleanup(context)
                return {"FINISHED"}
            return {"PASS_THROUGH"}
        except Exception:
            # 自愈:任何异常都退出 modal,绝不卡死 UI
            self._cleanup(context)
            return {"CANCELLED"}

def _get_preset_items(self=None, context=None):
    """EnumProperty items 回调:GS 系统显示 12 组 GS 预设;公式系统显示其参数变体。"""
    try:
        try:
            from ..presets.presets import get_items, get_variants
        except ImportError:
            from presets.presets import get_items, get_variants
    except ImportError:
        return [("none", "No presets found", "")]
    sid = "gray_scott"
    try:
        import bpy as _bpy
        scene = getattr(_bpy.context, "scene", None)
        if scene is not None and hasattr(scene, "ready_settings"):
            sid = scene.ready_settings.system_enum
    except Exception:
        pass
    if sid != "gray_scott":
        items = [("default", "文献默认", "")]
        for v in get_variants(sid):
            items.append((v["id"], v["name"], ""))
        return items
    items = []
    try:
        from ..ui.previews import preset_icon
    except ImportError:
        try:
            from ui.previews import preset_icon
        except ImportError:
            preset_icon = None
    for it in get_items():
        icon = 0
        if preset_icon is not None:
            try:
                icon = preset_icon(it[0])
            except Exception:
                icon = 0
        items.append((it[0], it[1], it[2], icon, 0))
    return items




class RD_OT_preset_load(bpy.types.Operator):
    """加载预设:从 presets.presets 模块取预设(与 presets.json 同源),消除文件读取编码风险。"""
    bl_idname = "ready.preset_load"
    bl_label = "Load Preset"
    bl_options = {"REGISTER"}
    bl_property = "preset_enum"

    preset_enum: bpy.props.EnumProperty(
        name="Preset",
        items=_get_preset_items,
    )

    def execute(self, context):
        try:
            from ..presets.presets import get_preset
        except ImportError:
            from presets.presets import get_preset
        p = get_preset(self.preset_enum)
        s = context.scene.ready_settings
        if s.system_enum == "oil_water":
            # Oil-Water 参数为文献固定值(排斥 0.7 / dt 0.05),无预设体系
            self.report({"INFO"}, "Ready: Oil-Water 参数固定(文献值),无需加载预设")
            return {"FINISHED"}
        if s.system_enum != "gray_scott":
            # 公式系统:选择参数变体后直接初始化
            if self.preset_enum != "default":
                try:
                    s.formula_variant = self.preset_enum
                except TypeError:
                    # 动态枚举 items 缓存尚未随 system_enum 刷新:
                    # 直接写底层标识符(值有效,重绘后正常显示)
                    s["formula_variant"] = self.preset_enum
            try:
                init_engine_from_settings(context)
            except RuntimeError:
                pass
            self.report({"INFO"}, f"Ready: 已加载参数变体 {self.preset_enum}")
            return {"FINISHED"}
        if p is None:
            self.report({"ERROR"}, f"未知预设: {self.preset_enum}")
            return {"CANCELLED"}
        s.param_Du = p["params"].get("Du", 0.16)
        s.param_Dv = p["params"].get("Dv", 0.08)
        s.param_F = p["params"].get("F", 0.0367)
        s.param_k = p["params"].get("k", 0.0649)
        s.param_dt = p["params"].get("dt", 1.0)
        # W1 扩展参数:应用网页导出的 pattern_scale / orientation / flow
        _ext = p.get("extensions") or {}
        try:
            if _ext.get("pattern_scale"):
                s.pattern_scale = max(0.25, min(2.5, float(_ext["pattern_scale"])))
            o = _ext.get("orientation") or {}
            if o and o.get("kind") and o.get("kind") != "none":
                try:
                    s.orientation_kind = o["kind"]
                except TypeError:
                    s["orientation_kind"] = o["kind"]
                s.orientation_strength = max(0.0, min(0.95, float(o.get("strength", 0.0))))
            else:
                s.orientation_kind = "none"
                s.orientation_strength = 0.0
            f = _ext.get("flow") or {}
            if f and f.get("kind") and f.get("kind") != "none":
                try:
                    s.flow_kind = f["kind"]
                except TypeError:
                    s["flow_kind"] = f["kind"]
                s.flow_strength = max(0.0, min(1.0, float(f.get("strength", 0.0))))
            else:
                s.flow_kind = "none"
                s.flow_strength = 0.0
        except Exception:
            pass
        # F15/N9 修复:同步 seed_region/noise_ratio(命名映射:预设旧值→枚举值)
        sr = p.get("seed_region", "")
        sr_map = {"center_square_0.25": "center_square", "center_disc": "center_disc",
                  "center_square": "center_square", "global": "global",
                  "uniform_sparse": "uniform_sparse"}
        if sr in sr_map:
            s.seed_region = sr_map[sr]
        # 注:不再同步 noise_ratio(预设里的 1.0 语义是区域满铺,会盖掉全局稀疏密度)
        try:
            init_engine_from_settings(context)
        except RuntimeError:
            pass
        self.report({"INFO"}, f"Ready: 已加载预设 {p['name']}")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class RD_OT_update_display(bpy.types.Operator):
    bl_idname = "ready.update_display"
    bl_label = "Update Display"

    @staticmethod
    def run(context):
        RD_OT_update_display._run(context)

    @staticmethod
    def run_safe():
        """timer 回调无完整 context 时的显示更新(审查修复:scheduler._tick 调用)。"""
        try:
            RD_OT_update_display._run(bpy.context)
        except Exception:
            pass

    @staticmethod
    def _run(context):
        get_engine = _imp_controller_engine()
        engine = get_engine()
        if engine.rule is None or not engine.fields:
            return
        settings = getattr(context, "scene", None)
        chem_idx = 0
        colormap = "viridis"
        output_mode = "attribute"
        colormap_range = "auto"
        if settings is not None and hasattr(settings, "ready_settings"):
            rs = settings.ready_settings
            chem_idx = 0 if rs.active_chemical == "a" else 1
            colormap = rs.colormap
            output_mode = rs.output_mode
            colormap_range = rs.colormap_range
        data = engine.fields[chem_idx]
        # B9 修复:范围锁定选项
        vmin = vmax = None
        if colormap_range == "fixed_b" and chem_idx == 1:
            vmin, vmax = 0.0, 0.5
        elif colormap_range == "fixed_a" and chem_idx == 0:
            vmin, vmax = 0.0, 1.0
        if engine.field_kind == "grid":
            try:
                from ..adapters.image_adapter import field_to_image
            except ImportError:
                from adapters.image_adapter import field_to_image
            img = field_to_image(data, "RD_preview", colormap=colormap,
                                 vmin=vmin, vmax=vmax)
            # 目标模式修复:自动把 RD_preview 设为所有打开的 Image Editor 的当前图像,
            # 用户切到 Image Editor 即可见(不需要摄像机)。N5 修复:用干净遍历。
            try:
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == "IMAGE_EDITOR":
                            sp = getattr(area.spaces, "active", None)
                            if sp is not None:
                                sp.image = img
            except Exception:
                pass
        elif engine.mesh_info and engine.mesh_info.get("obj"):
            obj = engine.mesh_info["obj"]
            # B2 修复:拓扑指纹校验,网格变更后跳过写入并提示重初始化
            m = getattr(obj, "data", None)
            if m is None:
                engine.last_error = "目标网格已删除,请重新初始化模拟"
                return
            topo = engine.mesh_info.get("topo")
            if topo is not None and (len(m.vertices), len(m.polygons)) != topo:
                engine.last_error = ("目标网格拓扑已变更(编辑/修改器/替换),"
                                     "显示写入已暂停,请重新初始化模拟")
                return
            engine.last_error = None
            try:
                from ..adapters.mesh_adapter import (write_named_attribute,
                                                     write_vertex_color,
                                                     write_displacement)
            except ImportError:
                from adapters.mesh_adapter import (write_named_attribute,
                                                   write_vertex_color,
                                                   write_displacement)
            if output_mode == "vertex_color":
                write_vertex_color(obj, data)
            elif output_mode == "displacement":
                write_displacement(obj, data)
            else:
                write_named_attribute(obj, data, "RD_value", domain="FACE")
        wm = getattr(bpy.context, "window_manager", None)
        if wm is not None:
            for window in wm.windows:
                for area in window.screen.areas:
                    for region in area.regions:
                        region.tag_redraw()

    def execute(self, context):
        RD_OT_update_display._run(context)
        return {"FINISHED"}


class RD_OT_mesh_prep(bpy.types.Operator):
    """网格预处理检查:运行质量报告并弹窗展示指标(非破坏,只读分析)。"""
    bl_idname = "ready.mesh_prep"
    bl_label = "Mesh Prep Check"
    bl_options = {"REGISTER"}

    def execute(self, context):
        obj = context.scene.ready_settings.target_object
        if obj is None:
            obj = getattr(context.view_layer.objects, "active", None)
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "请先选择目标网格对象")
            return {"CANCELLED"}
        try:
            from ..core.mesh_quality import mesh_quality_report
        except ImportError:
            from core.mesh_quality import mesh_quality_report
        import bmesh as _bmesh
        _bm = _bmesh.new()
        _bm.from_mesh(obj.data)
        # 类别判定(三角化前的原始多边形构成)
        tri = quad = ngon = 0
        for f in _bm.faces:
            n = len(f.verts)
            if n == 3:
                tri += 1
            elif n == 4:
                quad += 1
            else:
                ngon += 1
        category_parts = []
        if tri:
            category_parts.append(f"三角{tri}")
        if quad:
            category_parts.append(f"四边{quad}")
        if ngon:
            category_parts.append(f"n-gon{ngon}")
        category = "/".join(category_parts) if category_parts else "空"
        _bmesh.ops.triangulate(_bm, faces=_bm.faces[:])
        _bm.faces.index_update()
        verts = np.array([[v.co.x, v.co.y, v.co.z] for v in _bm.verts], dtype=np.float32)
        faces = np.array([[l.vert.index for l in f.loops] for f in _bm.faces], dtype=np.int32)
        _bm.free()
        s = context.scene.ready_settings
        report = mesh_quality_report(verts, faces,
                                     min_angle_deg=s.mesh_min_angle,
                                     cv_threshold=s.cv_threshold,
                                     target_face_density=s.mesh_target_density)
        s.mesh_report_category = category
        s.mesh_report_n_verts = report["n_verts"]
        s.mesh_report_n_faces = report["n_faces"]
        s.mesh_report_edge_ratio = report["edge_ratio"]
        s.mesh_report_sliver = report["sliver_ratio"]
        s.mesh_report_cv = report["area_cv"]
        s.mesh_report_density = report["face_density"]
        s.mesh_report_quantity_ok = report["quantity_ok"]
        s.mesh_report_uniform_ok = report["uniform_ok"]
        s.mesh_report_text = "; ".join(report["issues"]) if report["issues"] else "网格质量合格 ✓"
        self.report({"INFO"}, "Ready: " + s.mesh_report_text[:100])
        return {"FINISHED"}


class RD_OT_mesh_triangulate_copy(bpy.types.Operator):
    """生成三角化副本(非破坏:原对象不动,副本命名 <原名>_rd_tri)。"""
    bl_idname = "ready.mesh_triangulate_copy"
    bl_label = "Triangulate Copy"
    bl_options = {"REGISTER"}

    def execute(self, context):
        obj = context.scene.ready_settings.target_object
        if obj is None:
            obj = getattr(context.view_layer.objects, "active", None)
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "请先选择目标网格对象")
            return {"CANCELLED"}
        import bmesh as _bmesh
        # 副本数据块(原网格数据不动)
        src_mesh = obj.data
        new_mesh = src_mesh.copy()
        new_mesh.name = f"{obj.name}_rd_tri"
        _bm = _bmesh.new()
        _bm.from_mesh(new_mesh)
        _bmesh.ops.triangulate(_bm, faces=_bm.faces[:])
        _bm.to_mesh(new_mesh)
        _bm.free()
        new_obj = bpy.data.objects.new(f"{obj.name}_rd_tri", new_mesh)
        context.collection.objects.link(new_obj)
        new_obj.matrix_world = obj.matrix_world
        context.scene.ready_settings.target_object = new_obj
        self.report({"INFO"}, f"Ready: 已生成三角化副本 {new_obj.name}(原对象未改动)")
        return {"FINISHED"}



class RD_OT_material_from_rd(bpy.types.Operator):
    """把 RD_preview 图像接到活动物体材质(非破坏:新建 'RD_texture' 材质)。"""
    bl_idname = "ready.material_from_rd"
    bl_label = "Apply RD Texture to Material"
    bl_options = {"REGISTER"}

    def execute(self, context):
        obj = getattr(context.view_layer.objects, "active", None)
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "请先选中一个网格物体(活动对象)")
            return {"CANCELLED"}
        img = bpy.data.images.get("RD_preview")
        if img is None:
            self.report({"ERROR"}, "尚无 RD_preview 图像:先初始化并运行 2D 模拟")
            return {"CANCELLED"}
        mat = bpy.data.materials.get("RD_texture")
        if mat is None:
            mat = bpy.data.materials.new("RD_texture")
        mat.use_nodes = True
        nt = mat.node_tree
        tex = nt.nodes.get("RD_texture_node")
        if tex is None:
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.name = "RD_texture_node"
            tex.label = "RD_preview"
        tex.image = img
        if "Principled BSDF" in nt.nodes:
            bsdf = nt.nodes["Principled BSDF"]
            if not tex.outputs[0].links:
                nt.links.new(tex.outputs[0], bsdf.inputs["Base Color"])
        # 凹凸/置换:接 Displacement(材质预览/渲染可见);网格顶点凹凸用输出模式=置换+GN
        out = nt.nodes.get("Material Output")
        if out is not None and not any(l.to_socket == out.inputs["Displacement"] for l in tex.outputs[0].links):
            nt.links.new(tex.outputs[0], out.inputs["Displacement"])
        mat.cycles.displacement_method = "BUMP"
        if not obj.data.materials:
            obj.data.materials.append(mat)
        elif obj.data.materials[0] is not mat:
            obj.data.materials[0] = mat
        self.report({"INFO"}, "已把 RD_preview 接入材质 RD_texture(活动物体)")
        return {"FINISHED"}



class RD_OT_add_displacement_gn(bpy.types.Operator):
    """一键给目标网格添加几何置换(凹凸)修改器:自动搭好 GN 节点树,强度暴露为修改器输入。

    节点链:Position×Normal → VectorMath(SCALE, 输入=Normal, Scale=RD_disp×强度) → Set Position Offset
    幂等:已存在 Ready_Displace 修改器且节点树完整时直接复用,不重复创建。
    """
    bl_idname = "ready.add_displacement_gn"
    bl_label = "Add Bump (Geometry Nodes Modifier)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        obj = context.scene.ready_settings.target_object
        if obj is None:
            obj = getattr(context.view_layer.objects, "active", None)
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "请先选择目标网格对象")
            return {"CANCELLED"}
        # F14/N8 修复:不依赖 output_mode,直接写 RD_disp(引擎未初始化先初始化)
        get_engine = _imp_controller_engine()
        engine = get_engine()
        if engine.rule is None:
            try:
                init_engine_from_settings(context)
                engine = get_engine()
            except RuntimeError as e:
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}
        try:
            from ..adapters.mesh_adapter import write_displacement
        except ImportError:
            from adapters.mesh_adapter import write_displacement
        chem_idx = 0 if context.scene.ready_settings.active_chemical == "a" else 1
        write_displacement(obj, engine.fields[chem_idx])
        # 幂等:已有完整修改器则复用
        if "Ready_Displace" in obj.modifiers:
            mod = obj.modifiers["Ready_Displace"]
            if (mod.type == "NODES" and mod.node_group is not None
                    and mod.node_group.nodes.get("Ready_SetPosition") is not None):
                self.report({"INFO"}, "凹凸修改器已存在,直接复用 Ready_Displace")
                return {"FINISHED"}
        else:
            mod = obj.modifiers.new("Ready_Displace", "NODES")
        # 节点组(复用或新建)
        ng = mod.node_group
        if ng is None:
            ng = bpy.data.node_groups.new("Ready_Displace_GN", "GeometryNodeTree")
            mod.node_group = ng
        try:
            self._build_tree(ng)
        except Exception as e:
            self.report({"ERROR"}, f"GN 节点构建失败: {e}")
            return {"CANCELLED"}
        self.report({"INFO"}, "已添加 Ready_Displace 凹凸修改器(修改器面板调 强度)")
        return {"FINISHED"}

    @staticmethod
    def _build_tree(ng):
        if ng.nodes.get("Ready_SetPosition") is not None:
            return  # 已有完整树
        ng.nodes.clear()  # 清空残留,保证干净重建

        def new_node(ids):
            for nid in ids:
                try:
                    return ng.nodes.new(nid)
                except RuntimeError:
                    continue
            raise RuntimeError(f"无法创建节点: {ids}")

        def stype(s):
            return getattr(s, "type", "")

        gi = ng.nodes.get("Group Input") or new_node(["NodeGroupInput"])
        gp = ng.nodes.get("Group Output") or new_node(["NodeGroupOutput"])
        # Blender 4.x 新建 GeometryNodeTree 无默认 Geometry 接口,显式创建
        iface_names = [s.name for s in ng.interface.items_tree]
        if "Geometry" not in iface_names:
            ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
            ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
            iface_names.append("Geometry")
        if "强度" not in iface_names:
            sd = ng.interface.new_socket("强度", in_out="INPUT", socket_type="NodeSocketFloat")
            sd.default_value = 0.1
            sd.min_value = 0.0

        nrm = new_node(["GeometryNodeInputNormal"])
        attr = new_node(["GeometryNodeInputNamedAttribute"])
        attr.data_type = "FLOAT"
        attr.inputs["Name"].default_value = "RD_disp"
        fmath = new_node(["FunctionNodeFloatMath", "ShaderNodeMath"])
        fmath.operation = "MULTIPLY"
        vmath = new_node(["FunctionNodeVectorMath", "ShaderNodeVectorMath"])
        vmath.operation = "SCALE"
        setpos = new_node(["GeometryNodeSetPosition"])
        setpos.name = "Ready_SetPosition"
        # 布局
        gi.location = (0, 0)
        attr.location = (0, -200)
        fmath.location = (200, -200)
        nrm.location = (0, -400)
        vmath.location = (200, -400)
        setpos.location = (420, -100)
        gp.location = (640, 0)

        # 类型驱动的自适应连线:按名称优先、类型匹配、空闲 socket 去重
        used = set()

        def link(src, node, want_type, prefer_names):
            for name in prefer_names:
                try:
                    s = node.inputs[name]
                except KeyError:
                    continue
                if s in used:
                    continue
                if stype(s) == want_type:
                    ng.links.new(src, s)
                    used.add(s)
                    return
            for s in node.inputs:
                if s in used:
                    continue
                if stype(s) == want_type:
                    ng.links.new(src, s)
                    used.add(s)
                    return
            raise RuntimeError(f"{node.bl_idname} 缺少类型 {want_type} 的空闲输入")

        def out_sock(node, want_type, prefer_names, idx=0):
            for name in prefer_names:
                try:
                    s = node.outputs[name]
                except KeyError:
                    continue
                if stype(s) == want_type:
                    return s
            for s in node.outputs:
                if stype(s) == want_type:
                    return s
            return node.outputs[idx]

        geo_out = out_sock(gi, "GEOMETRY", ["Geometry"])
        qd_out = out_sock(gi, "VALUE", ["强度"])
        link(geo_out, setpos, "GEOMETRY", ["Geometry"])
        link(out_sock(attr, "VALUE", ["Attribute"]), fmath, "VALUE", ["A", "B", "Value"])
        link(qd_out, fmath, "VALUE", ["B", "Value", "A"])
        link(out_sock(nrm, "VECTOR", ["Normal"]), vmath, "VECTOR", ["Vector"])
        link(out_sock(fmath, "VALUE", ["Value"]), vmath, "VALUE", ["Scale"])
        link(out_sock(vmath, "VECTOR", ["Vector"]), setpos, "VECTOR", ["Offset"])
        link(out_sock(setpos, "GEOMETRY", ["Geometry"]), gp, "GEOMETRY", ["Geometry"])



class RD_OT_apply_vertex_displacement(bpy.types.Operator):
    """一键顶点凹凸(借鉴外部插件核心管线,但按本项目原则实现):

    顶点域 RD(边图拉普拉斯 + 开放面边界 Dirichlet 保持 + 稀疏种子)
    → V 归一化 → 沿顶点法线直接位移几何。UNDO 可回退(Ctrl+Z)。
    建议先做 ② 质量检查/三角化副本 保证顶点分布均匀。
    """
    bl_idname = "ready.apply_vertex_displacement"
    bl_label = "Apply Vertex Displacement"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        import time as _time
        obj = context.scene.ready_settings.target_object
        if obj is None:
            obj = getattr(context.view_layer.objects, "active", None)
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "请先选择目标网格对象")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            self.report({"ERROR"}, "请先切到物体模式")
            return {"CANCELLED"}
        s = context.scene.ready_settings
        try:
            from ..core.vertex_rd import run_vertex_rd
        except ImportError:
            from core.vertex_rd import run_vertex_rd
        import bmesh as _bm
        _t0 = _time.time()
        _b = _bm.new()
        _b.from_mesh(obj.data)
        _bm.ops.triangulate(_b, faces=_b.faces[:])
        _b.verts.ensure_lookup_table()
        _b.edges.ensure_lookup_table()
        _b.faces.ensure_lookup_table()
        n_verts = len(_b.verts)
        edges = np.array([(e.verts[0].index, e.verts[1].index) for e in _b.edges],
                         dtype=np.int32)
        faces = np.array([[l.vert.index for l in f.loops] for f in _b.faces],
                         dtype=np.int32)
        normals = np.array([v.normal for v in _b.verts], dtype=np.float32)
        verts_co = np.array([v.co for v in _b.verts], dtype=np.float32)
        if n_verts < 100 or len(edges) == 0:
            _b.free()
            self.report({"WARNING"}, "顶点过少,建议先重网格化(目标面数 20k+)")
            return {"CANCELLED"}
        # 顶点域 RD(边界保持开;V5:seed_ratio 接 settings + rng 播种可复现)
        try:
            from ..core.vertex_rd import sparse_seeds, find_boundary_verts, build_edge_graph, rd_step_vertex
        except ImportError:
            from core.vertex_rd import sparse_seeds, find_boundary_verts, build_edge_graph, rd_step_vertex
        _rng = np.random.default_rng(s.rng_seed)
        _v1, _v2, _deg = build_edge_graph(n_verts, edges)
        _bd = find_boundary_verts(n_verts, faces)
        U = np.ones(n_verts, dtype=np.float32)
        V = sparse_seeds(n_verts, s.vertex_seed_ratio, _bd, _rng)
        # 可选 Numba 加速(未安装自动回退 numpy,结果同源;读场景勾选框)
        _use_numba = bool(s.use_numba)
        _ran_numba = False
        if _use_numba:
            try:
                from ..backend.numba_backend import run_vertex_rd_numba, NUMBA_AVAILABLE
            except ImportError:
                from backend.numba_backend import run_vertex_rd_numba, NUMBA_AVAILABLE
            if NUMBA_AVAILABLE:
                run_vertex_rd_numba(U, V, _v1, _v2, _deg, _bd,
                                    s.param_Du, s.param_Dv, s.param_F, s.param_k,
                                    s.param_dt, s.bake_steps)
                _ran_numba = True
        if not _ran_numba:
            for _ in range(s.bake_steps):
                rd_step_vertex(U, V, _v1, _v2, _deg, _bd,
                              s.param_Du, s.param_Dv, s.param_F, s.param_k,
                              s.param_dt)
        # V 归一化 → 位移
        vmin, vmax = float(V.min()), float(V.max())
        norm_v = (V - vmin) / max(vmax - vmin, 1e-6)
        disp = s.mesh_displacement_strength
        new_co = verts_co + normals * (norm_v[:, None] * disp)
        for i, v in enumerate(_b.verts):
            v.co = new_co[i]
        _b.to_mesh(obj.data)
        _b.free()
        elapsed = _time.time() - _t0
        self.report({"INFO"}, f"顶点凹凸完成:{n_verts} 顶点,{elapsed:.1f}s "
                              f"(Ctrl+Z 可回退)")
        return {"FINISHED"}



class RD_OT_subdivide_copy(bpy.types.Operator):
    """生成细分副本(非破坏):副本加 Subdivision Surface(级别=settings.subdivide_levels)并应用。"""
    bl_idname = "ready.subdivide_copy"
    bl_label = "Subdivide Copy"
    bl_options = {"REGISTER"}

    def execute(self, context):
        obj = context.scene.ready_settings.target_object
        if obj is None:
            obj = getattr(context.view_layer.objects, "active", None)
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "请先选择目标网格对象")
            return {"CANCELLED"}
        s = context.scene.ready_settings
        new_mesh = obj.data.copy()
        new_mesh.name = f"{obj.name}_rd_sub"
        new_obj = bpy.data.objects.new(f"{obj.name}_rd_sub", new_mesh)
        context.collection.objects.link(new_obj)
        new_obj.matrix_world = obj.matrix_world
        mod = new_obj.modifiers.new("RD_Subdiv", "SUBSURF")
        mod.levels = s.subdivide_levels
        mod.render_levels = s.subdivide_levels
        bpy.context.view_layer.objects.active = new_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        context.scene.ready_settings.target_object = new_obj
        self.report({"INFO"}, f"已生成细分副本 {new_obj.name}(原对象未改动)")
        return {"FINISHED"}



class RD_OT_remesh_copy(bpy.types.Operator):
    """生成 Voxel Remesh 副本(非破坏;v6 式 voxel 估算:sqrt(表面积/目标面数)*1.2)。"""
    bl_idname = "ready.remesh_copy"
    bl_label = "Remesh Copy"
    bl_options = {"REGISTER"}

    def execute(self, context):
        obj = context.scene.ready_settings.target_object
        if obj is None:
            obj = getattr(context.view_layer.objects, "active", None)
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "请先选择目标网格对象")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            self.report({"ERROR"}, "请先切到物体模式")
            return {"CANCELLED"}
        s = context.scene.ready_settings
        # 表面积与 voxel 尺寸估算(v6 口径)
        area = 0.0
        for poly in obj.data.polygons:
            area += poly.area
        voxel_size = (area / max(s.remesh_target_faces, 1)) ** 0.5 * 1.2
        if voxel_size <= 0:
            self.report({"ERROR"}, "网格表面积无效")
            return {"CANCELLED"}
        new_mesh = obj.data.copy()
        new_mesh.name = f"{obj.name}_rd_remesh"
        new_obj = bpy.data.objects.new(f"{obj.name}_rd_remesh", new_mesh)
        context.collection.objects.link(new_obj)
        new_obj.matrix_world = obj.matrix_world
        bpy.context.view_layer.objects.active = new_obj
        # Voxel Remesh 后应用(4.2/4.5 均有 mesh_remesh_voxel_size)
        bpy.ops.object.voxel_remesh(mesh_remesh_voxel_size=voxel_size, adaptivity=0.0)
        context.scene.ready_settings.target_object = new_obj
        self.report({"INFO"}, f"已生成 Remesh 副本 {new_obj.name} "
                              f"(voxel={voxel_size:.4f}, 原对象未改动)")
        return {"FINISHED"}


class RD_OT_grow3d_pipeline(bpy.types.Operator):
    """3D 管道生长:体素 Gray-Scott(文献口径 grayscott_3D)在 Dirichlet 框架内生长,
    等值面提取为独立网格对象。选中网格体时:网格表面为生长边界(体素化内部求解,
    输出与原网格几何对齐);无网格时:自由盒模式(盒壁框架,居中输出)。"""
    bl_idname = "ready.grow3d_pipeline"
    bl_label = "3D Growth Pipeline"
    bl_options = {"REGISTER"}

    @staticmethod
    def _resolve_target(context, settings):
        """grow3d 目标网格:①区选择器优先,未选时用活动网格物体。"""
        obj = settings.target_object
        if obj is None or obj.type != "MESH":
            obj = getattr(context.view_layer, "objects", None)
            obj = getattr(obj, "active", None) if obj is not None else None
        if obj is not None and obj.type == "MESH":
            return obj
        return None

    def execute(self, context):
        try:
            from ..adapters.volume_adapter import simulate_growth_3d, voxelize_mesh
        except ImportError:
            from adapters.volume_adapter import simulate_growth_3d, voxelize_mesh
        s = context.scene.ready_settings
        wm = context.window_manager
        params = {"Du": s.param_Du, "Dv": s.param_Dv,
                  "F": s.param_F, "k": s.param_k}
        wm.progress_begin(0, 100)

        def _cb(p):
            wm.progress_update(int(p * 100))

        # 网格边界模式:选中网格体 → 体素化内部掩码(网格表面=Dirichlet 生长框架)
        domain_mask = None
        bbox_min = bbox_size = None
        target = self._resolve_target(context, s)
        if target is not None:
            try:
                import bmesh as _bm
                _b = _bm.new()
                _b.from_mesh(target.data)
                _bm.ops.triangulate(_b, faces=_b.faces[:])
                _mv = np.array([[v.co.x, v.co.y, v.co.z] for v in _b.verts],
                               dtype=np.float64)
                _mf = np.array([[f.verts[0].index, f.verts[1].index,
                                 f.verts[2].index] for f in _b.faces],
                               dtype=np.int64)
                _b.free()
                # 世界系包围盒(网格可能有变换)
                _mw = np.array(target.matrix_world.to_3x3(), dtype=np.float64)
                _wv = _mv @ _mw.T
                if len(_mf):
                    domain_mask, bbox_min, bbox_size = voxelize_mesh(
                        _wv, _mf, s.grow3d_size)
            except Exception as ex:
                wm.progress_end()
                self.report({"ERROR"}, f"网格体素化失败: {ex}(将退回自由盒模式)")
                domain_mask = None

        try:
            verts, faces, _b = simulate_growth_3d(
                size=s.grow3d_size, steps=s.grow3d_steps, params=params,
                seed=s.rng_seed, threshold=s.grow3d_threshold,
                progress_cb=_cb, use_numba=s.use_numba,
                domain_mask=domain_mask)
        except Exception as ex:
            wm.progress_end()
            self.report({"ERROR"}, f"3D 生长失败: {ex}")
            return {"CANCELLED"}
        wm.progress_end()
        try:
            from ..backend.numba_backend import NUMBA_AVAILABLE as _NA
        except ImportError:
            from backend.numba_backend import NUMBA_AVAILABLE as _NA
        accel = "numba" if (_NA and s.use_numba) else "numpy"

        if len(faces) == 0 or len(verts) == 0:
            self.report({"WARNING"}, "Ready: 等值面为空——降低阈值或增加步数后重试,"
                                     "或检查②参数区是否在生长区间(文献口径 F=0.035/k=0.064)")
            return {"FINISHED"}

        v_arr = np.asarray(verts, dtype=np.float32)
        f_arr = np.asarray(faces, dtype=np.int32)
        if domain_mask is not None:
            # 网格边界模式:体素坐标 [0,N-1] → 原网格世界包围盒(几何对齐)
            scale = bbox_size / max(s.grow3d_size - 1, 1)
            v_arr = bbox_min[None, :] + v_arr * scale[None, :]
            obj_name = f"RD_Growth3D_{target.name}"
        else:
            # 自由盒:居中网格对象(体素间距 1,中心置于世界原点)
            v_arr = v_arr - s.grow3d_size / 2.0
            obj_name = "RD_Growth3D"
        mesh = bpy.data.meshes.new(obj_name)
        mesh.from_pydata(v_arr.tolist(), [], f_arr.tolist())
        mesh.update()
        obj = bpy.data.objects.new(obj_name, mesh)
        context.collection.objects.link(obj)
        for poly in mesh.polygons:
            poly.use_smooth = True
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        mode = (f"网格边界[{target.name}]" if domain_mask is not None
                else "自由盒")
        self.report({"INFO"}, f"Ready: 3D 管道生长完成 "
                              f"{len(v_arr)} 顶点 / {len(f_arr)} 面 "
                              f"({s.grow3d_size}³ × {s.grow3d_steps} 步, {accel}, "
                              f"{mode}, 光滑等值面)")
        return {"FINISHED"}



class RD_OT_pattern_map_pick(bpy.types.Operator):
    """点击取参弹窗:渲染 (k,F) 图案地图到 Image Editor,鼠标悬停实时读数,左键取参。

    坐标映射:图像像素 (u,v) → (k,F),v 轴翻转(底部 = F 上限,与地图行序一致)。
    全部交互自愈:任何异常进入 cleanup 并取消,绝不卡死 UI。
    """
    bl_idname = "ready.pattern_map_pick"
    bl_label = "Pick (k,F) from Pattern Map"
    bl_options = {"REGISTER"}

    _handle = None          # draw handler 句柄
    _prev_image = None      # 进入前的 space.image(退出还原)
    _converted_area = None  # (area, old_type) 若自动转了 Image Editor
    _kf = None              # 当前悬停 (k, F)

    @staticmethod
    def _draw_cb(self, context):
        """十字准线 + (k,F) 读数(4.2 gpu 模块;失败静默)。"""
        try:
            from gpu.types import GPUShader
            import gpu
            import blf
            if self._kf is None:
                return
            area = getattr(context, "area", None)
            if area is None or area.type != "IMAGE_EDITOR":
                return
            reg = None
            for r in area.regions:
                if r.type == "WINDOW":
                    reg = r
                    break
            if reg is None:
                return
            x = int(self._kf[2] * reg.width)
            y = int(self._kf[3] * reg.height)
            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            gpu.state.blend_set("ALPHA")
            gpu.state.line_width_set(1.0)
            coords = [(0.0, float(y)), (float(reg.width), float(y)),
                      (float(x), 0.0), (float(x), float(reg.height))]
            batch = gpu.types.GPUBatch(type="LINES", buf=gpu.types.GPUVertBuf(
                len(coords), shader.format, "2f"))
            batch.attr_set("pos", gpu.types.GPUArray(coords))
            batch.program_set(shader)
            shader.uniform_float("color", (1.0, 0.3, 0.0, 0.9))
            batch.draw()
            gpu.state.blend_set("NONE")
            blf.size(0, 16)
            blf.position(0, x + 8, y + 8, 0)
            k, f = self._kf[0], self._kf[1]
            blf.draw(0, f"k={k:.5f}  F={f:.5f}")
        except Exception:
            pass

    def _show_map(self, context):
        """渲染地图 → bpy image → 确保 Image Editor 显示。"""
        try:
            from ..presets.pattern_map import render_pattern_map, map_image_pixels
        except ImportError:
            from presets.pattern_map import render_pattern_map, map_image_pixels
        arr = render_pattern_map(cols=24, rows=18, cell=24, steps=400,
                                 seed=42, use_cache=True)
        h, w = arr.shape
        img = bpy.data.images.get("RD_PatternMap")
        if img is None:
            img = bpy.data.images.new("RD_PatternMap", width=w, height=h,
                                      alpha=False)
        else:
            img.scale(w, h)
        img.pixels[:] = map_image_pixels(arr)
        img.update()
        # 确保有 Image Editor 且显示地图
        self._prev_image = None
        screen = getattr(context, "screen", None)
        if screen is None:
            return
        current_area = getattr(context, "area", None)
        for area in screen.areas:
            if area.type == "IMAGE_EDITOR":
                sp = getattr(area.spaces, "active", None)
                if sp is not None:
                    self._prev_image = sp.image
                    sp.image = img
                return
        for area in screen.areas:
            if area is current_area:
                continue
            if area.type in ("VIEW_3D", "PROPERTIES", "OUTLINER", "NODE_EDITOR"):
                self._converted_area = (area, area.type)
                area.type = "IMAGE_EDITOR"
                sp = getattr(area.spaces, "active", None)
                if sp is not None:
                    sp.image = img
                return
        for area in screen.areas:
            if area.type == "VIEW_3D":
                self._converted_area = (area, area.type)
                area.type = "IMAGE_EDITOR"
                sp = getattr(area.spaces, "active", None)
                if sp is not None:
                    sp.image = img
                return

    def _cleanup(self, context):
        if self._handle is not None:
            try:
                bpy.types.SpaceImageEditor.draw_handler_remove(self._handle,
                                                               "WINDOW")
            except Exception:
                pass
            self._handle = None
        self._kf = None
        if self._converted_area is not None:
            area, old_type = self._converted_area
            self._converted_area = None
            try:
                area.type = old_type
            except Exception:
                pass
        if self._prev_image is not None:
            for area in getattr(context, "screen", bpy.context).areas:
                if area.type == "IMAGE_EDITOR":
                    sp = getattr(area.spaces, "active", None)
                    if sp is not None and sp.image is not None and                             sp.image.name == "RD_PatternMap":
                        sp.image = self._prev_image
            self._prev_image = None

    def invoke(self, context, event):
        try:
            self._kf = None
            self._show_map(context)
            self._handle = bpy.types.SpaceImageEditor.draw_handler_add(
                self._draw_cb, (self, context), "WINDOW", "POST_PIXEL")
        except Exception:
            self._cleanup(context)
            self.report({"ERROR"}, "Pattern Map 打开失败(详见控制台)")
            return {"CANCELLED"}
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        try:
            if event.type in {"ESC", "RIGHTMOUSE"}:
                self._cleanup(context)
                return {"CANCELLED"}
            if event.type == "MOUSEMOVE":
                self._update_kf(context, event)
                return {"RUNNING_MODAL"}
            if event.type == "LEFTMOUSE" and event.value == "PRESS":
                if self._update_kf(context, event):
                    settings = context.scene.ready_settings
                    settings.param_F = round(self._kf[0], 5)
                    settings.param_k = round(self._kf[1], 5)
                    try:
                        RD_OT_update_display.run(context)
                    except Exception:
                        pass
                    self._cleanup(context)
                    self.report({"INFO"},
                                f"已取参: F={settings.param_F:.5f} k={settings.param_k:.5f}")
                    return {"FINISHED"}
            return {"RUNNING_MODAL"}
        except Exception:
            self._cleanup(context)
            return {"CANCELLED"}

    def _update_kf(self, context, event):
        """鼠标位置 → (k, F);成功返回 True 并更新 self._kf(含像素坐标供绘制)。"""
        try:
            from ..presets.pattern_map import kf_from_uv
        except ImportError:
            from presets.pattern_map import kf_from_uv
        area = getattr(context, "area", None)
        if area is None or area.type != "IMAGE_EDITOR":
            return False
        reg = None
        for r in area.regions:
            if r.type == "WINDOW":
                reg = r
                break
        if reg is None:
            return False
        v2d = getattr(reg, "view2d", None)
        if v2d is None:
            return False
        try:
            u, v = v2d.region_to_view(event.mouse_region_x,
                                      event.mouse_region_y)
        except Exception:
            return False
        if u < 0 or u > 1 or v < 0 or v > 1:
            return False
        k, f = kf_from_uv(u, v)
        self._kf = (k, f, u, v)
        return True


class RD_OT_import_preset_json(bpy.types.Operator):
    """导入 RD 网页工具导出的 JSON 预设(fileio/preset_io.py schema)。

    流程:文件浏览器选 JSON → import_preset_dict 校验(非法报错)
    → write_user_preset 持久化到 presets/user_presets.json(同 id 去重覆盖)
    → refresh_user_presets 刷新下拉(预设列表带 [导入] 前缀即时出现)。
    """
    bl_idname = "ready.import_preset_json"
    bl_label = "Import JSON Preset"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        try:
            try:
                from ..fileio.preset_io import import_preset_file, write_user_preset
            except ImportError:
                from fileio.preset_io import import_preset_file, write_user_preset
            try:
                from ..presets.presets import refresh_user_presets
            except ImportError:
                from presets.presets import refresh_user_presets
        except ImportError as e:
            self.report({"ERROR"}, f"模块导入失败: {e}")
            return {"CANCELLED"}
        try:
            d = import_preset_file(self.filepath)
        except ValueError as e:
            self.report({"ERROR"}, f"预设不合法: {e}")
            return {"CANCELLED"}
        try:
            write_user_preset(d)
            refresh_user_presets()
        except Exception as e:
            self.report({"ERROR"}, f"预设保存失败: {e}")
            return {"CANCELLED"}
        self.report({"INFO"},
                    f"已导入预设「{d['name']}」(③ 参数下拉 [导入] 前缀项)")
        return {"FINISHED"}


class RD_OT_paste_preset_json(bpy.types.Operator):
    """从剪贴板粘贴 JSON 导入(网页「复制 JSON」→ 面板「粘贴导入」,无需文件路径)。"""
    bl_idname = "ready.paste_preset_json"
    bl_label = "Paste Preset JSON"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            try:
                from ..fileio.preset_io import import_preset_text, write_user_preset
            except ImportError:
                from fileio.preset_io import import_preset_text, write_user_preset
            try:
                from ..presets.presets import refresh_user_presets
            except ImportError:
                from presets.presets import refresh_user_presets
        except ImportError as e:
            self.report({"ERROR"}, f"模块导入失败: {e}")
            return {"CANCELLED"}
        text = getattr(context.window_manager, "clipboard", "") or ""
        try:
            d = import_preset_text(text)
        except ValueError as e:
            self.report({"ERROR"}, f"预设不合法: {e}")
            return {"CANCELLED"}
        try:
            write_user_preset(d)
            refresh_user_presets()
        except Exception as e:
            self.report({"ERROR"}, f"预设保存失败: {e}")
            return {"CANCELLED"}
        self.report({"INFO"},
                    f"已从剪贴板导入「{d['name']}」(③ 参数下拉 [导入] 前缀项)")
        return {"FINISHED"}


class RD_OT_open_rdtool_web(bpy.types.Operator):
    """在系统默认浏览器打开 RD 网页选参工具(web/rdtool.html,自包含离线页面)。

    网页内核与插件同口径(5 点拉普拉斯 + 同裁剪);选参后「导出 JSON」
    → 回 Blender 用「导入 JSON 预设」调入。
    """
    bl_idname = "ready.open_rdtool_web"
    bl_label = "Open RD Web Tool"
    bl_options = {"REGISTER"}

    def execute(self, context):
        import os
        try:
            web_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
        except Exception:
            web_dir = None
        path = os.path.join(web_dir, "rdtool-orig", "rdtool.html") if web_dir else None
        if not path or not os.path.exists(path):
            self.report({"ERROR"}, "未找到 web/rdtool-orig/rdtool.html(插件目录不完整)")
            return {"CANCELLED"}
        url = "file:///" + path.replace("\\", "/")
        try:
            bpy.ops.wm.url_open(url=url)
            self.report({"INFO"}, "已在浏览器打开 RD 网页工具;选参后导出 JSON 再导入")
        except Exception:
            # url_open 受限时降级:提示手动打开
            self.report({"WARNING"}, f"自动打开受限,请手动打开: {path}")
        return {"FINISHED"}

