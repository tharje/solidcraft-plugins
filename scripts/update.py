#!/usr/bin/env python3
"""Collect SolidCraft plugins from GitHub into data/plugins.json.

A repository is listed when it has the `solidcraft-plugin` topic or is named in repos.txt,
and holds a SolidCraft plugin manifest (a plugin.json with an `id` and a `runtime`).
Set GITHUB_TOKEN for a higher API rate limit.
"""
import base64, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

import build_site

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def get(path, raw=False):
    req = urllib.request.Request(path if path.startswith("http") else API + path)
    req.add_header("Accept", "application/vnd.github.raw" if raw else "application/vnd.github+json")
    req.add_header("User-Agent", "solidcraft-plugin-hub")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        if e.code in (404, 409, 451):
            return None
        raise
    return body.decode("utf-8", "replace") if raw else json.loads(body)


def listed():
    names = []
    with open(os.path.join(ROOT, "repos.txt")) as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                names.append(line)
    page = 1
    while True:
        q = urllib.parse.quote("topic:solidcraft-plugin")
        res = get(f"/search/repositories?q={q}&per_page=100&page={page}")
        items = res.get("items", []) if res else []
        names += [i["full_name"] for i in items]
        if len(items) < 100:
            break
        page += 1
    seen, out = set(), []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def manifest(repo, branch):
    tree = get(f"/repos/{repo}/git/trees/{urllib.parse.quote(branch)}?recursive=1")
    if not tree:
        return None, None
    paths = sorted((t["path"] for t in tree.get("tree", []) if t["path"].endswith("plugin.json")
                    and "node_modules" not in t["path"] and "/target/" not in t["path"]), key=len)
    for p in paths[:8]:
        text = get(f"/repos/{repo}/contents/{urllib.parse.quote(p)}?ref={urllib.parse.quote(branch)}", raw=True)
        try:
            m = json.loads(text)
        except (TypeError, ValueError):
            continue
        if isinstance(m, dict) and m.get("id") and isinstance(m.get("runtime"), dict):
            return p, m
    return None, None


IMG = re.compile(r'!\[[^\]]*\]\(\s*<?([^)\s>]+)>?[^)]*\)|<img[^>]+src="([^"]+)"', re.I)
SKIP_IMG = re.compile(r"shields\.io|badge|img\.shields|badgen|/actions/workflows/|codecov|\.svg(\?|$)"
                      r"|buymeacoffee|ko-fi|paypal|liberapay|patreon|sponsor", re.I)


def readme_image(repo, branch):
    """The first picture in the README that isn't a badge, as an absolute URL."""
    meta = get(f"/repos/{repo}/readme")
    if not meta:
        return None
    text = get(meta["url"], raw=True) or ""
    base = os.path.dirname(meta["path"])
    for m in IMG.finditer(text):
        url = m.group(1) or m.group(2)
        if SKIP_IMG.search(url):
            continue
        if url.startswith(("http://", "https://")):
            return url
        path = os.path.normpath(os.path.join(base, url.lstrip("./") if url.startswith("./") else url)).lstrip("/")
        return f"https://raw.githubusercontent.com/{repo}/{branch}/{urllib.parse.quote(path)}"
    return None


# Topics that say how a plugin is built, or only that it is one: not shown as tags.
HIDDEN = {"solidcraft", "solidcraft-plugin", "plugin", "plugins", "cad-plugin", "rust", "wasm", "webassembly",
          "wasm-component", "wasi", "wit", "python", "typescript", "javascript", "agents", "cli"}
SAME = {"3d-print": "3d-printing", "3dprinting": "3d-printing", "parametric-cad": "parametric", "gear": "gears"}


def tags(topics):
    out = []
    for t in topics:
        t = SAME.get(t, t)
        if t not in HIDDEN and t not in out:
            out.append(t)
    return out


def entries(m):
    rt = m.get("runtime", {})
    out = []
    for e in rt.get("entries", []):
        slots = [s.get("name") for s in e.get("slots", []) if s.get("name")]
        out.append(slots[0] if slots else e.get("name"))
    # Several entries in one menu (EasyPDM's four under "File"): the menu says nothing, the entry names do.
    if len(set(out)) < len(out):
        out = [e.get("name") for e in rt.get("entries", [])]
    return out


def plugin(repo):
    r = get(f"/repos/{repo}")
    if not r or r.get("archived") or r.get("private"):
        return None
    branch = r["default_branch"]
    path, m = manifest(r["full_name"], branch)
    if not m:
        print(f"  {repo}: no SolidCraft plugin manifest, skipped", file=sys.stderr)
        return None
    rel = get(f"/repos/{r['full_name']}/releases/latest")
    zips = [a for a in (rel or {}).get("assets", []) if a["name"].lower().endswith(".zip")]
    downloads = 0
    for page in range(1, 4):
        rels = get(f"/repos/{r['full_name']}/releases?per_page=100&page={page}") or []
        downloads += sum(a.get("download_count", 0) for x in rels for a in x.get("assets", []))
        if len(rels) < 100:
            break
    return {
        "repo": r["full_name"],
        "url": r["html_url"],
        "owner": r["owner"]["login"],
        "avatar": r["owner"]["avatar_url"],
        "id": m.get("id"),
        "name": m.get("name") or r["name"],
        "description": m.get("description") or r.get("description") or "",
        "version": m.get("version"),
        "entries": entries(m),
        "commands": len(m.get("runtime", {}).get("commands", [])),
        "permissions": sorted(m.get("runtime", {}).get("permissions", {}).keys()) if isinstance(m.get("runtime", {}).get("permissions"), dict) else [],
        "topics": tags(r.get("topics", [])),
        "stars": r.get("stargazers_count", 0),
        "license": (r.get("license") or {}).get("spdx_id"),
        "updated": r.get("pushed_at"),
        "created": r.get("created_at"),
        "release": rel and {
            "tag": rel["tag_name"],
            "url": rel["html_url"],
            "date": rel.get("published_at"),
            "zip": zips[0]["browser_download_url"] if zips else None,
        },
        "downloads": downloads,
        "image": readme_image(r["full_name"], branch),
        "has_topic": "solidcraft-plugin" in r.get("topics", []),
    }


def main():
    out = []
    for repo in listed():
        print(repo, file=sys.stderr)
        p = plugin(repo)
        if p:
            out.append(p)
    out.sort(key=lambda p: (-p["stars"], p["name"].lower()))
    build_site.build(out)  # gives each plugin its slug, and writes the pages and sitemap
    data = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "plugins": out}
    with open(os.path.join(ROOT, "data", "plugins.json"), "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"{len(out)} plugins", file=sys.stderr)


if __name__ == "__main__":
    main()
