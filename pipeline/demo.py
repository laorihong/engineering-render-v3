# -*- coding: utf-8 -*-
"""演示工程：不依赖网络/图纸，端到端跑通 数据→2D→3D→渲染。"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from .common import ensure_dirs, find_chrome, log, save_json


def make_demo(work=None, with_render=True):
    from .map2d import draw_map2d
    from .overview import build_overview
    from .viewer import build_viewer

    root = Path(__file__).resolve().parents[1]
    work = Path(work or (root / "work" / "demo")).resolve()
    (work / "模型").mkdir(parents=True, exist_ok=True)
    (work / "底图").mkdir(parents=True, exist_ok=True)
    (work / "输出").mkdir(parents=True, exist_ok=True)
    # ---- 1) 几何：3000m 演示走廊（轻微曲线） ----
    lat0, lon0 = 24.3000, 113.1000
    pts = []
    for sm in range(0, 3001, 10):
        heading = math.radians(270 + 22 * math.sin(sm / 750))
        if not pts:
            lat, lon = lat0, lon0
        else:
            prev = pts[-1]
            lat = prev["lat"] + math.cos(heading) * 10 / 111320.0
            lon = prev["lon"] + math.sin(heading) * 10 / (111320.0 * math.cos(math.radians(lat)))
        pts.append({"station_m": float(sm), "lat": round(lat, 7), "lon": round(lon, 7)})
    geo = {"route": pts,
           "features": [
               {"name": "演示起点(平交)", "station_m": 0.0,
                "geo": {"lat": pts[0]["lat"], "lon": pts[0]["lon"]}},
               {"name": "示范大桥(拼宽)", "station_m": 1500.0, "geo": {}},
               {"name": "演示渡槽下穿", "station_m": 2100.0, "geo": {}},
               {"name": "演示终点(平交)", "station_m": 3000.0, "geo": {}},
           ],
           "bridges": [
               {"name": "示范大桥", "center": 1500.0, "len_m": 120.0,
                "width_m": 24.5, "spans": "6×20m"},
               {"name": "示范小桥", "center": 2550.0, "len_m": 30.0,
                "width_m": 24.5, "spans": "1×20m"},
           ]}
    for f in geo["features"]:
        if not f["geo"]:
            p = _interp(pts, f["station_m"])
            f["geo"] = {"lat": p["lat"], "lon": p["lon"]}
    (work / "模型" / "project_geometry.json").write_text(
        json.dumps(geo, ensure_ascii=False, indent=1), encoding="utf-8")
    # ---- 2) 合成底图（无网络演示用） ----
    las = [p["lat"] for p in pts]
    lons = [p["lon"] for p in pts]
    bbox = {"lat_min": min(las) - 0.0011, "lat_max": max(las) + 0.0011,
            "lon_min": min(lons) - 0.0012, "lon_max": max(lons) + 0.0012}
    W, H = 1800, 360
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        for x in range(W):
            base = (206 + int(18 * math.sin(x / 60)), 222 - int(16 * math.sin(y / 40)),
                    196 + int(12 * math.cos(x / 90)))
            if (x + y) % 9 == 0:
                base = tuple(max(0, c - 16) for c in base)
            px[x, y] = base
    # 河流（北南向，在示范大桥处穿过）
    d = ImageDraw.Draw(img)
    ri = _interp(pts, 1500)

    def xof(lon):
        return (lon - bbox["lon_min"]) / (bbox["lon_max"] - bbox["lon_min"]) * W

    def yof(lat):
        return (bbox["lat_max"] - lat) / (bbox["lat_max"] - bbox["lat_min"]) * H

    for y in range(H):
        lat = bbox["lat_max"] - y / H * (bbox["lat_max"] - bbox["lat_min"])
        wob = 0.00035 * math.sin(y / 55)
        lc = xof(ri["lon"] + wob)
        for x in range(int(lc - 18), int(lc + 18)):
            if 0 <= x < W:
                px[x, y] = (58, 96, 118)
    # 村庄/城镇色块
    for cx0, cy0, cw in [(80, 60, 60), (1500, 250, 80), (1650, 90, 55)]:
        d.rectangle([cx0, cy0, cx0 + cw, cy0 + 40], fill=(205, 190, 172))
    meta = {"z": 16, "lat_min": bbox["lat_min"], "lat_max": bbox["lat_max"],
            "lon_min": bbox["lon_min"], "lon_max": bbox["lon_max"],
            "width_px": W, "height_px": H,
            "m_per_px": (bbox["lat_max"] - bbox["lat_min"]) * 111320.0 / H,
            "provider": "demo_synthetic"}
    img.save(work / "底图" / "base_demo.png", "PNG")
    save_json(work / "底图" / "base_demo.json", meta)
    # ---- 3) 配置（相对 config 自身） ----
    cfg = {
        "project": {"name": "V3演示工程（合成底图）", "work_dir": ".",
                    "title_2d": "V3 演示 · 2D 线路走向图",
                    "title_viewer": "V3 演示 · 3D 看图台"},
        "coords": {"cm_deg": 113.0, "station_min_m": 0, "station_max_m": 3000},
        "geometry_file": "模型/project_geometry.json",
        "base_file": "底图/base_demo.png",
        "base_meta": "底图/base_demo.json",
        "map2d_file": "输出/2D线路走向图.png",
        "map2d": {
            "title": "V3 演示工程 · 2D 线路走向图",
            "spans": [{"name": "路线", "station0_m": 0, "station1_m": 3000,
                       "color": "#8b9098", "width_px": 7}],
            "labels": [
                {"text": "演示起点", "station_m": 0, "color": "#3fae5a"},
                {"text": "示范大桥", "station_m": 1500, "color": "#e0483a"},
                {"text": "演示终点", "station_m": 3000, "color": "#3fae5a"}],
            "minor_every_m": 500,
            "note": "V3 演示数据（合成底图，无真实坐标），用于流水线自检。"},
        "viewer": {"2d_embed": True, "title": "V3 演示 · 3D 看图台",
                   "note": "合成底图演示 · 大桥/小桥/渡槽标识示意"},
        "views": ["panorama", "bridge"],
        "images_for_overview": ["2D线路走向图.png", "viewer-panorama.png", "viewer-bridge.png"],
        "viewer_files": ["看图台.html"],
        "keys": {"tianditu": ""},
    }
    cfg_path = work / "config.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    # ---- 4) 执行 ----
    from .common import load_config
    cfg2 = load_config(cfg_path)
    ensure_dirs(cfg2)
    cfg2["_base"] = str(work / "底图" / "base_demo.png")
    cfg2["_base_meta"] = str(work / "底图" / "base_demo.json")
    draw_map2d(cfg2)
    build_viewer(cfg2, out_html=work / "输出" / "看图台.html")
    if with_render and find_chrome():
        from .render import render_views
        render_views(cfg2, views=["panorama", "bridge"], prefix="viewer")
    build_overview(cfg2, images=cfg["images_for_overview"], links=cfg["viewer_files"])
    log("演示工程完成：%s（config.json）" % cfg_path)
    return cfg_path


def _interp(route, sm):
    sts = [p["station_m"] for p in route]
    for i in range(len(sts) - 1):
        if sts[i] <= sm <= sts[i + 1]:
            f = (sm - sts[i]) / max(1e-9, sts[i + 1] - sts[i])
            return {"lat": route[i]["lat"] + (route[i + 1]["lat"] - route[i]["lat"]) * f,
                    "lon": route[i]["lon"] + (route[i + 1]["lon"] - route[i]["lon"]) * f}
    return route[0] if sm < sts[0] else route[-1]
