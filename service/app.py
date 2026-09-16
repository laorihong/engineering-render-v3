# -*- coding: utf-8 -*-
"""engineering-render-v3 HTTP 服务：给 MaxKB / Dify / 其他平台当"工具"调用。

设计要点：
- 只暴露白名单命令（fetch-base/map2d/viewer/render/overview/kml/extract/geo/docx），不接受任意 shell；
- 所有项目目录必须位于 PROJECTS_ROOT 之下（防目录穿越）；
- 渲染类长任务走异步作业（/v1/jobs），避免平台工具调用超时；
- 可选 API Key（环境变量 SERVICE_API_KEY，留空则不校验，仅建议内网使用）。

启动：uvicorn service.app:app --host 0.0.0.0 --port 8000
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_ROOT = Path(os.environ.get("PROJECTS_ROOT", ROOT / "work")).resolve()
JOBS_DIR = Path(os.environ.get("JOBS_DIR", PROJECTS_ROOT / "_jobs")).resolve()
API_KEY = os.environ.get("SERVICE_API_KEY", "").strip()
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "2"))
VERSION = "1.0.0"
STEPS = {"fetch-base", "map2d", "viewer", "render", "overview", "kml"}
DEFAULT_PIPELINE = ["fetch-base", "map2d", "viewer", "render", "overview", "kml"]

app = FastAPI(title="engineering-render-v3 service", version=VERSION)
_jobs = {}
_lock = threading.Lock()


# ---------- 鉴权与路径安全 ----------
def auth(x_api_key: Optional[str] = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")


def safe_path(p: str, must_exist: bool = False) -> Path:
    q = Path(p)
    q = (PROJECTS_ROOT / q).resolve() if not q.is_absolute() else q.resolve()
    if PROJECTS_ROOT not in q.parents and q != PROJECTS_ROOT:
        raise HTTPException(status_code=400, detail="path outside PROJECTS_ROOT: %s" % q)
    if must_exist and not q.exists():
        raise HTTPException(status_code=404, detail="not found: %s" % q)
    return q


def _job_dir(jid: str) -> Path:
    d = JOBS_DIR / jid
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log_line(jid: str, line: str):
    p = _job_dir(jid) / "log.txt"
    with open(p, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def _run(cmd: List[str], cwd: Path, jid: Optional[str] = None, timeout: int = 3600):
    if jid:
        _log_line(jid, "$ " + " ".join(cmd))
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, env=env)
    out = (p.stdout or "") + (p.stderr or "")
    if jid:
        for ln in out.splitlines():
            _log_line(jid, ln)
    return p.returncode, out


def _artifacts(project_dir: Path):
    out_dir = project_dir / "输出"
    res = []
    if out_dir.exists():
        for f in sorted(out_dir.rglob("*")):
            if f.is_file():
                res.append({"name": str(f.relative_to(out_dir)).replace("\\", "/"),
                            "size": f.stat().st_size})
    return res


def _run_job(jid: str, project_dir: Path, steps: List[str], timeout: int):
    job = _jobs[jid]
    job["status"] = "running"
    job["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    cfg = project_dir / "config.json"
    try:
        for step in steps:
            if step not in STEPS:
                raise ValueError("unsupported step: %s" % step)
            if not cfg.exists():
                raise ValueError("缺少 config.json：%s" % cfg)
            code, out = _run([sys.executable, str(ROOT / "v3.py"), "-c", str(cfg), step],
                             cwd=project_dir, jid=jid, timeout=timeout)
            if code != 0:
                raise RuntimeError("step %s 失败(exit=%d)" % (step, code))
        job["status"] = "succeeded"
    except Exception as e:  # noqa: BLE001
        job["status"] = "failed"
        job["error"] = repr(e)
        _log_line(jid, "[ERROR] " + repr(e))
    finally:
        job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        job["artifacts"] = _artifacts(project_dir)
        (_job_dir(jid) / "job.json").write_text(
            json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- 请求模型 ----------
class PreflightReq(BaseModel):
    network: bool = False
    config: Optional[str] = None


class RunStepReq(BaseModel):
    project_dir: str = Field(..., description="项目目录（PROJECTS_ROOT 之下）")
    step: str = Field(..., description="fetch-base|map2d|viewer|render|overview|kml")
    timeout_s: int = 600


class JobReq(BaseModel):
    project_dir: str
    steps: List[str] = Field(default_factory=lambda: list(DEFAULT_PIPELINE))
    timeout_s: int = 3600
    note: str = ""


class ExtractReq(BaseModel):
    pdf: str
    out_dir: str = "提取"
    timeout_s: int = 1800


class GeoReq(BaseModel):
    table: str = Field(..., description="csv/json：station_m,X,Y")
    cm_deg: float = Field(..., description="中央子午线经度")
    out: str = "模型/project_geometry.json"
    project_dir: Optional[str] = None


class DocxReq(BaseModel):
    md: str
    out_docx: str


# ---------- 基础接口 ----------
@app.get("/healthz")
def healthz():
    import importlib
    deps = {}
    for mod in ("pymupdf", "PIL", "docx"):
        try:
            importlib.import_module(mod)
            deps[mod] = True
        except Exception:
            deps[mod] = False
    chrome = os.environ.get("CHROME_PATH", "")
    if not chrome or not os.path.exists(chrome):
        try:
            sys.path.insert(0, str(ROOT))
            from pipeline.common import find_chrome
            chrome = find_chrome() or ""
        except Exception:
            chrome = ""
    return {"ok": True, "version": VERSION, "python": sys.version.split()[0],
            "deps": deps, "chrome": chrome or None,
            "projects_root": str(PROJECTS_ROOT),
            "auth": bool(API_KEY)}


@app.get("/")
def index():
    return {"service": "engineering-render-v3",
            "docs": "/docs", "health": "/healthz",
            "start_job": "POST /v1/jobs",
            "steps": sorted(STEPS),
            "pipeline": DEFAULT_PIPELINE}


@app.post("/v1/preflight", dependencies=[Depends(auth)])
def preflight(req: PreflightReq):
    cmd = [sys.executable, str(ROOT / "preflight.py")]
    if req.network:
        cmd.append("--network")
    if req.config:
        cmd += ["--config", str(safe_path(req.config))]
    code, out = _run(cmd, ROOT, timeout=300)
    return {"exit": code, "output": out}


# ---------- 同步执行单个步骤（适合 map2d/kml/viewer 等快步骤） ----------
@app.post("/v1/v3/run", dependencies=[Depends(auth)])
def v3_run(req: RunStepReq):
    if req.step not in STEPS:
        raise HTTPException(status_code=400, detail="unsupported step: %s" % req.step)
    project_dir = safe_path(req.project_dir, must_exist=True)
    cfg = project_dir / "config.json"
    if not cfg.exists():
        raise HTTPException(status_code=400, detail="config.json 不存在：%s" % cfg)
    code, out = _run([sys.executable, str(ROOT / "v3.py"), "-c", str(cfg), req.step],
                     cwd=project_dir, timeout=req.timeout_s)
    return {"exit": code, "output": out, "artifacts": _artifacts(project_dir)}


# ---------- 异步作业：适合 render 之类的长任务 ----------
@app.post("/v1/jobs", dependencies=[Depends(auth)])
def create_job(req: JobReq):
    project_dir = safe_path(req.project_dir, must_exist=True)
    bad = [s for s in req.steps if s not in STEPS]
    if bad:
        raise HTTPException(status_code=400, detail="unsupported steps: %s" % bad)
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    job = {"id": jid, "project_dir": str(project_dir), "steps": req.steps,
           "note": req.note, "status": "queued",
           "created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "artifacts": []}
    with _lock:
        _jobs[jid] = job
    _job_dir(jid)
    (_job_dir(jid) / "job.json").write_text(
        json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    _log_line(jid, "job %s -> %s steps=%s" % (jid, project_dir, req.steps))
    threading.Thread(target=_run_job, args=(jid, project_dir, req.steps, req.timeout_s),
                     daemon=True).start()
    return job


@app.get("/v1/jobs", dependencies=[Depends(auth)])
def list_jobs():
    with _lock:
        return sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)


@app.get("/v1/jobs/{job_id}", dependencies=[Depends(auth)])
def get_job(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        p = JOBS_DIR / job_id / "job.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/v1/jobs/{job_id}/log", dependencies=[Depends(auth)])
def get_log(job_id: str, tail: int = 200):
    p = JOBS_DIR / job_id / "log.txt"
    if not p.exists():
        raise HTTPException(status_code=404, detail="log not found")
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"lines": lines[-tail:]}


@app.get("/v1/jobs/{job_id}/artifacts", dependencies=[Depends(auth)])
def get_artifacts(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return _artifacts(Path(job["project_dir"]))


@app.get("/v1/jobs/{job_id}/artifacts/{name:path}", dependencies=[Depends(auth)])
def download_artifact(job_id: str, name: str):
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    base = Path(job["project_dir"]) / "输出"
    p = (base / name).resolve()
    if base not in p.parents or not p.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(str(p))


@app.get("/v1/jobs/{job_id}/zip", dependencies=[Depends(auth)])
def download_zip(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    out_dir = Path(job["project_dir"]) / "输出"
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail="输出 目录不存在")
    z = _job_dir(job_id) / "成果包.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(out_dir))
    return FileResponse(str(z), filename="%s-成果包.zip" % Path(job["project_dir"]).name)


# ---------- 文件上传（供平台侧提交图纸/坐标表） ----------
@app.post("/v1/upload", dependencies=[Depends(auth)])
async def upload(file: UploadFile = File(...)):
    updir = PROJECTS_ROOT / "_uploads"
    updir.mkdir(parents=True, exist_ok=True)
    name = Path(file.filename or "upload.bin").name
    dst = updir / ("%s_%s" % (time.strftime("%Y%m%d%H%M%S"), name))
    with open(dst, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": str(dst), "size": dst.stat().st_size}


# ---------- 快捷工具：extract / geo / docx ----------
@app.post("/v1/extract", dependencies=[Depends(auth)])
def extract(req: ExtractReq):
    pdf = safe_path(req.pdf, must_exist=True)
    out = req.out_dir if Path(req.out_dir).is_absolute() else str(pdf.parent / req.out_dir)
    code, o = _run([sys.executable, str(ROOT / "v3.py"), "extract", str(pdf), "--out", out],
                   cwd=pdf.parent, timeout=req.timeout_s)
    return {"exit": code, "output": o, "out_dir": out}


@app.post("/v1/geo", dependencies=[Depends(auth)])
def geo(req: GeoReq):
    table = safe_path(req.table, must_exist=True)
    cwd = safe_path(req.project_dir) if req.project_dir else table.parent
    out = req.out if Path(req.out).is_absolute() else str(cwd / req.out)
    code, o = _run([sys.executable, str(ROOT / "v3.py"), "geo", "--table", str(table),
                    "--cm", str(req.cm_deg), "--out", out], cwd=cwd, timeout=900)
    return {"exit": code, "output": o, "out": out}


@app.post("/v1/docx", dependencies=[Depends(auth)])
def docx(req: DocxReq):
    md = safe_path(req.md, must_exist=True)
    out = req.out_docx if Path(req.out_docx).is_absolute() else str(md.parent / req.out_docx)
    code, o = _run([sys.executable, str(ROOT / "v3.py"), "docx", str(md), out],
                   cwd=md.parent, timeout=600)
    return {"exit": code, "output": o, "out": out}
