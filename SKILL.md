---
name: engineering-render
description: "Produce complete engineering visualization packages (工程效果图) from design/construction documents: extract structure parameters from PDF/CAD, convert station coordinate tables (逐桩坐标/CGCS2000 Gauss-Krüger) to WGS84 and route bearing, download and stitch real satellite or road-map base imagery (ESRI/高德/天地图/Bing), build georeferenced parametric 3D bridge/road/campus models (Three.js or Blender), render 2D route alignment maps and 3D panorama/full-line/bridge close-up views with station (桩号) labels, and deliver HD PNGs plus a single-file interactive HTML viewer. Use when the user asks for 工程效果图/全景效果图/3D效果图/线路走向图/线位示意图/看图台, or provides 施工图/设计图纸/初设图纸/逐桩坐标 and wants visualization of a bridge, road, interchange, or building project."
---

# Engineering Render（工程效果图制作）

用设计/施工资料产出"真实底图 + 工程主体 + 桩号里程"的效果图体系。本流程已在石洲大桥、北江大桥、武江大桥、西河新桥与十里亭大桥（2026-09）上验证，可复用于同类项目。无特殊要求时，一律按"十里亭版（V3.1）"默认基线交付。

## 典型交付物

1. 高清静态图（2560×1440 PNG）：两方案（推荐+比选）× 全景/全线/主桥近景/正立面/顶视 各5视角
2. 2D 路线走向图与线位示意图：真实底图 + 主线/桥梁分段着色 + 百米桩与关键桩号 + 图例/比例尺/指北针
3. 单文件交互看图台 HTML（方案A/B 各一个）：2D 平移缩放 + 3D 实时旋转/全景/近景，可独立打开
4. 工程资料文件夹：底图、坐标与参数 JSON、假设与数据来源说明

## 开工前必做

1. 完整阅读 `references/material-checklist.md`，按 A/B/C 三级核对用户资料。
2. A 级资料缺失时先向用户索取或明示假设；坐标与桩号不许静默猜测。
3. 建立项目文件夹结构：`原始资料 / 提取 / 底图 / 模型 / 输出`。

## 主流程（技术细节读 `references/workflow.md`）

1. 资料清点：PDF→Word 仅供人翻阅；机器解析直接读 PDF 文字层（PyMuPDF）。
2. 提取结构参数（桥型/跨径/桥宽/梁高/墩型/全长/起终点桩号）→ 参数表交用户确认。
3. 地理定位：逐桩坐标 → CGCS2000 高斯反算 → WGS84 经纬度与方位角；用路线长度校核。
4. 底图：卫星影像用 ESRI z18（约0.55m/px）或 z19 高清；高德路网 z16 用于 2D；天地图备选。
5. 参数化 3D 建模：复制模板 HTML 或写 Blender 脚本；坐标约定 X=东、Z=北、Y=高，模型内路线沿 +X。
6. 地理配准：模型组旋转 `rotation.y = 方位角 - 90°`，主桥中心落原点，顶视图校验。
7. 环境要素：从影像提取建筑/树木生成简化体块（可开关）；百米桩 + 特征桩号标注。
8. 渲染：headless Chrome 出静态图；有 FBX/OBJ/IFC 模型时用 Blender Cycles 高保真渲染。
9. 2D 图与看图台：底图叠路线线位，标注"新建/现状（拆除）"关系。
10. 像素校验（无黑边/无透明变黑/桥落河道）后打包交付。

## 新项目默认质量基线（V3.1 · 十里亭大桥 2026-09 验证版）

- 纵坡连续缓坡：主桥面标高按 12m 量级；引道提前 ≥400m 起坡（≤2%），下坡在桥内提前、桥台处与地面顺接，禁止标高跳变。
- 路面/桥面按"直坡段整体旋转梁"绘制（不用水平分块拼接），避免接缝裂缝与台阶。
- 斜拉索/吊索从塔顶/拱顶斜向锚到桥面之上：柱体绕 Z 旋转取 `rotation.z = atan2(水平差, 高差)`，锚点高差取正，禁止索穿桥底；双索面布置在桥面两侧。
- 全线中央分隔带（混凝土防撞墙+黄实线）不可省；车道分隔虚线、两侧连续护栏必备；桥梁段加双挑路灯（间隔约 46m）。
- 交付默认两方案（推荐/比选）各 5 视角静态图 + 2D 走向图 + 单文件看图台 + 成果总览 + docx/md 说明 + KML。

## 渲染与校核环境（本机实测，2026-09）

- headless Chrome 的 WebGL 在 `file://` 下黑屏：先 `python -m http.server` 起本地服务，用 `http://127.0.0.1:PORT/...` 渲染。
- SwiftShader 大画布会黑屏：用窗口 1296×795（≈1.03MP）渲染原图，再 Lanczos 放大到 2560×1440。
- 残留 headless Chrome 进程/堆积的 user-data-dir 会导致后续渲染黑屏：每次渲染前清理，批量时逐张独立执行。
- 坐标带核验：CGCS2000 3°带 CM=114 → EPSG:4547（CM=111 才是 4546，选错整体偏移约 3°）；用图纸"平曲线要素表"锚点反算并核对河网。
- 详细参数与踩坑见 `references/workflow.md`。

## 关键纪律（非显然，务必遵守）

- 高德路网瓦片是调色板 PNG：先转 RGBA 再叠浅底，否则透明变黑。
- 卫星图裁剪用"瓦片局部像素坐标"，勿用整图全局像素坐标（会全黑）。
- 批量处理前先用一个已知地物校验坐标/配准。
- 重建项目必须区分"新建桥梁"与"现状旧桥（本项目拆除）"，防止看图误解。
- 底图仅供内部示意；对外发布前核对瓦片服务许可。
- 本机环境（Blender 路径、脚本库、Chrome 参数）见 `references/workflow.md`，使用前验证路径存在。

## 参考文件导航

- `references/material-checklist.md`：每次新项目开工先读，用于向用户要资料。
- `references/workflow.md`：跑技术步骤时读，含脚本清单、瓦片 URL、渲染参数与踩坑表。
