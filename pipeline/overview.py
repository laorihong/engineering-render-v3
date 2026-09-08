# -*- coding: utf-8 -*-
"""成果总览（单文件 HTML，图片内嵌）。"""
from pathlib import Path

from .common import image_to_data_uri, log


def build_overview(cfg, out_name="成果总览.html", images=None, links=None):
    out_dir = Path(cfg["_work"]) / "输出"
    imgs = images or cfg.get("images_for_overview", [])
    cards = []
    for name in imgs:
        p = out_dir / name
        if not p.exists():
            continue
        uri = image_to_data_uri(p, 2100, 84)
        cards.append('<div class="card"><h2>%s</h2><img style="width:100%%;border-radius:8px" src="%s"></div>'
                     % (name, uri))
    links_html = ""
    for lk in (links or cfg.get("viewer_files", [])):
        if (out_dir / lk).exists():
            links_html += '<a href="%s" target="_blank">%s</a>' % (lk, lk)
    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>@@TITLE@@</title>
<style>body{margin:0;background:#0b1724;color:#e8eef3;font-family:"Microsoft YaHei",sans-serif}
.top{padding:16px 22px;background:linear-gradient(90deg,#12395e,#0d2740);font-size:22px;font-weight:bold}
.wrap{max-width:1400px;margin:0 auto;padding:24px}
.card{background:#132b42;border:1px solid #23455f;border-radius:14px;padding:16px;margin:16px 0}
h2{color:#ffd27d;font-size:19px}
a{display:inline-block;background:#2f7fd0;color:#fff;text-decoration:none;padding:9px 14px;border-radius:8px;margin:4px}
.note{color:#9fb6c8;font-size:13px}</style></head><body>
<div class="top">@@TITLE@@</div>
<div class="wrap"><div class="card"><div class="note">单文件成果总览；图片均已内嵌。看图台需与总览同一目录。</div>@@LINKS@@</div>
@@CARDS@@</div></body></html>"""
    html = (html.replace("@@TITLE@@", cfg["project"]["name"] + " · 成果总览")
            .replace("@@LINKS@@", links_html)
            .replace("@@CARDS@@", "\n".join(cards)))
    out = out_dir / out_name
    out.write_text(html, encoding="utf-8")
    log("总览已保存 %s (%.1f MB)" % (out, out.stat().st_size / 1e6))
    return out
