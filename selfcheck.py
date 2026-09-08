# -*- coding: utf-8 -*-
"""仓库自检：演示产物完整性 + HTML 无残留占位符。"""
import os
from pathlib import Path

from PIL import Image

work = Path(__file__).resolve().parent / "work" / "demo"
out = work / "输出"
print("=== 演示输出 ===")
for p in sorted(out.iterdir()):
    print("%9.1f KB  %s" % (p.stat().st_size / 1024, p.name))
for h in (out / "看图台.html", out / "成果总览.html"):
    s = h.read_text(encoding="utf-8")
    print("%s 残留@@: %s" % (h.name, s.count("@@") > 0))
for n in ("viewer-panorama.png", "viewer-bridge.png"):
    im = Image.open(out / n)
    print(n, im.size, "黑屏?" , (sum(im.convert("L").getextrema()) / 510 < 0.05))
print("模板 three.min.js", (work.parent.parent / "templates" / "three.min.js").exists())
