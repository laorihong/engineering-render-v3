# -*- coding: utf-8 -*-
"""服务自检：不启动网络端口，直接测 API 逻辑（需 fastapi/httpx）。

用法：PROJECTS_ROOT=work python service/selftest.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PROJECTS_ROOT", str(ROOT / "work"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from service.app import app  # noqa: E402

c = TestClient(app)
print("healthz:", c.get("/healthz").json())

demo = ROOT / "work" / "demo"
assert (demo / "config.json").exists(), "缺少 work/demo，请先运行 python v3.py demo"

r = c.post("/v1/jobs", json={"project_dir": str(demo), "steps": ["kml"], "timeout_s": 300})
print("job:", r.status_code, r.json())
jid = r.json()["id"]
for _ in range(60):
    j = c.get("/v1/jobs/%s" % jid).json()
    if j["status"] in ("succeeded", "failed"):
        break
    time.sleep(0.5)
print("final:", j["status"], j.get("error", ""))
print("artifacts:", [a["name"] for a in c.get("/v1/jobs/%s/artifacts" % jid).json()][:6])
assert j["status"] == "succeeded", j
print("SELFTEST OK")
