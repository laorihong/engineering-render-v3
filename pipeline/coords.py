# -*- coding: utf-8 -*-
"""逐桩坐标→经纬度（GK 反算）→几何 JSON 骨架。"""
import csv
import json
from pathlib import Path

from .common import gk_inverse, log, save_json


def parse_table(path):
    """支持 csv(json) 三列：station_m,X,Y；或 json [{station_m,X,Y}]。"""
    p = Path(path)
    rows = []
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        data = data if isinstance(data, list) else data.get("points", [])
        for r in data:
            rows.append([float(r["station_m"]), float(r["X"]), float(r["Y"])])
    else:
        with open(p, encoding="utf-8-sig", newline="") as f:
            for r in csv.reader(f):
                if len(r) >= 3 and r[0].lower() != "station_m":
                    try:
                        rows.append([float(r[0]), float(r[1]), float(r[2])])
                    except ValueError:
                        pass
    rows.sort()
    return rows


def table_to_geometry(table_path, cm_deg, out_json, extra=None):
    rows = parse_table(table_path)
    pts = []
    for sm, x, y in rows:
        lat, lon = gk_inverse(x, y, cm_deg)
        pts.append({"station_m": round(sm, 3), "X": x, "Y": y,
                    "lat": round(lat, 7), "lon": round(lon, 7)})
    if not pts:
        raise SystemExit("坐标表无有效行")
    g = {"route": pts,
         "features": (extra or {}).get("features", []),
         "bridges": (extra or {}).get("bridges", [])}
    save_json(out_json, g)
    log("几何骨架已生成 %s（%d 点）" % (out_json, len(pts)))
    return g
