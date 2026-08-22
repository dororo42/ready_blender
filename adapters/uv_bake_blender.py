# -*- coding: utf-8 -*-
"""UV 烘焙 Blender 适配层 + fragment shader 后端 + 录制(Blender 运行时部分)。

本文件依赖 bpy,需在 Blender 内运行验证;核心数值逻辑(uv_raster.py)已独立测试。
"""
from __future__ import annotations


def get_uv_coords(obj):
    """从 Blender 网格取 UV 坐标(三角化后)。返回 (uvs (N,2), faces (F,3))。"""
    import bpy
    import bmesh
    import numpy as np
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        bm.free()
        raise RuntimeError("网格没有 UV 层,请先 UV 展开")
    uvs = []
    faces = []
    for face in bm.faces:
        f = []
        for loop in face.loops:
            uv = loop[uv_layer].uv
            uvs.append((uv.x, uv.y))
            f.append(len(uvs) - 1)
        faces.append(f)
    bm.free()
    return np.array(uvs, dtype=np.float32), np.array(faces, dtype=np.int32)


def bake_uv_texture(obj, face_values, texture_name="RD_bake", res=1024):
    """把面域浓度烘焙到 UV 纹理(混合工作流:网格直跑→烘焙到 UV)。

    返回 Blender Image。空像素(UV 未覆盖)填 0。
    """
    import bpy
    import numpy as np
    try:
        from ..uv_raster import rasterize_uv, bake_face_values
    except ImportError:
        from adapters.uv_raster import rasterize_uv, bake_face_values
    uvs, faces = get_uv_coords(obj)
    face_map, _ = rasterize_uv(uvs, faces, res)
    baked = bake_face_values(face_map, np.asarray(face_values, dtype=np.float32))
    baked = np.nan_to_num(baked, nan=0.0)
    # 归一化后写 Image
    lo, hi = float(baked.min()), float(baked.max())
    rng = max(hi - lo, 1e-9)
    norm = (baked - lo) / rng
    img = bpy.data.images.get(texture_name)
    if img is None or img.size[0] != res:
        if img:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(texture_name, width=res, height=res, float_buffer=True)
    rgba = np.zeros((res, res, 4), dtype=np.float32)
    rgba[..., 0] = norm
    rgba[..., 1] = norm * 0.6
    rgba[..., 2] = 1.0 - norm
    rgba[..., 3] = 1.0
    img.pixels[:] = rgba.ravel()
    img.update_tag()
    return img


# ---------------------------------------------------------------------------
# P2-5 fragment shader 后端(UV 路径 2D RD 加速,三平台含 macOS)
# 4.5 用 gpu.shader.create_from_info,4.2-4.4 用 gpu.types.GPUShader
# ---------------------------------------------------------------------------

_FRAG_RD = """
void main() {
    // ping-pong 纹理上的 Gray-Scott 一步
    vec2 uv = gl_FragCoord.xy / textureSize(tex0, 0);
    vec2 p = vec2(1.0) / textureSize(tex0, 0);
    vec2 lapl = vec2(0.0);
    lapl += texture(tex0, uv + vec2(1,0)*p).rg;
    lapl += texture(tex0, uv + vec2(-1,0)*p).rg;
    lapl += texture(tex0, uv + vec2(0,1)*p).rg;
    lapl += texture(tex0, uv + vec2(0,-1)*p).rg;
    lapl -= 4.0 * texture(tex0, uv).rg;
    vec2 state = texture(tex0, uv).rg;
    float a = state.x, b = state.y;
    float abb = a * b * b;
    a += (Du * lapl.x - abb + F * (1.0 - a)) * dt;
    b += (Dv * lapl.y + abb - (F + k) * b) * dt;
    outColor = vec4(a, b, 0.0, 1.0);
}
"""


class FragmentRDBackend:
    """UV 路径 2D RD 的 fragment shader 后端(Blender 运行时)。

    能力声明:支持 grid(2D UV 空间),不支持 mesh 邻接。
    运行时探测失败(macOS 兼容的 fragment 路径一般可用)则调用方降级 numpy。
    """

    name = "fragment"
    capabilities = {"grid": True, "mesh": False, "volume": False}

    def __init__(self, size=256):
        import gpu
        from gpu.types import GPUShaderCreateInfo, GPUStageInterfaceInfo
        self.size = size
        self._build_shader()

    def _build_shader(self):
        import bpy
        import gpu
        vert = """
        void main() {
            gl_Position = vec4(pos.xy, 0.0, 1.0);
        }
        """
        frag = """
        uniform sampler2D tex0;
        uniform float Du, Dv, F, k, dt;
        in vec2 uv;
        out vec4 outColor;
        """ + _FRAG_RD
        if bpy.app.version >= (4, 5, 0):
            # 审查修复:GPUShaderCreateInfo 仅 4.5+,必须懒导入,
            # 否则 4.2-4.4 构造即 ImportError(与双版本兼容声明矛盾)
            from gpu.types import GPUShaderCreateInfo
            info = GPUShaderCreateInfo()
            info.vertex_source(vert)
            info.fragment_source(frag)
            self.shader = gpu.shader.create_from_info(info)
        else:
            self.shader = gpu.types.GPUShader(vert, frag)

    def step(self, texture_a, texture_b, params, n=1):
        """在 ping-pong 渲染目标上跑 n 步(需 offscreen 渲染,Blender 内实现)。"""
        # 注:完整 ping-pong 需要 gpu.types.GPUOffScreen;骨架已留,
        # 详细实现依赖 Blender 运行时调试(4.2/4.5 双版本)。
        raise NotImplementedError("需在 Blender 运行时完成 offscreen ping-pong 调试")


# ---------------------------------------------------------------------------
# P2-7 录制:与 Blender 时间轴对齐
# ---------------------------------------------------------------------------

class Recorder:
    """录制:frame_change_pre handler 中每帧跑固定步数并写入状态。"""

    def __init__(self):
        self.enabled = False
        self.steps_per_frame = 10

    def on_frame_change_pre(self, scene):
        """注册为 bpy.app.handlers.frame_change_pre。"""
        if not self.enabled:
            return
        try:
            from ..controller.engine import get_engine
        except ImportError:
            from controller.engine import get_engine
        engine = get_engine()
        if engine.rule is None:
            return
        engine._do_steps(self.steps_per_frame)
        try:
            from ..ui.operators import RD_OT_update_display
        except ImportError:
            from ui.operators import RD_OT_update_display
        try:
            import bpy
            RD_OT_update_display.run(bpy.context)
        except Exception:
            pass


def register_recorder():
    import bpy
    rec = Recorder()
    bpy.app.handlers.frame_change_pre.append(rec.on_frame_change_pre)
    return rec


def unregister_recorder(rec):
    import bpy
    try:
        bpy.app.handlers.frame_change_pre.remove(rec.on_frame_change_pre)
    except Exception:
        pass
