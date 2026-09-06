# -*- coding: utf-8 -*-
"""组装 linusmossberg reaction-diffusion 完全本地化单文件 HTML。

- 内联:three.min.js / GPUComputationRenderer.min.js / SimplexNoise.js /
  dat.gui.min.js / 两个 glsl / presets.js / settings-gui.js / main.js / events.js
  / css(main.css + iconfont.ttf base64) / day-sunny.svg base64;
- 移除 Google Analytics 远程脚本(离线自包含);
- 新增:导出 JSON/CSV(Blender 导入链 schema)+ 版权声明(MIT 保留)。
"""
import base64
import os

SRC = r"C:\Users\Administrator\.openclaw-autoclaw\workspace\.cluster\linusmossberg-rd-analysis\reaction-diffusion-master"
OUT_DIR = r"C:\Users\Administrator\.openclaw-autoclaw\workspace\ready_blender\web"
os.makedirs(OUT_DIR, exist_ok=True)


def read(rel):
    with open(os.path.join(SRC, rel), encoding="utf-8") as f:
        return f.read()


def script(rel):
    body = read(rel)
    # 防止内容含 </script>(压缩库偶发)
    body = body.replace("</script", "<\\/script").replace("</SCRIPT", "<\\/SCRIPT")
    return f"<script>{body}</script>"


font_b64 = base64.b64encode(
    open(os.path.join(SRC, "css", "iconfont.ttf"), "rb").read()).decode()
sun_b64 = base64.b64encode(
    open(os.path.join(SRC, "data", "day-sunny.svg"), "rb").read()).decode()

css = read("css/main.css")
css = css.replace("url('iconfont.ttf')", f"url('data:font/truetype;base64,{font_b64}')")

html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width">
    <title>Reaction Diffusion (本地化版)</title>
    <style>{css}</style>
  </head>
  <body>
    <div id="draw">DRAW</div>
    <img id="light" src="data:image/svg+xml;base64,{sun_b64}" />
    <a id="save-link"></a>

    <div id="rd-toolbar">
      <span class="rd-brand">RD 本地化 · linusmossberg (MIT)</span>
      <button onclick="rdExportJSON()" title="导出当前参数为 JSON(Blender 插件可直接导入)">导出 JSON</button>
      <button onclick="rdExportCSV()" title="导出当前参数为 CSV(Excel 可读)">导出 CSV</button>
      <span class="rd-note">本地单文件 · 无网络依赖 · 预设 20 组</span>
    </div>
    <style>
      #rd-toolbar {{
        position: fixed; top: 8px; right: 8px; z-index: 99;
        background: rgba(20,20,20,.82); color: #eee;
        padding: 6px 10px; border-radius: 6px; font: 12px sans-serif;
        display: flex; gap: 8px; align-items: center;
        box-shadow: 0 2px 8px rgba(0,0,0,.4);
      }}
      #rd-toolbar button {{
        background: #fcac4e; border: 0; border-radius: 4px;
        padding: 4px 10px; font: 12px sans-serif; cursor: pointer;
      }}
      #rd-toolbar button:hover {{ background: #ffc37a; }}
      .rd-brand {{ font-weight: 700; }}
      .rd-note {{ color: #9ab; }}
    </style>

    {script("js/external/three.min.js")}
    {script("js/external/GPUComputationRenderer.min.js")}
    {script("js/external/SimplexNoise.js")}
    {script("js/external/dat.gui.min.js")}
    {script("shaders/reaction-diffusion.glsl")}
    {script("shaders/render.glsl")}
    {script("js/presets.js")}
    {script("js/settings-gui.js")}
    {script("js/main.js")}
    {script("js/events.js")}
    <script>
    /* ── 本地化附加:导出 JSON/CSV(Blender ready_blender 插件导入链 schema)── */
    function rdExportJSON() {{
      var p = {{
        id: 'lm_' + Date.now(),
        name: 'linusmossberg · ' + gui.preset,
        rule: 'Gray-Scott',
        params: {{
          Du: +(0.256 * Settings.diffusion_scale).toFixed(5),
          Dv: +(0.128 * Settings.diffusion_scale).toFixed(5),
          F: +Settings.feed.toFixed(5),
          k: +Settings.kill.toFixed(5),
          dt: 1.0,
          wrap: false
        }},
        seed_region: 'uniform_sparse',
        noise_ratio: 0.05,
        source: 'linusmossberg 网页导出(本地化版, MIT)',
        exported_at: new Date().toISOString(),
        extensions: {{
          pattern_scale: 1.0,
          style_map: {{
            noise_scale: Settings.environment_noise_scale,
            feed_variation: Settings.feed_variation,
            kill_variation: Settings.kill_variation,
            diffusion_scale_variation: Settings.diffusion_scale_variation
          }},
          orientation: {{ anisotropy: Settings.anisotropy }},
          flow: null
        }}
      }};
      var blob = new Blob([JSON.stringify(p, null, 2)], {{type: 'application/json'}});
      var a = document.createElement('a');
      a.download = 'rd-preset-' + gui.preset.replace(/[^a-z0-9]+/gi, '-').toLowerCase() + '.json';
      a.href = URL.createObjectURL(blob);
      document.body.appendChild(a);
      a.click();
      setTimeout(function() {{ URL.revokeObjectURL(a.href); a.remove(); }}, 5000);
    }}

    function rdExportCSV() {{
      var rows = [
        ['parameter', 'value'],
        ['name', gui.preset],
        ['Du', (0.256 * Settings.diffusion_scale).toFixed(5)],
        ['Dv', (0.128 * Settings.diffusion_scale).toFixed(5)],
        ['F', Settings.feed.toFixed(5)],
        ['k', Settings.kill.toFixed(5)],
        ['dt', '1.0'],
        ['diffusion_scale', Settings.diffusion_scale],
        ['feed_variation', Settings.feed_variation],
        ['kill_variation', Settings.kill_variation],
        ['diffusion_scale_variation', Settings.diffusion_scale_variation],
        ['anisotropy', Settings.anisotropy],
        ['environment_noise_scale', Settings.environment_noise_scale],
        ['separate_fields', Settings.separate_fields]
      ];
      var csv = rows.map(function(r) {{ return r.join(','); }}).join('\\n');
      var blob = new Blob([csv], {{type: 'text/csv'}});
      var a = document.createElement('a');
      a.download = 'rd-preset-' + gui.preset.replace(/[^a-z0-9]+/gi, '-').toLowerCase() + '.csv';
      a.href = URL.createObjectURL(blob);
      document.body.appendChild(a);
      a.click();
      setTimeout(function() {{ URL.revokeObjectURL(a.href); a.remove(); }}, 5000);
    }}
    </script>

    <!--
    ============================================================
    本地化版(单文件自包含)说明
    ------------------------------------------------------------
    原始项目: https://github.com/linusmossberg/reaction-diffusion
    原始演示: https://linusmossberg.github.io/reaction-diffusion
    许可: MIT License, Copyright (c) 2020 Linus Mossberg
    本地化: 移除 Google Analytics 与外部引用;内联全部依赖;
            新增"导出 JSON/CSV"(schema 与 Blender ready_blender
            插件 fileio/preset_io.py 一致,可直接导入)。
    MIT License 全文:
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    ============================================================
    -->
  </body>
</html>
"""

out = os.path.join(OUT_DIR, "reaction-diffusion.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"written: {out} ({os.path.getsize(out)/1024:.0f} KB)")

# 自检:无外部 http 引用
import re
ext = re.findall(r'(?:src|href)="(https?:[^"]+)"', html)
print("外部引用:", ext if ext else "无(完全离线)")