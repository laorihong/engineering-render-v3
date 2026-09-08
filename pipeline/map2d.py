# -*- coding: utf-8 -*-
"""2D 走向图（v3-lite 引线标注；完整版由 AI 按项目细化）。"""
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .common import ensure_dirs, find_font, log, fmt_st, load_json
from .geo import load_geometry


def _px(meta, lat, lon):
    z = meta["z"]

    def merc(la, lo):
        n = 2 ** z
        return ((lo + 180.0) / 360.0 * n,
                (1.0 - math.asinh(math.tan(math.radians(la))) / math.pi) / 2.0 * n)

    x0f, y0f = merc(meta["lat_max"], meta["lon_min"])
    x1f, y1f = merc(meta["lat_min"], meta["lon_max"])
    X, Y = merc(lat, lon)
    W, H = meta["width_px"], meta["height_px"]
    return (X - x0f) / (x1f - x0f) * W, (Y - y0f) / (y1f - y0f) * H


def draw_map2d(cfg):
    ensure_dirs(cfg)
    g = load_geometry(cfg)
    m2 = cfg.get("map2d", {})
    base = cfg.get("_base")
    if not base or not os.path.exists(base):
        base = _pick_base(cfg)
    if not base:
        raise SystemExit("无底图：先运行 fetch-base 或提供 base_file")
    meta = load_json(str(base).replace(".png", ".json"))
    im = Image.open(base).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    fnt = find_font()
    f_bold = find_font(bold=True)
    fb = ImageFont.truetype(f_bold or fnt, max(36, W // 60))
    fs = ImageFont.truetype(fnt, max(24, W // 90))
    fl = ImageFont.truetype(fnt, max(20, W // 130))
    fn = ImageFont.truetype(fnt, max(16, W // 170))
    route = g["route"]
    pp = [(p["lat"], p["lon"]) for p in route]

    def line_pts(s0, s1):
        pts = []
        for p in route:
            if s0 - 1e-6 <= p["station_m"] <= s1 + 1e-6:
                pts.append(_px(meta, p["lat"], p["lon"]))
        return pts

    for sp in m2.get("spans", []):
        col = sp.get("color", "#8b9098")
        w = max(3, int(W / 900 * sp.get("width_px", 7) / 7))
        pts = line_pts(sp["station0_m"], sp["station1_m"])
        if pts:
            d.line(pts, fill=col, width=w)

    # 特征引线（上下交替）
    for i, lb in enumerate(m2.get("labels", [])):
        st = lb["station_m"]
        p = min(route, key=lambda r: abs(r["station_m"] - st))
        x, y = _px(meta, p["lat"], p["lon"])
        side = "up" if i % 2 == 0 else "down"
        txt = "%s  %s" % (lb["text"], fmt_st(st))
        fnt_k = fl
        bb = d.textbbox((0, 0), txt, font=fnt_k)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        lift = H * 0.05
        cy = y + (lift if side == "down" else -lift)
        x0 = max(4, min(W - tw - 30, x - tw / 2 - 10))
        bg = lb.get("color", "#163a5e")
        d.rounded_rectangle([x0, cy - th / 2 - 8, x0 + tw + 20, cy + th / 2 + 8],
                            radius=8, fill=bg)
        d.text((x0 + 10, cy - th / 2), txt, font=fnt_k, fill="#ffffff")
        d.line([(x, y), (x, cy + (th / 2 + 12 if side == "down" else -(th / 2 + 12)))],
               fill="#e8c37a", width=max(2, W // 2000))
        r = max(4, W // 1500)
        d.ellipse([x - r, y - r, x + r, y + r], fill="#ffd27d", outline="#0b1724", width=2)

    every = m2.get("minor_every_m", 500)
    for k in range(int(route[0]["station_m"] // every + 1) * every,
                   int(route[-1]["station_m"]) + 1, every):
        if any(abs(k - lb["station_m"]) < every / 2 for lb in m2.get("labels", [])):
            continue
        p = min(route, key=lambda r: abs(r["station_m"] - k))
        x, y = _px(meta, p["lat"], p["lon"])
        r = max(3, W // 2000)
        d.ellipse([x - r, y - r, x + r, y + r], fill="#ffffff", outline="#0b1724", width=2)
        d.text((x + 8, y + 6), fmt_st(k).replace("K0", "").replace("K", ""), font=fn, fill="#ffffff")

    # 标题/图例/比例尺
    title = m2.get("title", cfg["project"].get("title_2d", "2D 线路走向图"))
    bb = d.textbbox((0, 0), title, font=fb)
    tw = bb[2] - bb[0]
    tx = W / 2
    d.rounded_rectangle([tx - tw / 2 - 20, H * 0.015, tx + tw / 2 + 20, H * 0.015 + fb.size + 24],
                        radius=10, fill=(14, 30, 46, 215))
    d.text((tx - tw / 2, H * 0.015 + 8), title, font=fb, fill="#ffffff")
    lgx, lgy = W * 0.02, H * 0.08
    for i, sp in enumerate(m2.get("spans", [])[:7]):
        yy = lgy + i * (H * 0.026)
        d.line([(lgx, yy), (lgx + W * 0.02, yy)], fill=sp["color"], width=8)
        d.text((lgx + W * 0.024, yy - 10), sp.get("name", sp["color"]), font=fl, fill="#ffffff")
    bar_m = m2.get("scale_m", 500)
    bar_px = bar_m / meta["m_per_px"]
    bx, by = W * 0.04, H * 0.95
    d.rectangle([bx, by, bx + bar_px, by + 8], outline="#ffffff", width=3)
    d.rectangle([bx, by, bx + bar_px / 2, by + 8], fill="#ffffff")
    d.text((bx, by + 12), "0  %dm" % bar_m, font=fn, fill="#ffffff")
    note = m2.get("note", "底图/坐标/结构示意说明见成果说明文档")
    d.rectangle([0, H * 0.972, W, H], fill=(14, 30, 46, 215))
    d.text((W * 0.02, H * 0.979), note, font=fn, fill="#d8e0e6")
    out = Path(cfg.get("_map2d") or (Path(cfg["_work"]) / "输出" / "2D线路走向图.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "PNG")
    cfg["_map2d"] = str(out)
    log("2D 已保存 %s %s" % (out, im.size))
    return out


def _pick_base(cfg):
    p = cfg.get("_base")
    if p and os.path.exists(p):
        return p
    work = Path(cfg["_work"]) / "底图"
    cands = sorted(work.glob("*_z*.png"))
    return str(cands[0]) if cands else None
