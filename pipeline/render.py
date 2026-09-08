# -*- coding: utf-8 -*-
"""headless Chrome 静态渲染（2560×1440 归一化）。"""
import os
import subprocess
import time
from pathlib import Path

from PIL import Image

from .common import find_chrome, log

TARGET = (2560, 1440)


def render_html(html, view, out_png, chrome=None, window=(2596, 1591)):
    chrome = chrome or find_chrome()
    if not chrome:
        raise SystemExit("未找到 Chrome/Edge（可设置环境变量 CHROME_PATH）")
    profile = Path(os.environ.get("TEMP", "/tmp")) / ("v3chrome_" + str(int(time.time())))
    profile.mkdir(parents=True, exist_ok=True)
    url = Path(html).resolve().as_uri() + ("?v=" + view)
    cmd = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
           "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
           "--hide-scrollbars", "--user-data-dir=%s" % profile,
           "--window-size=%d,%d" % window, "--virtual-time-budget=9000",
           "--screenshot=%s" % out_png, url]
    log("渲染 %s (%s)" % (os.path.basename(out_png), view))
    subprocess.run(cmd, check=False, capture_output=True)
    wait = 0
    while not os.path.exists(out_png) and wait < 60:
        time.sleep(0.5)
        wait += 1
    if not os.path.exists(out_png):
        raise RuntimeError("Chrome 未生成截图: %s" % view)
    _normalize(out_png)
    return out_png


def _normalize(png):
    im = Image.open(png).convert("RGB")
    if im.size != TARGET:
        sc = max(TARGET[0] / im.size[0], TARGET[1] / im.size[1])
        nw, nh = int(im.size[0] * sc), int(im.size[1] * sc)
        im2 = im.resize((nw, nh), Image.LANCZOS)
        x0, y0 = (nw - TARGET[0]) // 2, (nh - TARGET[1]) // 2
        im = im2.crop((x0, y0, x0 + TARGET[0], y0 + TARGET[1]))
        im.save(png, "PNG")


def render_views(cfg, views=None, prefix="viewer"):
    html = cfg.get("_viewer")
    if not html or not os.path.exists(html):
        raise SystemExit("无看图台：先运行 viewer")
    out_dir = Path(cfg["_work"]) / "输出"
    out_dir.mkdir(parents=True, exist_ok=True)
    views = views or cfg.get("views", ["panorama", "bridge"])
    res = []
    for v in views:
        p = out_dir / ("%s-%s.png" % (prefix, v))
        render_html(html, v, str(p))
        res.append(str(p))
        log("OK %s" % p)
    return res
