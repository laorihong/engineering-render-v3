#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V3 工程效果图 CLI：参数化、相对路径、可换机运行。

常用：
  python v3.py doctor                     # 环境体检
  python v3.py demo --dir work/demo       # 无网络端到端演示
  python v3.py extract 图纸.pdf --out 提取
  python v3.py geo --table 坐标.csv --cm 113.1667 --out 模型/project_geometry.json
  python v3.py -c config.json fetch-base
  python v3.py -c config.json map2d
  python v3.py -c config.json viewer
  python v3.py -c config.json render
  python v3.py -c config.json overview
  python v3.py -c config.json kml
  python v3.py docx 说明.md 说明.docx
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline.common import load_config, log  # noqa: E402


def _cfg(args):
    cfg_path = args.config or (Path.cwd() / "config.json")
    if not os.path.exists(cfg_path):
        raise SystemExit("找不到配置：%s（可用 -c 指定，或先运行 demo/init-config）" % cfg_path)
    return load_config(cfg_path)


def main():
    ap = argparse.ArgumentParser(prog="v3", description="V3 工程效果图流水线 CLI")
    ap.add_argument("-c", "--config", default=None, help="config.json 路径")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor", help="一键环境体检")
    p.add_argument("--network", action="store_true")

    p = sub.add_parser("demo", help="无网络端到端演示")
    p.add_argument("--dir", default="work/demo")
    p.add_argument("--no-render", action="store_true")

    p = sub.add_parser("init-config", help="从 config.example.json 复制一份配置")
    p.add_argument("--out", default="config.json")

    p = sub.add_parser("extract", help="PDF 关键页文字抽取")
    p.add_argument("pdf")
    p.add_argument("--out", default="提取")

    p = sub.add_parser("geo", help="逐桩坐标表→几何 JSON")
    p.add_argument("--table", required=True, help="csv/json：station_m,X,Y")
    p.add_argument("--cm", type=float, required=True, help="中央子午线经度")
    p.add_argument("--out", default="模型/project_geometry.json")

    for name in ("fetch-base", "map2d", "viewer", "render", "overview", "kml"):
        sub.add_parser(name, help="流水线步骤：" + name)

    p = sub.add_parser("docx", help="md→docx（WPS）")
    p.add_argument("md")
    p.add_argument("out_docx")

    args = ap.parse_args()
    if args.cmd == "doctor":
        cmd = [sys.executable, str(ROOT / "preflight.py")]
        if args.network:
            cmd.append("--network")
        sys.exit(subprocess.call(cmd))
    if args.cmd == "demo":
        from pipeline.demo import make_demo
        make_demo(work=Path.cwd() / args.dir, with_render=not args.no_render)
        return
    if args.cmd == "init-config":
        src = ROOT / "config.example.json"
        dst = Path(args.out)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        log("已生成配置 %s（请按项目修改 work_dir/参数）" % dst)
        return
    if args.cmd == "extract":
        from pipeline.pdf_extract import extract_pages
        extract_pages(args.pdf, args.out)
        return
    if args.cmd == "geo":
        from pipeline.coords import table_to_geometry
        table_to_geometry(args.table, args.cm, args.out)
        return
    if args.cmd == "docx":
        from pipeline.docs import md_to_docx
        md_to_docx(args.md, args.out_docx)
        log("docx 已保存 %s" % args.out_docx)
        return
    cfg = _cfg(args)
    if args.cmd == "fetch-base":
        from pipeline.tiles import fetch_base
        fetch_base(cfg)
    elif args.cmd == "map2d":
        from pipeline.map2d import draw_map2d
        draw_map2d(cfg)
    elif args.cmd == "viewer":
        from pipeline.viewer import build_viewer
        build_viewer(cfg)
    elif args.cmd == "render":
        from pipeline.render import render_views
        render_views(cfg)
    elif args.cmd == "overview":
        from pipeline.overview import build_overview
        build_overview(cfg)
    elif args.cmd == "kml":
        from pipeline.kml import gen_kml
        gen_kml(cfg)


if __name__ == "__main__":
    main()
