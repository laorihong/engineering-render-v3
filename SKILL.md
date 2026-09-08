---
name: engineering-render-v3
description: "V3 工程效果图流水线（可迁移 CLI 版）：PDF 解析、逐桩坐标反算、真实卫星/路网底图、参数化 3D 看图台、2D 走向图、静态渲染、KML 与 WPS 说明。适用于桥梁/道路/互通/园区等‘图纸→六件套’项目，可在另一台装有 Python+Chrome+Codex 的机器上复用。"
---

# engineering-render-v3（流水线版）

本技能是“工程效果图 V3 方法”的**可执行仓库版**。与系统级
`engineering-render` 技能配合使用：本仓库负责参数化脚本与自动步骤，
`engineering-render` 提供读图判断、地理锚定与观感把握的经验规则。

## 使用

1. `python preflight.py` 体检环境；
2. `python v3.py demo` 无网络自检；
3. 按 `README.md`/`config.example.json` 建项目配置；
4. AI 完成图纸解读后生成 `模型/project_geometry.json`；
5. `python v3.py -c config.json fetch-base map2d viewer render overview kml`。

## 规则

- 禁止在脚本/文档中写死本机绝对路径；一律相对仓库或 config（`work_dir`）。
- 坐标与桩号：以图纸/逐桩坐标为准；示意锚点必须写进说明。
- 底图与成果仅供内部示意；对外发布前核对瓦片服务许可。
- 复杂桥型/长线路分段等需要项目级建模判断时，由智能体按
  `references/`（随系统 `engineering-render` 技能提供）扩展 viewer/map2d。

## 参考

- `README.md`（快速上手与换机清单）
- `pipeline/`（各步骤源码，含数据契约注释）
- `config.example.json`（配置样例）
