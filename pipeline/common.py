# -*- coding: utf-8 -*-
"""通用：路径、配置、日志、图像与字体工具。所有路径都相对化。"""
import base64
import io
import json
import math
import os
import shutil
import sys
from pathlib import Path

import PIL.Image

REPO = Path(__file__).resolve().parents[1]


def log(msg):
    print(msg, flush=True)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def load_config(cfg_path):
    """载入配置，并把相对路径锚定到 config 所在目录。"""
    cfg_path = Path(cfg_path).resolve()
    cfg = load_json(cfg_path)
    base = cfg_path.parent
    cfg["_root"] = str(base)
    work = cfg["project"].get("work_dir", "work")
    wdir = Path(work)
    if not wdir.is_absolute():
        wdir = base / wdir
    cfg["_work"] = str(wdir.resolve())
    for key in ("geometry_file", "base_file", "base_meta", "map2d_file"):
        if cfg.get(key):
            p = Path(cfg[key])
            cfg["_" + key.replace("_file", "").replace("_meta", "_meta")] = _res(base, wdir, p)
    return cfg


def _res(base, work, p):
    p = Path(p)
    if p.is_absolute():
        return str(p)
    return str((work / p if p.parts and p.parts[0] in ("模型", "底图", "输出", "提取")
                else base / p).resolve())


def ensure_dirs(cfg):
    work = Path(cfg["_work"])
    for sub in ("提取", "底图", "模型", "输出"):
        (work / sub).mkdir(parents=True, exist_ok=True)
    return work


def find_font(bold=False):
    names = [r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
             "/System/Library/Fonts/PingFang.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    for n in names:
        if os.path.exists(n):
            return n
    return None


def find_chrome():
    candidates = [
        os.environ.get("CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return shutil.which("chrome") or shutil.which("chromium") or shutil.which("msedge")


def image_to_data_uri(png, max_w=2300, quality=83):
    im = PIL.Image.open(png).convert("RGB")
    if im.size[0] > max_w:
        k = max_w / im.size[0]
        im = im.resize((int(im.size[0] * k), int(im.size[1] * k)), PIL.Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def gk_inverse(x, y, cm_deg, zone_wide=3):
    """CGCS2000/西安80 高斯平面→经纬度（近似；正式使用前用已知点校验）。"""
    a = 6378137.0
    f = 1 / 298.257222101
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    cm = math.radians(cm_deg)
    fe = 500000.0
    x = float(x)
    y = float(y) - fe
    m = x
    a0 = 1 + 3 / 4 * e2 + 45 / 64 * e2 ** 2 + 175 / 256 * e2 ** 3 + 11025 / 16384 * e2 ** 4
    b1 = 3 / 4 * e2 + 15 / 16 * e2 ** 2 + 525 / 512 * e2 ** 3 + 2205 / 2048 * e2 ** 4
    b2 = 15 / 64 * e2 ** 2 + 105 / 256 * e2 ** 3 + 2205 / 4096 * e2 ** 4
    b3 = 35 / 512 * e2 ** 3 + 315 / 2048 * e2 ** 4
    b4 = 315 / 16384 * e2 ** 4
    bf = m / (a * (1 - e2) * a0)
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    tf = bf
    for _ in range(6):
        tf = bf + (-b1 * math.sin(2 * tf) / 2 + b2 * math.sin(4 * tf) / 4
                   - b3 * math.sin(6 * tf) / 6 + b4 * math.sin(8 * tf) / 8) / a0
    nf = a / math.sqrt(1 - e2 * math.sin(tf) ** 2)
    vf = nf / math.sqrt(1 + ep2 * math.cos(tf) ** 2)
    mf = (1 - e2) / (1 - e2 * math.sin(tf) ** 2) * nf
    tf_ = math.tan(tf)
    lat = tf - vf * tf_ / (2 * mf) * (y / (nf * math.cos(tf))) ** 2
    lat += vf * tf_ / (24 * mf) * (5 + 3 * tf_ ** 2 + ep2 * math.cos(tf) ** 2
                                   - 9 * ep2 * tf_ ** 2 * math.cos(tf) ** 2) * (y / (nf * math.cos(tf))) ** 4
    lon = y / (nf * math.cos(tf))
    lon -= (1 + 2 * tf_ ** 2 + ep2 * math.cos(tf) ** 2) / 6 * (y / (nf * math.cos(tf))) ** 3
    lon += (5 + 28 * tf_ ** 2 + 24 * tf_ ** 4) / 120 * (y / (nf * math.cos(tf))) ** 5
    return math.degrees(lat), math.degrees(cm + lon)


def fmt_st(st):
    st = round(float(st))
    return "K%d+%03d" % (st // 1000, st % 1000)
