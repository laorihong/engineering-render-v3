# -*- coding: utf-8 -*-
"""headless Chrome 静态渲染（2560×1440 归一化）。"""
import os
import subprocess
import time
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from .common import find_chrome, log

TARGET = (2560, 1440)


def _serve(dirpath, name):
    """把看图台目录用本地 HTTP 暴露：部分环境下 file:// 的 WebGL 会整片黑屏，HTTP 正常。"""
    handler = lambda *a, **k: SimpleHTTPRequestHandler(*a, directory=str(dirpath), **k)  # noqa: E731
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/%s" % (srv.server_address[1], urllib.parse.quote(name))


def render_html(html, view, out_png, chrome=None, window=(2596, 1591)):
    chrome = chrome or find_chrome()
    if not chrome:
        raise SystemExit("未找到 Chrome/Edge（可设置环境变量 CHROME_PATH）")
    profile = Path(os.environ.get("TEMP", "/tmp")) / ("v3chrome_" + str(int(time.time())))
    profile.mkdir(parents=True, exist_ok=True)
    srv = None
    html_path = Path(html).resolve()
    if str(html).startswith("http://") or str(html).startswith("https://"):
        url = str(html) + ("&" if "?" in str(html) else "?") + "v=" + view
    else:
        srv, base = _serve(html_path.parent, html_path.name)
        url = base + "?v=" + view
    def shoot(win):
        cmd = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
               "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
               "--hide-scrollbars", "--user-data-dir=%s" % profile,
               "--window-size=%d,%d" % win, "--virtual-time-budget=15000",
               "--screenshot=%s" % out_png, url]
        log("渲染 %s (%s)" % (os.path.basename(out_png), view))
        subprocess.run(cmd, check=False, capture_output=True)
        wait = 0
        while not os.path.exists(out_png) and wait < 60:
            time.sleep(0.5)
            wait += 1
    try:
        shoot(window)
        if os.path.exists(out_png) and window[0] > 1600:
            m1, s1 = _stats(out_png)
            if s1 < 8:   # 近乎纯色 = 空屏（部分机器大画布 WebGL 失效）
                alt = str(out_png) + ".alt.png"
                os.replace(out_png, alt)
                log("画面疑似空屏(σ=%.1f)，降分辨率重试" % s1)
                cmd = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
                       "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                       "--hide-scrollbars", "--user-data-dir=%s" % profile,
                       "--window-size=1296,795", "--virtual-time-budget=15000",
                       "--screenshot=%s" % out_png, url]
                subprocess.run(cmd, check=False, capture_output=True)
                wait = 0
                while not os.path.exists(out_png) and wait < 60:
                    time.sleep(0.5)
                    wait += 1
                m2, s2 = _stats(out_png) if os.path.exists(out_png) else (0.0, 0.0)
                if s2 >= s1:
                    if os.path.exists(alt):
                        os.remove(alt)
                    log("采用低分辨率重试结果(σ=%.1f)" % s2)
                else:
                    os.replace(alt, out_png)
                    log("保留原渲染(σ=%.1f)" % s1)
    finally:
        if srv is not None:
            srv.shutdown()
            srv.server_close()
    if not os.path.exists(out_png):
        raise RuntimeError("Chrome 未生成截图: %s" % view)
    _normalize(out_png)
    return out_png


def _stats(png):
    try:
        im = Image.open(png).convert("L")
        px = list(im.resize((48, 27)).getdata())
        mean = sum(px) / len(px)
        var = sum((v - mean) ** 2 for v in px) / len(px)
        return mean, var ** 0.5
    except Exception:
        return 0.0, 0.0


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
    if not html or not os.path.exists(str(html)):
        # 跨进程调用（如 HTTP 服务的分步作业）时运行时键会丢失，回退找默认看图台
        cand = Path(cfg["_work"]) / "输出" / "看图台.html"
        if cfg.get("viewer_file"):
            c2 = Path(cfg["viewer_file"])
            c2 = c2 if c2.is_absolute() else Path(cfg["_work"]) / c2
            if os.path.exists(str(c2)):
                cand = c2
        if os.path.exists(str(cand)):
            html = str(cand)
        else:
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
