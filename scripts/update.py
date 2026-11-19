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


def search(q):
    """Every repository a GitHub search finds (forks left out), up to the 1000 it gives."""
    items = []
    for page in range(1, 11):
        res = get(f"/search/repositories?q={urllib.parse.quote(q)}&per_page=100&page={page}")
        got = res.get("items", []) if res else []
        items += got
        if len(got) < 100:
            break
    return items


def has_manifest_file(item):
    """A cheap first look, before a repository found by name gets the full check: any plugin.json?"""
    tree = get(f"/repos/{item['full_name']}/git/trees/{urllib.parse.quote(item['default_branch'])}?recursive=1")
    return any(t["path"].endswith("plugin.json") for t in (tree or {}).get("tree", []))


def listed():
    """repos.txt, the repositories with the topic, and those with "solidcraft" in their name,
    description or README that hold a plugin.json. Lines starting with "-" in repos.txt leave a
    repository out."""
    names, skip = [], set()
    with open(os.path.join(ROOT, "repos.txt")) as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line.startswith("-"):
                skip.add(line[1:].strip().lower())
            elif line:
                names.append(line)
    names += [i["full_name"] for i in search("topic:solidcraft-plugin")]
    known = {n.lower() for n in names}
    for i in search("solidcraft"):
        if i["full_name"].lower() not in known | skip and not i.get("archived") and has_manifest_file(i):
            names.append(i["full_name"])
    seen, out = set(), []
    for n in names:
        if n.lower() not in seen | skip:
            seen.add(n.lower())
            out.append(n)
    return out


def manifests(repo, branch):
    """Every SolidCraft plugin manifest in the repository: one, or several in a collection."""
    tree = get(f"/repos/{repo}/git/trees/{urllib.parse.quote(branch)}?recursive=1")
    if not tree:
        return []
    paths = sorted((t["path"] for t in tree.get("tree", []) if t["path"].endswith("plugin.json")
                    and "node_modules" not in t["path"] and "/target/" not in t["path"]), key=len)
    out, ids = [], set()
    for p in paths[:12]:
        text = get(f"/repos/{repo}/contents/{urllib.parse.quote(p)}?ref={urllib.parse.quote(branch)}", raw=True)
        try:
            m = json.loads(text)
        except (TypeError, ValueError):
            continue
        if isinstance(m, dict) and m.get("id") and isinstance(m.get("runtime"), dict) and m["id"] not in ids:
            ids.add(m["id"])  # the same plugin copied into a build folder counts once
            out.append((p, m))
    return out


IMG = re.compile(r'!\[[^\]]*\]\(\s*<?([^)\s>]+)>?[^)]*\)|<img[^>]+src="([^"]+)"', re.I)
SKIP_IMG = re.compile(r"shields\.io|badge|img\.shields|badgen|/actions/workflows/|codecov|\.svg(\?|$)"
                      r"|buymeacoffee|ko-fi|paypal|liberapay|patreon|sponsor", re.I)


def readme_image(repo, branch, folder=""):
    """The first picture in the README (of a folder, or else of the repository) that isn't a badge,
    as an absolute URL."""
    meta = folder and get(f"/repos/{repo}/readme/{urllib.parse.quote(folder)}")
    meta = meta or get(f"/repos/{repo}/readme")
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


# Categories for the filter, in the order they're shown. A plugin goes in the first whose words
# turn up in its id, name, description or topics; CATEGORY_OF settles the ones words get wrong.
CATEGORIES = [
    ("Storage & organizing", r"gridfinity|opengrid|organi[sz]|storage|drawer|bins?\b"),
    ("Hardware & fasteners", r"screw|nut\b|nuts\b|insert|thread|bolt|bearing|extrusion|v-wheel|fastener|hole"),
    ("Gears & motion", r"gear|cycloid|rack\b|pulley|cam\b"),
    ("Woodworking", r"wood|joiner|cabinet|carcass|sheet goods"),
    ("Aero & marine", r"airfoil|wing|propeller|turbine|rotor"),
    ("Shapes & patterns", r"pattern|lattice|honeycomb|gyroid|helix|helical|voronoi|text\b"),
    ("3D printing", r"3d-print|printable|filament|mesh|stl\b|watertight"),
    ("Export & workflow", r"export|step\b|pdm|drawing|sheet|upload|send"),
]
CATEGORY_OF = {
    "solidcraft-aprilcube": "3D printing",
    "filament-swatch": "3D printing",
    "mesh-solidify": "3D printing",
    "helical-sketch": "Shapes & patterns",
    "iso-sheet": "Export & workflow",
    "makeorbit": "Export & workflow",
    "wood-joinery": "Woodworking",
}


def category(p):
    if p["id"] in CATEGORY_OF:
        return CATEGORY_OF[p["id"]]
    words = " ".join([p["id"], p["name"], p["description"], *p["topics"]]).lower()
    return next((name for name, rx in CATEGORIES if re.search(rx, words)), "Other")


ICON_MAX = 40_000
# Anything that could run or fetch something when the SVG is opened on its own: such an icon is left out.
ICON_BAD = re.compile(r"<script|<foreignobject|<iframe|<embed|<object|\bon[a-z]+\s*=|javascript:|"
                      r"(?:href|src)\s*=\s*[\"']\s*(?:https?:|//|data:)|@import|url\(\s*[\"']?\s*(?:https?:|//)", re.I)


def icon_paths(m):
    """The icons the manifest gives its commands (x-solidcraft-icon, SolidCraft 0.44), first one first."""
    out = []
    for e in m.get("runtime", {}).get("entries", []):
        schema = e.get("input_schema") if isinstance(e.get("input_schema"), dict) else {}
        icon = schema.get("x-solidcraft-icon") or e.get("x-solidcraft-icon")
        if isinstance(icon, str) and icon.lower().endswith(".svg") and icon not in out:
            out.append(icon)
    return out


def icon(repo, branch, folder, m):
    """The plugin's first command icon as SVG text, or None when it has none or it doesn't look safe."""
    for rel in icon_paths(m):
        path = os.path.normpath(os.path.join(folder, rel)).lstrip("/")
        if path.startswith(".."):
            continue
        text = get(f"/repos/{repo}/contents/{urllib.parse.quote(path)}?ref={urllib.parse.quote(branch)}", raw=True)
        if text and len(text) <= ICON_MAX and "<svg" in text and not ICON_BAD.search(text):
            return text
    return None


# What a plugin needs that its card can't tell, by plugin id.
NOTES = {
    "easypdm": "Needs an EasyPDM server and the EasyPDM companion program, which also makes the plugin zip for each computer.",
}


def latin(text):
    """Mostly Latin letters (English and most European languages)?"""
    letters = [c for c in text or "" if c.isalpha()]
    return not letters or sum(c < "\u0250" for c in letters) / len(letters) > 0.5


def language(text):
    """The language a non-Latin manifest is written in, as well as one can tell."""
    if re.search(r"[\u0400-\u04ff]", text):
        return "Russian" if re.search(r"[ыэёЫЭЁ]", text) else "Cyrillic"
    if re.search(r"[\u3040-\u30ff]", text):
        return "Japanese"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "Chinese"
    if re.search(r"[\uac00-\ud7af]", text):
        return "Korean"
    return None


def english(m, r):
    """Name, description and a note for the card. A manifest in another script keeps its own words in
    the plugin, but the card is in English when the repository's description is."""
    name = m.get("name") or r["name"]
    desc = m.get("description") or r.get("description") or ""
    if latin(name + desc) or not r.get("description") or not latin(r["description"]):
        return name, desc, None
    words = [w for w in re.split(r"[-_ ]+", m.get("id") or r["name"]) if w.lower() not in ("solidcraft", "plugin", "plugins")]
    english_name = " ".join(words).capitalize() if words and latin(" ".join(words)) else r["name"]
    lang = language(name + desc)
    note = f"The plugin's menu and form are in {lang} ({name})." if lang else f"The plugin's menu and form are not in English ({name})."
    return english_name, r["description"], note


def plugins(repo):
    """The repository's plugins, as cards. A collection of several gets a card per plugin, each with
    its own folder, zip (the release asset named after its id) and picture."""
    r = get(f"/repos/{repo}")
    if not r or r.get("archived") or r.get("private"):
        return []
    branch = r["default_branch"]
    found = manifests(r["full_name"], branch)
    if not found:
        print(f"  {repo}: no SolidCraft plugin manifest, skipped", file=sys.stderr)
        return []
    rel = get(f"/repos/{r['full_name']}/releases/latest")
    zips = [a for a in (rel or {}).get("assets", []) if a["name"].lower().endswith(".zip")]
    assets = []
    for page in range(1, 4):
        rels = get(f"/repos/{r['full_name']}/releases?per_page=100&page={page}") or []
        assets += [a for x in rels for a in x.get("assets", [])]
        if len(rels) < 100:
            break
    several = len(found) > 1
    out = []
    for path, m in found:
        folder = os.path.dirname(path)
        if os.path.basename(folder) in ("plugin", "package"):  # EasyPDM.SolidCraft/plugin: its README is one up
            folder = os.path.dirname(folder)
        mine = lambda a: a["name"].lower().startswith(m["id"].lower())
        zip_ = next((a for a in zips if mine(a)), None) if several else (zips[0] if zips else None)
        # A plugin in a folder of a bigger project (EasyPDM): the repository's topics and downloads
        # are the project's, not the plugin's.
        part = (not several and folder and not zip_ and not any("solidcraft" in t for t in r.get("topics", [])))
        name, desc, note = english(m, r)
        if part:
            note = NOTES.get(m["id"]) or f"Part of the bigger {r['name']} project: see its README for what else it needs."
        out.append({
            "repo": r["full_name"],
            "url": f"{r['html_url']}/tree/{branch}/{urllib.parse.quote(folder)}" if (several or part) and folder else r["html_url"],
            "owner": r["owner"]["login"],
            "avatar": r["owner"]["avatar_url"],
            "id": m.get("id"),
            "name": name,
            "description": desc,
            "note": note,
            "version": m.get("version"),
            "entries": entries(m),
            "commands": len(m.get("runtime", {}).get("commands", [])),
            "permissions": sorted(m.get("runtime", {}).get("permissions", {}).keys()) if isinstance(m.get("runtime", {}).get("permissions"), dict) else [],
            "topics": [] if part else tags(r.get("topics", [])),
            "stars": r.get("stargazers_count", 0),
            "license": (r.get("license") or {}).get("spdx_id"),
            "updated": r.get("pushed_at"),
            "created": r.get("created_at"),
            "release": rel and {
                "tag": rel["tag_name"],
                "url": rel["html_url"],
                "date": rel.get("published_at"),
                "zip": zip_["browser_download_url"] if zip_ else None,
            },
            "downloads": 0 if part else sum(a.get("download_count", 0) for a in assets if not several or mine(a)),
            "image": readme_image(r["full_name"], branch, folder if several or part else ""),
            "has_topic": "solidcraft-plugin" in r.get("topics", []),
            "icon_svg": icon(r["full_name"], branch, os.path.dirname(path), m),
        })
        out[-1]["category"] = category(out[-1])
    return out


def main():
    out = []
    for repo in listed():
        print(repo, file=sys.stderr)
        out += plugins(repo)
    # plugins without a zip to download last, as on the page
    out.sort(key=lambda p: (not (p.get("release") or {}).get("zip"), -p["stars"], p["name"].lower()))
    build_site.build(out)  # gives each plugin its slug, and writes the pages and sitemap
    data = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "plugins": out}
    with open(os.path.join(ROOT, "data", "plugins.json"), "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"{len(out)} plugins", file=sys.stderr)


if __name__ == "__main__":
    main()
