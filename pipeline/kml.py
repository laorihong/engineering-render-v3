# -*- coding: utf-8 -*-
"""KML 输出（奥维/Google Earth）。"""
from pathlib import Path

from .common import ensure_dirs, fmt_st, log
from .geo import load_geometry


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def gen_kml(cfg, out_name="路线与结构物.kml"):
    ensure_dirs(cfg)
    g = load_geometry(cfg)
    route = g["route"]

    def line(points):
        return "\n".join("%.7f,%.7f,0" % (p["lon"], p["lat"]) for p in points)

    k = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
         "<name>%s</name>" % _esc(cfg["project"]["name"]),
         "<Style id='main'><LineStyle><color>ff2bb4ff</color><width>6</width></LineStyle></Style>",
         "<Style id='bridge'><LineStyle><color>ff144fe0</color><width>9</width></LineStyle></Style>",
         "<Style id='key'><IconStyle><color>ff40b2ff</color><scale>1.1</scale></IconStyle></Style>",
         "<Folder><name>主线</name><Placemark><name>%s</name><styleUrl>#main</styleUrl>"
         "<LineString><tessellate>1</tessellate><coordinates>%s</coordinates></LineString></Placemark></Folder>"
         % (_esc(cfg["project"]["name"]), line(route))]
    if g.get("bridges"):
        k.append("<Folder><name>桥梁</name>")
        for b in g["bridges"]:
            pts = [p for p in route if abs(p["station_m"] - b["center"]) <= b["len_m"] / 2]
            if len(pts) >= 2:
                k.append("<Placemark><name>%s %s</name><styleUrl>#bridge</styleUrl>"
                         "<LineString><coordinates>%s</coordinates></LineString></Placemark>"
                         % (_esc(b["name"]), fmt_st(b["center"]), line(pts)))
        k.append("</Folder>")
    if g.get("features"):
        k.append("<Folder><name>特征</name>")
        for f in g["features"]:
            gd = f["geo"]
            k.append("<Placemark><name>%s %s</name><styleUrl>#key</styleUrl>"
                     "<Point><coordinates>%.7f,%.7f,0</coordinates></Point></Placemark>"
                     % (_esc(f["name"]), fmt_st(f["station_m"]), gd["lon"], gd["lat"]))
        k.append("</Folder>")
    k.append("</Document></kml>")
    out = Path(cfg["_work"]) / "输出" / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(k), encoding="utf-8")
    log("KML 已保存 %s" % out)
    return out
