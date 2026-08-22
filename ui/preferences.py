# -*- coding: utf-8 -*-
"""Numba 偏好配置(Pro v6 式):镜像源/安装/自检,可选依赖不捆绑。

改良(v1.4 报告 2.3 建议):安装后做 import numba 自检并报告,而非仅依赖 pip 返回码。
"""
import bpy

MIRRORS = [
    ("default", "默认官方源", "https://pypi.org/simple"),
    ("tsinghua", "清华大学镜像", "https://pypi.tuna.tsinghua.edu.cn/simple"),
    ("aliyun", "阿里云镜像", "https://mirrors.aliyun.com/pypi/simple"),
]


def _addon_pkg():
    """插件根包名(修复 N13:扩展模式包名为 bl_ext.<repo>.ready_blender,
    硬编码 "ready_blender" 会导致 AddonPreferences 注册失败被静默吞掉)。"""
    pkg = __package__ or ""
    return pkg.rsplit(".", 1)[0] if pkg.startswith("bl_ext.") else "ready_blender"


class ReadyPreferences(bpy.types.AddonPreferences):
    bl_idname = _addon_pkg()

    mirror_source: bpy.props.EnumProperty(
        name="镜像源", items=[(m[0], m[1], m[2]) for m in MIRRORS], default="default")
    custom_mirror: bpy.props.StringProperty(name="自定义镜像 URL", default="")
    use_numba: bpy.props.BoolProperty(name="启用 Numba 加速", default=True,
                                      description="已安装 Numba 时顶点域路径自动加速")

    def draw(self, context):
        layout = self.layout
        try:
            from ..backend.numba_backend import numba_status
        except ImportError:
            from backend.numba_backend import numba_status
        available, msg = numba_status()
        box = layout.box()
        box.label(text="Numba 加速引擎(可选)", icon="TIME")
        if available:
            box.label(text=f"✓ {msg}", icon="CHECKMARK")
        else:
            box.label(text=f"✗ {msg}", icon="ERROR")
            box.label(text="提示:不装也能用,自动回退 numpy 路径", icon="INFO")
        box.prop(self, "use_numba")
        box.separator()
        box.prop(self, "mirror_source")
        row = box.row()
        row.label(text="或自定义:")
        row.prop(self, "custom_mirror", text="")
        row2 = box.row(align=True)
        row2.operator("ready.numba_install", text="安装", icon="IMPORT")
        row2.operator("ready.numba_check", text="自检", icon="INFO")


def _get_mirror_url(prefs):
    if prefs.custom_mirror.strip():
        return prefs.custom_mirror.strip()
    return dict((m[0], m[2]) for m in MIRRORS).get(prefs.mirror_source, MIRRORS[0][2])


class RD_OT_numba_install(bpy.types.Operator):
    """pip 安装 numba(可选依赖,用户自助;官方平台规则允许运行时引导安装)。"""
    bl_idname = "ready.numba_install"
    bl_label = "Install Numba"
    bl_options = {"REGISTER"}

    def execute(self, context):
        import subprocess, sys
        prefs = context.preferences.addons[_addon_pkg()].preferences
        url = _get_mirror_url(prefs)
        host = url.split("//")[1].split("/")[0]
        self.report({"INFO"}, f"正在从 {url} 安装 Numba...")
        try:
            cmd = [sys.executable, "-m", "pip", "install", "numba",
                   "-i", url, "--trusted-host", host, "--no-warn-script-location"]
            subprocess.check_call(cmd)
        except Exception as e:
            self.report({"ERROR"}, f"pip 安装失败: {e}")
            return {"CANCELLED"}
        # 改良:安装后 import 自检(而非仅依赖 pip 返回码)
        try:
            from ..backend.numba_backend import numba_status
        except ImportError:
            from backend.numba_backend import numba_status
        available, msg = numba_status()
        if available:
            self.report({"INFO"}, f"安装成功且自检通过: {msg}")
        else:
            self.report({"WARNING"}, f"安装完成但自检未通过: {msg}(请重启 Blender 后重试)")
        return {"FINISHED"}


class RD_OT_numba_check(bpy.types.Operator):
    bl_idname = "ready.numba_check"
    bl_label = "Check Numba"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            from ..backend.numba_backend import numba_status
        except ImportError:
            from backend.numba_backend import numba_status
        available, msg = numba_status()
        self.report({"INFO"} if available else {"WARNING"}, msg)
        return {"FINISHED"}
