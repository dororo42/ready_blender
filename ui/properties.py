# -*- coding: utf-8 -*-
"""属性组:Scene.ready_settings(仅存 UI 参数,不存模拟状态)。"""
import bpy


# 审查修复:参数滑块 update 回调 → 同步引擎并标 dirty(热更新)
# B1 修复:域/目标对象变更时自动重建引擎(rebuild 触发路径)
# 2D 模式自动转 Image Editor(复用优先,记录原区域类型,切回 3D 时还原)
_auto_ie_area = None  # (area, original_type)


def _ensure_image_editor(context):
    """切到 2D 模式时确保有一个 Image Editor 显示 RD_preview。"""
    global _auto_ie_area
    import bpy as _bpy
    screen = getattr(context, "screen", None)
    if screen is None:
        return
    # 已有 IMAGE_EDITOR:直接复用
    for area in screen.areas:
        if area.type == "IMAGE_EDITOR":
            sp = getattr(area.spaces, "active", None)
            img = _bpy.data.images.get("RD_preview")
            if sp is not None and img is not None:
                sp.image = img
            return
    # 没有则转换一个非当前区域(优先其他 VIEW_3D/PROPERTIES/OUTLINER)
    current = getattr(context, "area", None)
    for area in screen.areas:
        if area is current:
            continue
        if area.type in ("VIEW_3D", "PROPERTIES", "OUTLINER", "NODE_EDITOR"):
            _auto_ie_area = (area, area.type)
            area.type = "IMAGE_EDITOR"
            return
    # 兜底:只剩当前区域时转换当前区域
    for area in screen.areas:
        if area.type == "VIEW_3D":
            _auto_ie_area = (area, area.type)
            area.type = "IMAGE_EDITOR"
            return


def _restore_area():
    """切回 3D 模式时把自动转换的区域还原。"""
    global _auto_ie_area
    if _auto_ie_area is None:
        return
    area, old_type = _auto_ie_area
    _auto_ie_area = None
    try:
        area.type = old_type
    except Exception:
        pass


def _domain_changed(self, context):
    try:
        if getattr(self, "field_kind", "") == "grid":
            _ensure_image_editor(context)
        else:
            _restore_area()
    except Exception:
        pass
    # grow3d:一次性生成管道,不依赖引擎;切换时自动填入文献口径预设参数
    if getattr(self, "field_kind", "") == "grow3d":
        try:
            self.param_Du = 0.082
            self.param_Dv = 0.041
            self.param_F = 0.035
            self.param_k = 0.064
            self.param_dt = 1.0
        except Exception:
            pass
        return
    try:
        try:
            from .operators import init_engine_from_settings
        except ImportError:
            from ui.operators import init_engine_from_settings
        from ..controller.engine import get_engine
    except ImportError:
        from controller.engine import get_engine
    try:
        eng = get_engine()
        if eng.rule is not None:
            init_engine_from_settings(context)
    except Exception:
        pass


# 调速:速度(步/秒)→ 每 tick 步数(固定 20 tick/秒)
def _speed_changed(self, context):
    try:
        self.tick_interval = 0.05
        self.tick_steps = max(1, min(2000, round(self.speed_steps_per_sec / 20)))
    except Exception:
        pass

def _param_changed(self, context):
    try:
        try:
            from ..controller.engine import get_engine
        except ImportError:
            from controller.engine import get_engine
        eng = get_engine()
        if eng.rule is None:
            return
        # 仅 Gray-Scott 系统同步五个滑块;公式系统参数为文献默认值
        if getattr(self, "system_enum", "gray_scott") != "gray_scott":
            return
        try:
            from ..core.parameter import scale_params
        except ImportError:
            from core.parameter import scale_params
        Du_eff, Dv_eff, dt_eff, n_sub = scale_params(
            self.param_Du, self.param_Dv, self.param_dt,
            getattr(self, "pattern_scale", 1.0))
        eng.params.update({
            "Du": Du_eff, "Dv": Dv_eff,
            "F": self.param_F, "k": self.param_k,
            "dt": dt_eff, "wrap": self.grid_wrap, "_n_sub": n_sub,
        })
        eng.mark_dirty("hot")
    except Exception:
        pass


def _formula_variant_items(self, context):
    try:
        sid = getattr(self, "system_enum", "gray_scott")
        try:
            from ..presets import presets as _p
        except ImportError:
            from presets import presets as _p
        items = [("default", "文献默认", "使用该系统的文献默认参数")]
        for v in _p.get_variants(sid):
            items.append((v["id"], v["name"], ""))
        return items
    except Exception:
        return [("default", "文献默认", "")]


def _mesh_poll(self, obj):
    """Target Mesh 只允许网格物体(灯光/相机等不出现)。"""
    return obj is not None and obj.type == "MESH"


class ReadySettings(bpy.types.PropertyGroup):
    """UI 参数属性组。模拟状态在 controller/engine.py 的单例中,不挂 Scene。"""

    # 系统与网格
    rule_name: bpy.props.StringProperty(
        name="Rule", default="Gray-Scott",
        description="反应扩散规则(当前仅 Gray-Scott)")
    formula_variant: bpy.props.EnumProperty(
        name="参数变体",
        description="当前公式系统的参数变体(文献典型值;GS 系统不使用)",
        items=_formula_variant_items)
    system_enum: bpy.props.EnumProperty(
        name="系统 / System",
        items=[
            ("gray_scott", "Gray-Scott", "斑点/珊瑚/蠕虫/混沌(内置内核)"),
            ("fitzhugh_nagumo", "FitzHugh-Nagumo", "兴奋波/神经传导(FitzHugh 1961)"),
            ("brusselator", "Brusselator", "图灵斑图(Prigogine & Lefever 1968)"),
            ("schnakenberg", "Turing (Schnakenberg)", "图灵斑图/条纹(Schnakenberg 1979)"),
            ("oregonator", "Oregonator (BZ)", "Belousov-Zhabotinsky 化学波(Field & Noyes 1974)"),
            ("oil_water", "Oil-Water 相分离", "两相随机混合→相分离(Agmon 2014);参数固定,白噪声自动初始化,支持 2D 网格与 3D 网格(图邻域)"),
        ],
        default="gray_scott",
        update=_domain_changed)
    target_object: bpy.props.PointerProperty(
        name="Target Mesh", type=bpy.types.Object,
        description="应用反应扩散的目标网格对象(仅网格物体可选)",
        poll=_mesh_poll,
        update=_domain_changed)
    field_kind: bpy.props.EnumProperty(
        name="Domain",
        items=[
            ("grid", "规则网格 (2D)", "256² 规则网格,显示在 Image Editor"),
            ("mesh", "网格 (MeshRD)", "在目标网格面上求解"),
            ("grow3d", "3D 生长 (Grow3D)", "体素 Gray-Scott 生长→光滑等值面网格(一次性生成独立对象)"),
        ],
        default="mesh",
        update=_domain_changed)

    # Gray-Scott 参数
    param_Du: bpy.props.FloatProperty(name="Du", default=0.16, min=0.0, max=1.0, precision=4, update=_param_changed)
    param_Dv: bpy.props.FloatProperty(name="Dv", default=0.08, min=0.0, max=1.0, precision=4, update=_param_changed)
    param_F: bpy.props.FloatProperty(name="F", default=0.0367, min=0.0, max=0.2, precision=4, update=_param_changed)
    param_k: bpy.props.FloatProperty(name="k", default=0.0649, min=0.0, max=0.2, precision=4, update=_param_changed)
    param_dt: bpy.props.FloatProperty(name="dt", default=1.0, min=0.05, max=2.0, precision=2, update=_param_changed)
    pattern_scale: bpy.props.FloatProperty(
        name="图案缩放", default=1.0, min=0.25, max=2.5, precision=2, update=_param_changed,
        description="图案波长缩放(不移动 F/k 在参数空间的位置):Du/Dv × s²;放大时自动子步保护数值稳定")

    # ── 扩展参数:Orientation(各向异性扩散) 与 Flow(空间平流) ──
    orientation_kind: bpy.props.EnumProperty(
        name="取向类型",
        items=[
            ("none", "关闭", "等向扩散(默认)"),
            ("linear", "线性(竖直)", "全图统一竖直方向(90°),strength 越强图案越条纹化"),
            ("horizontal", "线性(水平)", "全图统一水平方向(0°)"),
            ("radial", "径向", "取向指向圆心"),
            ("circles", "同心圆", "取向沿圆周切向"),
            ("swirl", "旋涡", "径向与切向各半"),
            ("bubble", "气泡", "内部向外、越过半径反向"),
        ],
        default="none", update=_param_changed)
    orientation_strength: bpy.props.FloatProperty(
        name="取向强度", default=0.0, min=0.0, max=0.95, precision=2, update=_param_changed,
        description="各向异性强度 0~0.95;0=等向。仅 grid 模式(Gray-Scott)生效")
    flow_kind: bpy.props.EnumProperty(
        name="流动类型",
        items=[
            ("none", "关闭", "无平流(默认)"),
            ("vertical", "竖直", "全场整体上移"),
            ("radial", "外扩", "自中心向外扩散"),
            ("rotate", "旋转", "整体绕中心旋转"),
            ("swirl", "旋涡", "内慢外快的旋转"),
            ("bubble", "气泡", "中心区外扩,远端衰减"),
            ("ring", "环形", "峰值在中间半径的旋转带"),
            ("vortex", "涡旋", "中心强、边缘弱的旋转"),
        ],
        default="none", update=_param_changed)
    flow_strength: bpy.props.FloatProperty(
        name="流动强度", default=0.0, min=0.0, max=1.0, precision=3, update=_param_changed,
        description="平流速度强度;仅 grid 模式(Gray-Scott)生效")

    # 运行
    tick_steps: bpy.props.IntProperty(name="Steps per Tick", default=50, min=1, max=2000)
    tick_interval: bpy.props.FloatProperty(name="Tick Interval (s)", default=0.05, min=0.01, max=1.0)
    speed_steps_per_sec: bpy.props.IntProperty(
        name="速度(步/秒)", default=1000, min=20, max=2000,
        description="预览速度目标;实际受 CPU 算力限制(256² 约 780 步/秒)",
        update=_speed_changed)
    bake_steps: bpy.props.IntProperty(name="Bake Steps", default=10000, min=100, max=1000000)
    progress: bpy.props.FloatProperty(name="Progress", default=0.0, min=0.0, max=1.0, subtype="FACTOR")
    is_baking: bpy.props.BoolProperty(name="Is Baking", default=False)

    # 显示
    colormap: bpy.props.EnumProperty(
        name="Colormap",
        items=[("viridis", "Viridis", ""), ("magma", "Magma", ""), ("gray", "Grayscale", "")],
        default="viridis")
    colormap_range: bpy.props.EnumProperty(
        name="Range",
        items=[
            ("auto", "自动(min/max)", "每帧自适应归一化(演化过程颜色会漂移)"),
            ("fixed_b", "固定 b[0,0.5]", "b 场固定范围 0~0.5,演化过程颜色稳定(B9)"),
            ("fixed_a", "固定 a[0,1]", "a 场固定范围 0~1"),
        ],
        default="auto")
    active_chemical: bpy.props.EnumProperty(
        name="Chemical",
        items=[("a", "a (substrate)", ""), ("b", "b (catalyst)", "")],
        default="b")
    output_mode: bpy.props.EnumProperty(
        name="Output Mode",
        items=[
            ("attribute", "命名属性 (GN)", "写入 FACE 域命名属性 RD_value"),
            ("vertex_color", "顶点色", "写入顶点色层 RD_value(视口需切着色为属性/顶点色才可见)"),
            ("displacement", "置换属性", "写入 POINT 域置换属性 RD_disp"),
        ],
        default="vertex_color")

    # 画笔
    brush_radius: bpy.props.IntProperty(name="Brush Radius", default=8, min=1, max=64)
    brush_value: bpy.props.FloatProperty(name="Brush Value", default=1.0, min=0.0, max=1.0)

    def _brush_chem_update(self, context):
        """画笔化学品切换联动(修复"涂 a 无反馈"):
        1) 显示化学品同步为涂抹化学品——涂什么看什么;
        2) 智能默认值:a 场初始恒为 1.0,b 场初始恒为 0.0,
           若当前笔值在新化学品上"不可见"(等于其本底值),自动翻到对侧极值。"""
        try:
            if self.brush_chemical != self.active_chemical:
                self.active_chemical = self.brush_chemical
            if self.brush_chemical == "a" and self.brush_value >= 0.999:
                self.brush_value = 0.0  # a 本底=1,涂 1 等于没涂 → 翻为挖底
            elif self.brush_chemical == "b" and self.brush_value <= 0.001:
                self.brush_value = 1.0  # b 本底=0,涂 0 等于没涂 → 翻为满值
        except Exception:
            pass

    brush_chemical: bpy.props.EnumProperty(
        name="Brush Chemical",
        items=[("a", "a", ""), ("b", "b", "")],
        default="b",
        update=_brush_chem_update)
    noise_ratio: bpy.props.FloatProperty(name="Noise Ratio", default=0.05, min=0.0, max=1.0)
    seed_region: bpy.props.EnumProperty(
        name="Seed Region",
        items=[
            ("uniform_sparse", "均匀稀疏种子", "随机点撒满全表面(密度=种子密度),图案满铺,推荐"),
            ("global", "全局稀疏", "全网格稀疏扰动,密度 = Noise Ratio"),
            ("center_square", "中心方块", "网格中央方形区域全扰动(Pearson 式;覆盖受波前速度限制)"),
            ("center_disc", "中心圆盘", "网格中央圆形区域全扰动(Pearson 式;覆盖受波前速度限制)"),
        ],
        default="uniform_sparse")

    # 网格
    grid_size: bpy.props.IntProperty(name="Grid Size", default=256, min=32, max=1024)
    grid_wrap: bpy.props.BoolProperty(name="Wrap", default=True)
    cv_threshold: bpy.props.FloatProperty(name="Density CV Threshold", default=0.5, min=0.1, max=2.0)
    mesh_min_angle: bpy.props.FloatProperty(name="Sliver Min Angle", default=20.0, min=5.0, max=45.0)
    mesh_target_density: bpy.props.FloatProperty(name="Target Face Density", default=12.0, min=1.0, max=500.0)
    use_subdivide: bpy.props.BoolProperty(
        name="细分网格", default=False,
        description="勾选后可生成细分副本(Subdivision Surface 应用后)获得更高密度网格")
    subdivide_levels: bpy.props.IntProperty(
        name="细分级别", default=1, min=1, max=7,
        description="Subdivision Surface 级别;面数约 ×4^级别(7 级约 ×16k,谨防内存不足)")
    use_remesh: bpy.props.BoolProperty(
        name="Remesh 网格", default=False,
        description="勾选后可生成 Voxel Remesh 副本(均匀体素重网格化,与细分不同:保持顶点分布均匀)")
    remesh_target_faces: bpy.props.IntProperty(
        name="目标面数", default=20000, min=1000, max=1000000,
        description="Voxel Remesh 目标面数(按表面积估算 voxel 尺寸)")

    # 网格质量报告(由 RD_OT_mesh_prep 写入,面板只读展示)
    mesh_report_n_verts: bpy.props.IntProperty(name="Report Verts", default=0)
    mesh_report_n_faces: bpy.props.IntProperty(name="Report Faces", default=0)
    mesh_report_category: bpy.props.StringProperty(name="Report Category", default="")
    mesh_report_edge_ratio: bpy.props.FloatProperty(name="Report Edge Ratio", default=0.0)
    mesh_report_sliver: bpy.props.FloatProperty(name="Report Sliver", default=0.0)
    mesh_report_cv: bpy.props.FloatProperty(name="Report CV", default=0.0)
    mesh_report_density: bpy.props.FloatProperty(name="Report Density", default=0.0)
    mesh_report_quantity_ok: bpy.props.BoolProperty(name="Report Quantity OK", default=False)
    mesh_report_uniform_ok: bpy.props.BoolProperty(name="Report Uniform OK", default=False)
    mesh_report_text: bpy.props.StringProperty(name="Report Text", default="")
    mesh_displacement_strength: bpy.props.FloatProperty(
        name="顶点凹凸强度", default=0.1, min=-0.5, max=0.5,
        description="一键顶点凹凸的位移幅度(沿法线)")
    vertex_seed_ratio: bpy.props.FloatProperty(
        name="种子密度", default=0.05, min=0.005, max=0.5,
        description="均匀稀疏种子(uniform_sparse)与顶点凹凸的种子比例;提高可加速铺满(比例制,与网格规模无关,系统会自校正到自然密度)")
    # 3D 生长管道(体素 Gray-Scott → 等值面网格)
    grow3d_size: bpy.props.IntProperty(
        name="体素分辨率", default=48, min=16, max=96,
        description="3D 生长管道每轴体素数 N;场为 N³,耗时与内存随 N³ 增长(48≈10 秒/1500 步,96≈80 秒)")
    grow3d_steps: bpy.props.IntProperty(
        name="迭代步数", default=1500, min=100, max=8000,
        description="3D 生长管道迭代步数;步数越多管道延伸越远(受波前速度限制)")
    grow3d_threshold: bpy.props.FloatProperty(
        name="等值面阈值", default=0.35, min=0.05, max=0.6,
        description="b 场等值面提取阈值;调低→结构更粗,调高→仅保留高浓度核心")
    rng_seed: bpy.props.IntProperty(
        name="随机种子", default=42, min=0, max=2**31 - 1,
        description="初始条件随机种子(同参数同种子结果可复现)")
    use_numba: bpy.props.BoolProperty(
        name="Numba 加速", default=True,
        description="勾选且已安装 Numba 时,顶点凹凸与 3D 生长管道走 JIT 加速;否则用 numpy 回退")
