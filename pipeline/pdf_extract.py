# -*- coding: utf-8 -*-
"""PDF 文字层关键词扫描与导出（可迁移，无硬编码路径）。"""
import sys
from pathlib import Path


def extract_pages(pdf, out_dir, keys=None, max_pages=2000):
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    keys = keys or ["目录", "设计说明", "技术经济指标", "逐桩坐标", "直线", "曲线及转角",
                    "桥梁", "隧道", "渡槽", "平面交叉", "中央子午线", "坐标系统", "挡土墙", "涵洞"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    name = Path(pdf).stem
    res = ["=== %s 页数=%d ===" % (Path(pdf).name, doc.page_count)]
    hits = 0
    for i in range(min(doc.page_count, max_pages)):
        try:
            t = doc[i].get_text()
        except Exception:
            continue
        if not t:
            continue
        ks = [k for k in keys if k in t]
        if ks:
            hits += 1
            res.append("\n----- PDF页 %d [%s] -----\n%s" % (i + 1, ",".join(ks[:6]), t[:8000]))
    out = out_dir / (name + "_关键页.txt")
    out.write_text("\n".join(res), encoding="utf-8")
    print("已导出 %d 个关键页 -> %s" % (hits, out))
    return out
