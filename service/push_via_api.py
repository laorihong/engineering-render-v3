# -*- coding: utf-8 -*-
"""当 git push（github.com:443）被网络阻断时，用 GitHub Git Data API 提交文件。

用法（在仓库根目录）：
    python service/push_via_api.py laorihong/engineering-render-v3 main "提交说明" [文件...]

不传文件列表时，自动提交仓库未推送的改动（git status --porcelain 中的已跟踪/新增文件，
排除 work/ 等被 .gitignore 忽略的路径）。
Token 取 `gh auth token`（需先 gh auth login）或环境变量 GH_TOKEN。
"""
import base64
import json
import os
import subprocess
import sys
import urllib.request


def token():
    t = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if t:
        return t.strip()
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def api(method, path, body=None, tok=None):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": "Bearer " + tok,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "engineering-render-v3-push"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def changed_files():
    out = subprocess.check_output(["git", "status", "--porcelain"], text=True)
    files = []
    for ln in out.splitlines():
        p = ln[3:].strip().strip('"')
        if " -> " in p:
            p = p.split(" -> ")[-1]
        if p and os.path.isfile(p) and not p.startswith("work/"):
            files.append(p)
    return sorted(set(files))


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    repo, branch, message = sys.argv[1], sys.argv[2], sys.argv[3]
    files = sys.argv[4:] or changed_files()
    if not files:
        print("没有需要提交的文件")
        return
    tok = token()
    ref = api("GET", "/repos/%s/git/ref/heads/%s" % (repo, branch), tok=tok)
    base_commit = ref["object"]["sha"]
    base_tree = api("GET", "/repos/%s/git/commits/%s" % (repo, base_commit), tok=tok)["tree"]["sha"]
    tree = []
    for p in files:
        content = base64.b64encode(open(p, "rb").read()).decode()
        blob = api("POST", "/repos/%s/git/blobs" % repo,
                   {"content": content, "encoding": "base64"}, tok=tok)
        tree.append({"path": p.replace("\\", "/"), "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("blob", p, blob["sha"][:8])
    new_tree = api("POST", "/repos/%s/git/trees" % repo,
                   {"base_tree": base_tree, "tree": tree}, tok=tok)["sha"]
    commit = api("POST", "/repos/%s/git/commits" % repo,
                 {"message": message, "tree": new_tree, "parents": [base_commit]}, tok=tok)
    api("PATCH", "/repos/%s/git/refs/heads/%s" % (repo, branch),
        {"sha": commit["sha"], "force": False}, tok=tok)
    print("pushed", commit["sha"], "->", repo, branch)


if __name__ == "__main__":
    main()
