# engineering-render-v3 对外服务（MaxKB / Dify 工具接入）

把本仓库的 V3 流水线包成 HTTP 服务，让平台（如 MaxKB）以「工具」形式调用，供同事在问答界面提交项目、触发渲染、下载成果包。

## 1. 本地直接运行

```bash
cd engineering-render-v3
pip install -r requirements.txt -r service/requirements.txt
set SERVICE_API_KEY=change-me        # Windows；Linux 用 export
set PROJECTS_ROOT=work
python -m uvicorn service.app:app --host 0.0.0.0 --port 8000
```

自检（不占端口）：

```bash
python v3.py demo --dir work/demo     # 先生成演示项目
python service/selftest.py
```

## 2. Docker 部署（推荐，内网服务器）

```bash
cd engineering-render-v3
docker compose up -d --build
curl http://127.0.0.1:8000/healthz
```

- 镜像内已装 Chromium 与中文字体（Noto CJK），`CHROME_PATH=/usr/bin/chromium`；
- `./work` 挂载进容器作为项目根目录（`PROJECTS_ROOT=/app/work`）；
- 修改 `SERVICE_API_KEY`（`docker-compose.yml` 或同目录 `.env`），务必改掉默认值。

## 3. 典型调用

```bash
# 3.1 上传图纸（返回服务端路径）
curl -H "X-API-Key: change-me" -F "file=@施工图.pdf" http://IP:8000/v1/upload

# 3.2 坐标表 → 几何 JSON
curl -H "X-API-Key: change-me" -H "Content-Type: application/json" \
  -d '{"table":"/app/work/_uploads/xxx.csv","cm_deg":114.0,"project_dir":"/app/work/十里亭大桥"}' \
  http://IP:8000/v1/geo

# 3.3 创建渲染作业（异步）
curl -H "X-API-Key: change-me" -H "Content-Type: application/json" \
  -d '{"project_dir":"/app/work/十里亭大桥","note":"同事A提交"}' \
  http://IP:8000/v1/jobs

# 3.4 查询进度 / 下载成果包
curl -H "X-API-Key: change-me" http://IP:8000/v1/jobs/<job_id>
curl -H "X-API-Key: change-me" -o 成果包.zip http://IP:8000/v1/jobs/<job_id>/zip
```

## 4. 接进 MaxKB

1. 部署本服务，确认 `http://内网IP:8000/healthz` 返回 `ok: true`；
2. MaxKB →【工具】→【创建】→ 选择由 OpenAPI 导入（或"创建工具"后粘贴 `service/openapi.yaml`，把 `servers.url` 改成内网地址）；
3. 鉴权：OpenAPI 里已声明 `X-API-Key` 头，填 `SERVICE_API_KEY` 的值；
4. MaxKB →【智能体】→ 新建（建议高级智能体）→ 在【技能】里勾选上一步创建的工具（可再挂知识库：把 SKILL.md/资料清单作为问答知识）；
5. 调试示例对话：
   - "把 /app/work/十里亭大桥 这个项目跑一遍，出全套成果" → 模型调用 `createJob`，返回 job_id；
   - "作业 xxx 好了吗" → 调用 `getJob`；
   - "把成果包发我" → 调用 `downloadJobZip`。

> 提示：渲染是长任务，务必让智能体先用 `createJob` 再轮询 `getJob`，不要在工具里同步等 render。

## 5. 安全与边界

- 路径被限制在 `PROJECTS_ROOT` 内，且只允许白名单步骤，不接受任意 shell；
- 建议部署在内网，并设置 `SERVICE_API_KEY`；如需外网访问，前置 Nginx + HTTPS + IP 白名单；
- MaxKB 社区版在部分 API 能力上受限（共享资源/授权属 X-Pack），但"调用外部 HTTP 工具"不受影响。

## 6. 后续升级为 MCP

若希望模型自主选择工具（更接近 Codex 技能体验），可在此服务外再包一层 MCP Server（SSE/Streamable HTTP），把 `createJob/getJob/downloadJobZip` 暴露为 MCP tools，然后在 MaxKB【工具】→【创建 MCP】填写：

```json
{"engineering-render":{"url":"http://内网IP:9000/mcp","transport":"sse"}}
```

并在高级智能体中使用【MCP 调用】节点。
