# -*- coding: utf-8 -*-
"""几何加载与桩号→经纬度插值。"""
import bisect
import math

from .common import load_json, log


def load_geometry(cfg):
    p = cfg["_geometry"]
    g = load_json(p)
    route = g["route"]
    route = sorted(route, key=lambda r: r["station_m"])
    return g


class RouteIndex:
    def __init__(self, route):
        self.route = route
        self.st = [float(r["station_m"]) for r in route]

    def interp(self, sm):
        st = self.st
        if sm <= st[0]:
            return self.route[0]
        if sm >= st[-1]:
            return self.route[-1]
        j = bisect.bisect_left(st, sm)
        a, b = self.route[j - 1], self.route[j]
        f = (sm - st[j - 1]) / max(1e-9, st[j] - st[j - 1])
        return {"station_m": sm, "lat": a["lat"] + (b["lat"] - a["lat"]) * f,
                "lon": a["lon"] + (b["lon"] - a["lon"]) * f}

    def bbox(self, pad_deg=0.0):
        las = [r["lat"] for r in self.route]
        lons = [r["lon"] for r in self.route]
        return {"lat_min": min(las) - pad_deg, "lat_max": max(las) + pad_deg,
                "lon_min": min(lons) - pad_deg, "lon_max": max(lons) + pad_deg}


def station_to_geo(route, sm):
    return RouteIndex(route).interp(sm)


def geo_lin(la0, lo0, la1, lo1, t):
    return la0 + (la1 - la0) * t, lo0 + (lo1 - lo0) * t


def en_of(lat, lon, lat0, lon0):
    mlon = 111320.0 * math.cos(math.radians(lat0))
    return (lon - lon0) * mlon, (lat - lat0) * 111320.0


def log_geometry_summary(g):
    log("几何：路线点 %d，范围 %.3f~%.3f m，特征 %d，桥 %d"
        % (len(g.get("route", [])), g["route"][0]["station_m"], g["route"][-1]["station_m"],
           len(g.get("features", [])), len(g.get("bridges", []))))
