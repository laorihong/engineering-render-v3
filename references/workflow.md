# 技术工作流（详细）

## 0. 本机环境事实（2026-09-02 记录，用前先验证存在）

| 资源 | 路径 |
|---|---|
| 工作区根目录 | `D:\工作助理\AI\codex\初步设计图纸生成效果图` |
| 可复用脚本库 | 工作区根目录下 `*.py`（见下表） |
| 3D 交互模板 | `D:\工作助理\AI\codex\初步设计图纸生成效果图\石洲大桥效果图\shizhou_geo.html` |
| 多标签看图台参考 | `D:\工作助理\AI\codex\初步设计图纸生成效果图\石洲大桥效果图\石洲大桥-工程看图.html` |
| Three.js 本地库 | `D:\工作助理\AI\codex\初步设计图纸生成效果图\石洲大桥效果图\three.min.js` |
| Blender 5.2 LTS | `D:\工作助理\AI\codex\Blender\blender-5.2.0-windows-x64\blender.exe` |

脚本清单（工作区根目录，复制/改造后用于新项目）：

| 脚本 | 作用 |
|---|---|
| `pdf2word.py` | PDF → 图片型 Word（仅人读） |
| `extract_design.py` | 按关键词提取结构参数 |
| `parse_route_coords.py` | 逐桩坐标 → 经纬度/方位角 |
| `fetch_satellite.py` | ESRI/卫星瓦片下载拼接 |
| `fetch_amap_base.py` / `fetch_hd.py` | 高德路网/高清影像瓦片 |
| `extract_buildings.py` | 影像提取建筑/树木轮廓 |
| `build_geo_final.py` | 底图 base64 内嵌 + 要素注入 |
| `patch_geo_mapbg.py` / `patch_geo_stations.py` | 地图背景模式 / 桩号标注 |
| `draw_map2d.py` / `draw_gaode_maps.py` / `draw_schematic.py` | 2D 走向图/高德底图/线位示意 |

## 1. 资料解析（PyMuPDF）

- 用文字层按关键词扫描：跨径组合、主桥/引桥、梁高、桥宽、墩型、通航、路线全长、控制点。
- PDF 结构损坏会刷 xref 警告：`fitz.TOOLS.mupdf_display_errors(False)` 抑制。
- 逐桩坐标表若文字层乱序：用正则按 `(桩号, X, Y)` 三元组提取后按桩号排序。
- 输出"结构参数表 + 坐标表"JSON，先交用户确认再建模。

## 2. 坐标换算（GK 反算）

- 输入：CGCS2000 高斯平面坐标（3°带，注意中央子午线）；输出：WGS84 经纬度（CGCS2000 与 WGS84 差异在制图尺度可忽略，但先用已知点校验）。
- 反算传参：X=N（北坐标）、Y=E（东坐标），E 在前是常见坑。
- 方位角：`atan2(ΔE, ΔN)`；模型旋转 `rotation.y = bearing - 90°`（°转弧度）。
- 校核：起终点平面距离 ≈ 图纸路线全长；方位角与交点表一致。
- 石洲大桥参照：主桥中心 ≈ 23.1166°N, 113.9568°E；桥轴向方位角 ≈ 162.8°。

## 3. 底图下载与拼接

瓦片源：

| 底图 | URL 模板 | 典型级别 | 备注 |
|---|---|---|---|
| ESRI 卫星 | `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` | z18≈0.55m/px，z19≈0.27m/px | 主用，免 Key |
| 高德路网 | `https://webrd0{1-4}.is.autonavi.com/appmaptile?style=8&x={x}&y={y}&z={z}` | z16 | 2D 走向图 |
| 天地图影像 | WMTS `img_w`，需 `tk` Key | z18 | 备选，地区清晰度不一 |
| Bing | 卫星备用 | z19 | 备用 |

纪律：
- 高德瓦片是调色板 PNG 带透明：先转 RGBA、叠浅底再拼接，否则透明变黑。
- 裁剪用"瓦片局部坐标（瓦片内坐标 + 瓦片序号×256）"计算像素框；用整图全局坐标会全黑。
- 保存底图 + 元数据 JSON（经纬度范围、m/px、z 级）；校验亮度网格与地物分布。

## 4. 参数化 3D 建模

约定：
- 世界坐标 X=东、Z=北、Y=高；模型组内路线沿 +X，K0+000 在 x=0。
- 桥面标高函数 `deckYAt(x)`：引道→引桥→主桥→引桥→引道。
- 变截面箱梁按段插值（如根部 8.75m → 跨中 3.5m）；墩（双肢薄壁/柱式）、承台、防撞栏、车道线、桥名牌参数化。

Three.js 要点：
- 深色材质需 `material.color.convertSRGBToLinear()`，否则沥青/水面发灰。
- 灯光 Hemisphere + Directional(阴影)、ACES 色调映射、渐变天空。
- 底图平面纹理 `texture.flipY = false` 保证北向；底图过大时 base64 内嵌进 HTML（file:// 下禁止加载本地图片）。
- 复制 `shizhou_geo.html` 模板 → 替换路线长度/桥跨/桥宽/梁高/方位角/底图参数，最快。

Blender（有真实模型或要高保真时）：
- `blender.exe -b 场景.blend -P 脚本.py` 无界面批处理。
- 导入 FBX/OBJ/glTF/USD/IFC 后配 Cycles 材质与光照渲染；CPU 可渲，有独显可 GPU。

## 5. 环境要素与桩号

- 建筑/树木：对卫星影像连通域分析（亮色→建筑，绿→树）→ 世界坐标简化体块，默认关闭、按钮开关。
- 桩号：百米桩 + 特征桩（桥起/主桥起/中心/终点），THREE.Sprite Canvas 文字贴图面向镜头。

## 6. 渲染静态图（headless Chrome）

- 本机参数：`chrome.exe --headless=new --no-sandbox --disable-gpu --use-angle=swiftshader --enable-unsafe-swiftshader --hide-scrollbars`
- 视口补偿：headless 视口比窗口小约 16×151px（要 2560×1440 用 `--window-size=2596,1591`）。
- 静态图加 `--virtual-time-budget=15000` 等纹理加载；**交互 HTML 禁止加该参数**（requestAnimationFrame 永不结束会挂起）。
- 输出后做像素校验：无黑边、无全黑、透明未变黑、构图正常。

## 7. 2D 走向图与看图台

- 逐桩坐标 → 经纬度 → Web Mercator 投影到底图；主线蓝/桥梁段橙/主桥段红、百米桩、关键桩号、交叉道路、指北针、比例尺、图例。
- 重建项目：图上标注"新建 XX"与"现状旧桥（本项目拆除）"；旧桥在新桥旁的底图现状不代表建成关系。
- 看图台单 HTML：标签切换 2D（拖拽/缩放/多角度 0/45/60/90/135/180/270°）+ 3D（`?preset=panorama|fullline|bridge`）。

## 8. 交付

- 交付：高清 PNG + 单文件交互 HTML + 底图 + 坐标/参数 JSON + 假设与来源说明。
- 同项目迭代：先确认"参数表 + 底图范围 + 视角清单"再批量渲染。

## 踩坑速查

| 现象 | 原因 | 解决 |
|---|---|---|
| Chrome headless 崩溃/黑屏 | GPU 进程被拦截 | 加 `--no-sandbox --use-angle=swiftshader --enable-unsafe-swiftshader` |
| 图片底部黑边 | 视口比窗口小 | 窗口补偿 16×151px 或裁剪 |
| 卫星底图全黑 | 用全局像素坐标裁剪 | 用瓦片局部坐标 |
| 高德底图变黑 | 调色板 PNG 透明 | 转 RGBA 叠浅底 |
| 深色材质发灰 | sRGB 当线性 | `convertSRGBToLinear()` |
| 内嵌浏览器黑屏 | file:// 禁本地图片 | 底图 base64 内嵌 |
| 拖拽无效 | Webview 接管手势 | 自动旋转 + 屏幕按钮 + 方向键 |
| PDF xref 报错 | 图纸 PDF 损坏 | 关闭 MuPDF 错误显示 |
| 逐桩表乱序 | 文字层顺序乱 | 正则三元组按桩号排序 |

## 底图许可提醒

卫星/路网底图来自公开瓦片服务，仅供内部汇报与示意；对外发布或商业用途前核对 ESRI/高德/天地图的使用条款，必要时换用授权影像。

## 2026-09 十里亭大桥优化记录（新项目默认基线，务必执行）

### 1. 纵坡与桥面建模（消除"拼接裂缝/台阶"）

- 禁止把桥面分成若干"水平平顶块"拼接：坡段会出现可见台阶与断缝；平段分块贴拼也会留缝。
- 正确做法：先定义连续纵坡函数 `deckY(x)`（分段线性且接点连续，禁止桥台处跳变），再把每个直坡段画成**整体旋转梁**：
  `rotBox(x0,x1,width,th,color,yoff)` → 梁长 `L=hypot(dx,dy)`、`rotation.z=atan2(dy,dx)`、中心 y 取 `(deckY(x0)+deckY(x1))/2+yoff`。
- 纵坡量级：主桥面标高按 12m 量级；引道起坡点提前到桥前 ≥400m（≤2%），东侧下坡在桥内提前、桥台处与地面 4.5m 顺接。
- 梁体结构：主梁底箱 + 顶板 + 沥青三层分别用同参数旋转梁叠放；平段标线与护栏按 26m 段叠放（同标高无台阶），坡段护栏用整体旋转细梁。

### 2. 斜拉索 / 吊索方向（曾出现索穿桥底）

- three.js `CylinderGeometry` 长轴沿 Y。由塔顶 (tx,yA) 到桥面锚点 (ax,yB)（yA>yB），以中心点放置后：
  `cb.rotation.z = Math.atan2(ax - tx, yA - yB)`（即 `atan2(dcx, dyc)`，dyc 恒正）。
- 旧写法 `-atan2(dyc,dcx)` 会把索转成近水平并穿过桥底，禁止使用。
- 双索面锚在 `z = ±(桥宽/2 - 2)` 左右；拱桥吊杆同理从拱肋锚到桥面以上。
- 渲染后目检"正立面/主桥近景"确认索均在桥面上方。

### 3. 中央分隔带、标线与装饰（一级公路/城市主干路标配）

- 全线连续中央分隔带：混凝土防撞墙 0.62m 宽 ×1.05m 高，两侧黄实线。
- 每半幅两条车道分隔虚线；两侧白色防撞护栏全程连续（高约 1.05m）。
- 桥梁段双挑路灯，间距约 46m；这些缺一不可，无特殊要求时默认绘制。

### 4. 坐标与跨河定位

- 高斯反算务必核对带号：CGCS2000 3°带 CM=114 → EPSG:4547；CM=111 → EPSG:4546；CM=117 → 另行查表。用 `pyproj.Transformer.from_crs(epsg,'EPSG:4326',always_xy=True)`，参数顺序 (easting, northing)。
- 锚点优先取图纸"路线平面图·平曲线要素表"（起点 QD、交点 JD 的 X/Y），并用相邻点平面距离等于桩号差校核。
- 本分册无逐桩表时：按切线方向直线外延并在说明中明示"示意"；有表后一键替换。
- 桥梁起终点用多张数量表互证（填前夯实、桥头路基处治、特殊路基、软基表），不要凭图名猜测。
- 河网定位用 Overpass：`way["waterway"="river"](bbox)` 取节点，与路线折线求交得跨河桩号；水域多边形用于 3D 水面。
- 平面图若为矢量文字/扫描件：先 PyMuPDF 文字层，再用 RapidOCR 识别页面位图复核坐标数字。

### 5. headless Chrome 渲染纪律（本机实测）

- `file://` 打开看图台时 WebGL 黑屏 → 先起本地服务：`python -m http.server PORT --directory 输出目录`，用 `http://127.0.0.1:PORT/xx.html?v=视角` 渲染。
- SwiftShader 渲染上限约 1.03MP（1296×795）：更大的 `--window-size` 会整图黑屏；先出 1296×795 原图，再 PIL Lanczos 放大并裁成 2560×1440。
- 残留 headless Chrome 进程或堆积的 user-data-dir 会使后续渲染黑屏：每次渲染前杀 headless 进程并清理 profile 目录；连续多视角时优先逐张独立 shell 调用（单条长循环在同一进程内连续跑不可靠）。
- 静态图渲染参数：`--headless=new --no-sandbox --disable-gpu --use-angle=swiftshader --enable-unsafe-swiftshader --hide-scrollbars --user-data-dir=<独立目录> --window-size=1296,795 --virtual-time-budget=15000 --screenshot=out.png "url?v=view"`。
- 交付前检查：`rg -l "@@" 输出/*.html` 应为空；必要时抽取 `<script>` 用 `node --check` 查语法。
