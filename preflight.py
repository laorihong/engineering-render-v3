# -*- coding: utf-8 -*-
"""一键环境体检：Python、依赖、Chrome、字体、模板、可选网络。
用法：python preflight.py [--network] [--config path/to/config.json]
"""
import argparse
import importlib
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check(name, ok, detail=""):
    print("%s  %s  %s" % ("[OK]" if ok else "[!!]", name, detail))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", action="store_true", help="顺便探测网络（瓦片服务可达性）")
    ap.add_argument("--config", default=None, help="配置文件路径（验证可解析）")
    args = ap.parse_args()
    print("== V3 工程效果图 · 环境体检 ==\n仓库: %s" % ROOT)
    ok_all = True
    ok_all &= check("Python >= 3.9", sys.version_info >= (3, 9), sys.version.split()[0])
    pdf_ok = False
    for mod in ("pymupdf", "fitz"):
        try:
            importlib.import_module(mod)
            pdf_ok = True
            break
        except Exception:
            continue
    ok_all &= check("PyMuPDF（pymupdf/fitz）", pdf_ok,
                    "缺失时 extract 不可用；pip install pymupdf")
    for mod, name in [("PIL", "Pillow"), ("docx", "python-docx")]:
        try:
            importlib.import_module(mod)
            ok_all &= check(name, True)
        except Exception:
            ok_all &= check(name, False, "pip install -r requirements.txt")
    chrome = None
    for c in [os.environ.get("CHROME_PATH", ""),
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/usr/bin/google-chrome", "/usr/bin/chromium"]:
        if c and os.path.exists(c):
            chrome = c
            break
    ok_all &= check("Chrome/Edge（静态渲染）", bool(chrome), chrome or "设置 CHROME_PATH 或仅跳过 render")
    font = any(os.path.exists(p) for p in
               [r"C:\Windows\Fonts\msyh.ttc", "/System/Library/Fonts/PingFang.ttc"])
    ok_all &= check("中文字体", font, "缺字体时 2D 图中文可能显示方框")
    three = ROOT / "templates" / "three.min.js"
    ok_all &= check("templates/three.min.js", three.exists(),
                    "缺失时 viewer 无 3D 引擎，需放入 three.js")
    cfg_ok = True
    if args.config and os.path.exists(args.config):
        try:
            sys.path.insert(0, str(ROOT))
            from pipeline.common import load_config
            cfg = load_config(args.config)
            cfg_ok &= check("配置文件解析", True, os.path.basename(args.config))
            cfg_ok &= check("geometry JSON", os.path.exists(cfg["_geometry"]), cfg.get("_geometry", ""))
            cfg_ok &= check("输出目录", os.path.isdir(os.path.join(cfg["_work"], "输出")),
                            os.path.join(cfg["_work"], "输出"))
        except Exception as e:
            cfg_ok &= check("配置文件解析", False, repr(e))
    if args.network:
        for url in ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer?f=pjson",
                    "https://ecn.t0.tiles.virtualearth.net"]:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    ok_all &= check("网络可达 " + url.split("/")[2], r.status == 200, r.status)
            except Exception as e:
                ok_all &= check("网络可达 " + url.split("/")[2], False, repr(e))
    print("\n结论：%s" % ("环境就绪" if ok_all else "存在缺失项，请按提示补齐"))
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
