# -*- coding: utf-8 -*-
"""瓦片底图：Bing / ESRI / 天地图下载拼接（参数化、可断点续传）。"""
import json
import math
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from .common import ensure_dirs, log, save_json
from .geo import load_geometry


def merc(lat, lon, z):
    n = 2 ** z
    return ((lon + 180.0) / 360.0 * n,
            (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)


def quadkey(tx, ty, z):
    q = ""
    for i in range(z, 0, -1):
        m = 1 << (i - 1)
        d = (1 if tx & m else 0) + (2 if ty & m else 0)
        q += str(d)
    return q


def _url_bing(tx, ty, z):
    qk = quadkey(tx, ty, z)
    h = "t%d" % ((tx + ty) % 4)
    return "https://ecn.%s.tiles.virtualearth.net/tiles/a%s.jpeg?g=2031" % (h, qk)


def _url_esri(tx, ty, z):
    return ("https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/%d/%d/%d" % (z, ty, tx))


def _url_tianditu(tx, ty, z, key, layer="img_w"):
    return "https://t%d.tianditu.gov.cn/DataServer?T=%s&x=%d&y=%d&l=%d&tk=%s" % (
        (tx + ty) % 8, layer, tx, ty, z, key)


def _fetch(url, min_bytes, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if len(data) >= min_bytes:
                return data
        except Exception:
            pass
        time.sleep(1.0 * (i + 1))
    return None


def _tile_range(bbox, z):
    x0f, y0f = merc(bbox["lat_max"], bbox["lon_min"], z)
    x1f, y1f = merc(bbox["lat_min"], bbox["lon_max"], z)
    return (int(math.floor(x0f)), int(math.ceil(x1f)),
            int(math.floor(y0f)), int(math.ceil(y1f)),
            x0f, y0f, x1f, y1f)


def download_bbox(bbox, z, out_dir, tag, provider="bing", min_bytes=1800,
                  tianditu_key="", workers=8):
    """下载并拼接一张底图。返回 (png, meta)。"""
    out_dir = Path(out_dir)
    tmp = out_dir / ("tiles_%s_z%d" % (tag, z))
    tmp.mkdir(parents=True, exist_ok=True)
    tx0, tx1, ty0, ty1, x0f, y0f, x1f, y1f = _tile_range(bbox, z)
    total = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    log("瓦片 %s z%d: %d 块" % (tag, z, total))

    def fetch_tile(ty, tx):
        p = tmp / ("%d_%d.jpg" % (tx, ty))
        if p.exists() and p.stat().st_size > min_bytes:
            return
        if provider == "bing":
            url = _url_bing(tx, ty, z)
        elif provider == "esri":
            url = _url_esri(tx, ty, z)
        elif provider == "tianditu":
            url = _url_tianditu(tx, ty, z, tianditu_key)
        else:
            raise ValueError("未知 provider: %s" % provider)
        data = _fetch(url, min_bytes)
        if data:
            p.write_bytes(data)

    jobs = [(ty, tx) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda j: fetch_tile(*j), jobs))
    ok = sum(1 for j in jobs if (tmp / ("%d_%d.jpg" % (j[1], j[0]))).exists())
    log("下载完成 %d/%d" % (ok, total))
    W, H = (tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256
    big = Image.new("RGB", (W, H))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            p = tmp / ("%d_%d.jpg" % (tx, ty))
            if p.exists():
                try:
                    big.paste(Image.open(p).convert("RGB"),
                              ((tx - tx0) * 256, (ty - ty0) * 256))
                except Exception:
                    pass
    px0, py0 = int((x0f - tx0) * 256), int((y0f - ty0) * 256)
    px1, py1 = int(math.ceil((x1f - tx0) * 256)), int(math.ceil((y1f - ty0) * 256))
    crop = big.crop((px0, py0, px1, py1))
    png = out_dir / ("%s_z%d.png" % (tag, z))
    crop.save(png, "PNG")
    meta = {"z": z, "lat_min": bbox["lat_min"], "lat_max": bbox["lat_max"],
            "lon_min": bbox["lon_min"], "lon_max": bbox["lon_max"],
            "width_px": crop.size[0], "height_px": crop.size[1],
            "m_per_px": (bbox["lat_max"] - bbox["lat_min"]) * 111320.0 / crop.size[1],
            "provider": provider, "tiles_ok": ok, "tiles_total": total}
    save_json(str(png).replace(".png", ".json"), meta)
    log("底图已保存 %s %s" % (png, crop.size))
    return png, meta


def pad_bbox(bbox, lat_pad_m, lon_pad_m):
    dlat = lat_pad_m / 111320.0
    dlon = lon_pad_m / (111320.0 * math.cos(math.radians((bbox["lat_min"] + bbox["lat_max"]) / 2)))
    return {"lat_min": bbox["lat_min"] - dlat, "lat_max": bbox["lat_max"] + dlat,
            "lon_min": bbox["lon_min"] - dlon, "lon_max": bbox["lon_max"] + dlon}


def fetch_base(cfg, tag=None, bbox=None):
    """CLI：按 config.base 拉取全线底图。"""
    ensure_dirs(cfg)
    g = load_geometry(cfg)
    base_cfg = cfg["base"]
    ri = __import__("pipeline.geo", fromlist=["RouteIndex"]).RouteIndex(g["route"])
    bbox = bbox or ri.bbox()
    bbox = pad_bbox(bbox, base_cfg.get("lat_pad_m", 250), base_cfg.get("lon_pad_m", 200))
    png, meta = download_bbox(bbox, base_cfg["zoom"],
                              Path(cfg["_work"]) / "底图",
                              tag or "base", provider=base_cfg["provider"],
                              min_bytes=base_cfg.get("min_tile_bytes", 1800),
                              tianditu_key=cfg.get("keys", {}).get("tianditu", ""))
    # 回写配置默认文件名
    cfg["_base"] = str(png)
    cfg["_base_meta"] = str(png).replace(".png", ".json")
    return png
