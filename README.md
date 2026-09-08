# engineering-render-v3 —— 工程效果图“图纸→六件套”可迁移流水线

把已成熟的 V3 方法做成**参数化 CLI + 一键环境体检**的仓库骨架：没有硬编码本机盘符，
拷到另一台装有 Python 与 Codex/同类智能体的机器即可复用；也可直接推到 GitHub。

## 一、仓库结构

```text
engineering-render-v3/
├─ preflight.py            # 一键环境体检（依赖/Chrome/字体/模板/可选网络）
├─ v3.py                   # CLI：doctor/demo/extract/geo/fetch-base/map2d/viewer/render/overview/kml/docx
├─ config.example.json     # 配置样例（含 schema 注释）
├─ requirements.txt
├─ templates/
│  └─ three.min.js         # 看图台 3D 引擎（单文件 HTML 内嵌）
├─ pipeline/
│  ├─ common.py            # 配置装载/路径解析/日志/图像与字体工具/GK反算
│  ├─ geo.py               # 几何加载、桩号→经纬度插值
│  ├─ pdf_extract.py       # PDF 文字层关键词扫描
│  ├─ coords.py            # 逐桩坐标表→经纬度几何 JSON
│  ├─ tiles.py             # Bing/ESRI/天地图 瓦片下载与拼接（可断点续传）
│  ├─ map2d.py             # 2D 走向图（v3-lite 引线）
│  ├─ viewer.py            # 单文件 3D 看图台（2D/3D 页签）
│  ├─ render.py            # headless Chrome 静态渲染 2560×1440
│  ├─ overview.py          # 成果总览（图片 data-URI 内嵌）
│  ├─ kml.py               # 奥维/Google Earth KML
│  ├─ docs.py              # md→docx（WPS 可开）
│  └─ demo.py              # 无网络端到端演示工程
└─ work/                   # 运行时生成（已 gitignore）
```

## 二、30 秒上手

```bash
# 1) 环境体检
python preflight.py

# 2) 无网络自检（自动生成 3km 演示工程并跑通 2D→3D→渲染→总览）
python v3.py demo --dir work/demo
open work/demo/输出/成果总览.html

# 3) 真项目：先按 config.example.json 建配置
python v3.py init-config --out work/myproj/config.json
#    修改 work_dir、起终点、底图 provider/zoom、map2d 分段与标签、结构 JSON 路径
python v3.py -c work/myproj/config.json extract   图纸.pdf --out 提取     # 读图（AI 判断后填 geometry）
python v3.py -c work/myproj/config.json fetch-base                     # 拉底图
python v3.py -c work/myproj/config.json map2d viewer render overview kml
```

> `extract`/`geo` 只做“机器能自动的部分”；图纸理解、结构桩号表整理、
> 坐标锚点校验、效果图观感仍建议由 Codex（智能体）结合 SKILL 完成——
> 这正是 V3“Skill 包 + 脚本 + 智能体”三件套里智能体承担的环节。

## 三、换机/上 GitHub 前要做的三件事

1. **参数外置**：本仓库全部相对路径；项目目录、天地图 Key 走 `config.json`/环境变量（建议 `.env`），不要写盘符。
2. **环境补齐**：目标机装 Python 3.10+、`pip install -r requirements.txt`、Chrome/Edge；设 `CHROME_PATH` 可显式指定。
3. **数据与许可**：源 PDF 不入库；底图/成果仅供内部示意；天地图 Key 用环境变量注入（参考 `.env.example`）。

## 四、几何 JSON 结构（pipeline 数据契约）

`geometry_file` 指向 `模型/project_geometry.json`，AI 完成图纸解读后填写：

```json
{
  "route":   [{"station_m": 0.0, "lat": 24.3000, "lon": 113.1000}],
  "features":[{"name": "起点平交", "station_m": 0.0, "geo": {"lat": 0, "lon": 0}}],
  "bridges": [{"name": "某大桥", "center": 1500.0, "len_m": 148.0,
               "width_m": 24.5, "spans": "7×20m"}]
}
```

说明：`v3.py geo --table 坐标.csv --cm 113.1667` 可把逐桩坐标表自动转成该结构（AI 再补 features/bridges）。

## 五、扩展点（留给项目级微调）

- 复杂桥型（斜拉/拱/桁架）与旧桥拆除：在 `viewer.py` 的 JS 建模段按项目加“桥型函数”，延续各项目沉淀的参数化写法；
- 复杂 2D 标注（分幅、挡墙、涵洞点位）：项目级在 `map2d.py` 基础上扩展，或让 AI 生成项目专用绘制脚本；
- 高保真渲染：可外挂 Blender（`blender -b -P xxx.py`）替代 headless Chrome；
- 分段长线路：把 `route` 按分段切为多份 geometry，各段各跑一遍 viewer/render。
