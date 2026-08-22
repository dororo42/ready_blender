# -*- coding: utf-8 -*-
"""网格生成器(几何自实现,输出 verts + faces)。净室实现,几何来自公开构造。

覆盖:三角网格 / 六角网格 / rhombille / 测地球面(二十面体细分)/ 环面。
(Delaunay/Voronoi/BCC/FCC/Penrose 在后续增量;Penrose 需替换式平铺约 300 行,单独提交。)
"""
from __future__ import annotations
import numpy as np


def triangular(nx: int, ny: int, scale: float = 1.0):
    """三角网格:nx×ny 顶点,每个方格 2 个三角形。返回 (verts (N,3) float32, faces (F,3) int32)。

    注意(审查修复):用 meshgrid(indexing="xy") 保证行主序展平索引 = j*nx+i,
    与 faces 循环的 p = j*nx+i 一致;两三角形绕序均为 +z 外向。
    """
    xs = np.arange(nx, dtype=np.float32) * scale
    ys = np.arange(ny, dtype=np.float32) * scale
    xv, yv = np.meshgrid(xs, ys, indexing="xy")
    verts = np.stack([xv, yv], axis=-1).reshape(-1, 2)
    verts = np.concatenate([verts, np.zeros((len(verts), 1), np.float32)], axis=1)
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            p = j * nx + i
            faces.append([p, p + 1, p + nx + 1])
            faces.append([p, p + nx + 1, p + nx])
    return verts, np.array(faces, dtype=np.int32)


def hexagonal(nx: int, ny: int, scale: float = 1.0):
    """六角网格(pointy-top):每个六角拆 6 个三角形,蜂窝平铺。

    审查修复:原实现间距错误(水平 1.5s/垂直 √3s),相邻六角共享顶点不重合;
    修正为标准 pointy-top 格:水平 √3·s、垂直 1.5·s、奇行偏移 √3/2·s,
    再加 _weld 焊接共享顶点。
    """
    s = 1.0 * scale
    dx = np.sqrt(3.0) * s
    dy = 1.5 * s
    verts = []
    faces = []
    for j in range(ny):
        for i in range(nx):
            cx = i * dx + (0.5 * dx if j % 2 else 0.0)
            cy = j * dy
            base = len(verts)
            for k in range(6):
                ang = np.pi / 6 + k * np.pi / 3
                verts.append([cx + s * np.cos(ang), cy + s * np.sin(ang), 0.0])
            c = len(verts)
            verts.append([cx, cy, 0.0])
            for k in range(6):
                faces.append([c, base + k, base + (k + 1) % 6])
    return _weld(np.array(verts, dtype=np.float32), np.array(faces, dtype=np.int32))


def _weld(verts, faces, tol=1e-4):
    """按坐标焊接重复顶点(浮点舍入去重),返回 (welded_verts, remapped_faces)。"""
    rounded = np.round(verts / tol).astype(np.int64)
    _, inverse = np.unique(rounded, axis=0, return_inverse=True)
    welded = np.zeros((len(np.unique(inverse)), 3), dtype=np.float32)
    for i, idx in enumerate(inverse):
        welded[idx] = verts[i]
    return welded, inverse[faces].astype(np.int32)


def rhombille(nx: int, ny: int, scale: float = 1.0):
    """Rhombille 平铺(三菱形拼六角)。每个菱形拆 2 个三角形。

    审查修复:采用与 hexagonal 相同的 pointy-top 格(水平 √3·s、垂直 1.5·s),
    每个菱形 = 中心 + 两相邻六角顶点 + 邻居中心(顶点向量和),焊接共享点。
    """
    s = 1.0 * scale
    dx = np.sqrt(3.0) * s
    dy = 1.5 * s
    verts = []
    faces = []
    for j in range(ny):
        for i in range(nx):
            cx = i * dx + (0.5 * dx if j % 2 else 0.0)
            cy = j * dy
            c = len(verts)
            verts.append([cx, cy, 0.0])
            ring = []
            for k in range(6):
                ang = np.pi / 6 + k * np.pi / 3
                verts.append([cx + s * np.cos(ang), cy + s * np.sin(ang), 0.0])
                ring.append(len(verts) - 1)
            for k in range(6):
                v1 = verts[ring[k]]
                v2 = verts[ring[(k + 1) % 6]]
                # 邻居中心 = 中心 + (v1−中心) + (v2−中心)
                nx_v = cx + (v1[0] - cx) + (v2[0] - cx)
                ny_v = cy + (v1[1] - cy) + (v2[1] - cy)
                n = len(verts)
                verts.append([nx_v, ny_v, 0.0])
                faces.append([c, ring[k], n])
                faces.append([c, n, ring[(k + 1) % 6]])
    return _weld(np.array(verts, dtype=np.float32), np.array(faces, dtype=np.int32))


def geodesic_sphere(subdivisions: int = 2, radius: float = 1.0):
    """测地球面:二十面体细分。subdivisions 越大越密。"""
    t = (1.0 + np.sqrt(5.0)) / 2.0
    base_verts = np.array([
        [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
        [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
        [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
    ], dtype=np.float64)
    base_verts /= np.linalg.norm(base_verts, axis=1, keepdims=True)
    base_faces = np.array([
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ], dtype=np.int32)
    verts = [tuple(v) for v in base_verts]
    faces = [list(f) for f in base_faces]
    edge_pts = {}
    for _ in range(subdivisions):
        new_faces = []
        for f in faces:
            mids = []
            for k in range(3):
                a, b = f[k], f[(k + 1) % 3]
                key = (min(a, b), max(a, b))
                if key not in edge_pts:
                    m = tuple((np.array(verts[a]) + np.array(verts[b])) / 2.0)
                    m = m / np.linalg.norm(m)
                    edge_pts[key] = len(verts)
                    verts.append(m)
                mids.append(edge_pts[key])
            a, b, c = f
            ab, bc, ca = mids
            new_faces += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
        faces = new_faces
    verts = np.array(verts, dtype=np.float32) * radius
    return verts, np.array(faces, dtype=np.int32)


def torus(nu: int = 48, nv: int = 24, R: float = 1.0, r: float = 0.4):
    """环面(四边形网格,每格拆 2 三角形)。"""
    verts = []
    for j in range(nv):
        for i in range(nu):
            u = 2 * np.pi * i / nu
            v = 2 * np.pi * j / nv
            verts.append([(R + r * np.cos(v)) * np.cos(u),
                          (R + r * np.cos(v)) * np.sin(u),
                          r * np.sin(v)])
    faces = []
    for j in range(nv):
        for i in range(nu):
            p = j * nu + i
            q = j * nu + (i + 1) % nu
            s = ((j + 1) % nv) * nu + i
            t = ((j + 1) % nv) * nu + (i + 1) % nu
            faces.append([p, q, t])
            faces.append([p, t, s])
    return np.array(verts, dtype=np.float32), np.array(faces, dtype=np.int32)
