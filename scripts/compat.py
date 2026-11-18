#!/usr/bin/env python3
"""Try every listed plugin in the newest SolidCraft release, into data/compat.json.

For each plugin with a release zip: does SolidCraft load it (plugin.inspect), and does each of its
commands run with its default values (plugin.run in solidcraft-cli, headless, on Linux)? A plugin
that asks for files or sensitive command groups is only loaded, never run. A command that needs
something picked first can't run on its own, so "loads" is no sign of a fault; the site only ever
shows what worked. A plugin is tried again when its release or SolidCraft's changes.

  compat.py                 newest stable SolidCraft, downloaded into .cache/
  compat.py --build DIR     an unpacked SolidCraft build already on disk
Set GITHUB_TOKEN for a higher API rate limit.
"""
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, tempfile, time, urllib.request, zipfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, ".cache")
REPO = "tangency-labs/solidcraft"
ZIP_MAX = 50 * 1024 * 1024
RUN_SECONDS = 120


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "solidcraft-plugin-hub"})
    if os.environ.get("GITHUB_TOKEN") and url.startswith("https://api.github.com/"):
        req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read(ZIP_MAX + 1)
    if len(data) > ZIP_MAX:
        raise ValueError("download too large")
    return data if binary else json.loads(data)


def solidcraft():
    """(version, build dir) of the newest stable Linux release, checked against its SHA256SUMS."""
    rel = get(f"https://api.github.com/repos/{REPO}/releases/latest")
    version = rel["tag_name"].lstrip("v")
    name = f"solidcraft-{version}-linux-x86_64"
    target = os.path.join(CACHE, name)
    if not os.path.exists(os.path.join(target, "bin", "solidcraft-cli")):
        base = f"https://github.com/{REPO}/releases/download/v{version}/"
        sums = get(base + "SHA256SUMS.txt", binary=True).decode()
        want = next(l.split()[0] for l in sums.splitlines() if l.endswith(f" {name}.tar.gz"))
        req = urllib.request.Request(base + f"{name}.tar.gz", headers={"User-Agent": "solidcraft-plugin-hub"})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
        if hashlib.sha256(data).hexdigest() != want:
            raise RuntimeError(f"checksum mismatch for {name}.tar.gz")
        os.makedirs(CACHE, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            t.extractall(CACHE, filter="data")
    return version, target


def cli(build, env, *args):
    return subprocess.run([os.path.join(build, "bin", "solidcraft-cli"), *args], capture_output=True,
                          text=True, timeout=RUN_SECONDS, env=env)


def unpack(data, into):
    """The folder in the zip that holds plugin.json (nothing is written outside `into`)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for m in z.infolist():
            path = os.path.normpath(m.filename)
            if path.startswith("..") or os.path.isabs(path):
                raise ValueError("unsafe path in zip")
        z.extractall(into)
    found = sorted((os.path.join(d, "plugin.json") for d, _, files in os.walk(into) if "plugin.json" in files), key=len)
    if not found:
        raise ValueError("no plugin.json in the zip")
    # SolidCraft wants the folder named after the plugin's id, as its installer does
    with open(found[0]) as f:
        pid = str(json.load(f).get("id") or "plugin")
    folder = os.path.join(os.path.dirname(into), "installed", os.path.basename(pid))
    shutil.copytree(os.path.dirname(found[0]), folder)
    return folder


def try_plugin(build, zip_url):
    """{"loads": bool, "ran": [entry names], "entries": n, "error": str?}"""
    with tempfile.TemporaryDirectory() as tmp:
        # SolidCraft's own settings and plugin folders, kept apart from anything else on the machine
        env = dict(os.environ, HOME=tmp, XDG_DATA_HOME=f"{tmp}/data", XDG_CONFIG_HOME=f"{tmp}/config",
                   XDG_CACHE_HOME=f"{tmp}/cache")
        folder = unpack(get(zip_url, binary=True), os.path.join(tmp, "plugin"))
        r = cli(build, env, "exec", "plugin.inspect", json.dumps({"path": folder}))
        if r.returncode:
            return {"loads": False, "ran": [], "entries": 0, "error": (r.stderr or r.stdout).strip()[-300:]}
        info = json.loads(r.stdout)
        manifest = info.get("manifest") or {}
        rt = manifest.get("runtime") or {}
        entries = [e.get("name") for e in rt.get("entries", []) if e.get("name")]
        out = {"loads": True, "ran": [], "entries": len(entries)}
        perms = rt.get("permissions") or {}
        if perms.get("files") or perms.get("command_groups") or perms.get("input_folder") or perms.get("net"):
            out["skipped"] = "asks for permissions"   # files or sensitive commands: loaded, not run
            return out
        for entry in entries:
            script = os.path.join(tmp, "run.json")
            with open(script, "w") as f:
                json.dump({"commands": [{"command": "plugin.run", "params": {
                    "path": folder, "approval": info["approval"], "entry": entry, "params": {}}}]}, f)
            try:
                r = cli(build, env, "run", script, "--save", os.path.join(tmp, "out.sc"), "--quiet")
            except subprocess.TimeoutExpired:
                continue
            if r.returncode == 0:
                out["ran"].append(entry)
        return out


def main():
    args = sys.argv[1:]
    if args[:1] == ["--build"]:
        build = os.path.abspath(args[1])
        r = subprocess.run([os.path.join(build, "bin", "solidcraft-cli"), "--version"], capture_output=True, text=True)
        version = r.stdout.split()[-1].lstrip("v") if r.returncode == 0 and r.stdout.split() else os.path.basename(build)
    else:
        version, build = solidcraft()
    with open(os.path.join(DATA, "plugins.json")) as f:
        plugins = json.load(f)["plugins"]
    path = os.path.join(DATA, "compat.json")
    try:
        with open(path) as f:
            old = json.load(f).get("plugins", {})
    except (OSError, ValueError):
        old = {}
    results = {}
    for p in plugins:
        rel = p.get("release") or {}
        if not rel.get("zip"):
            continue
        prev = old.get(p["slug"])
        if prev and prev.get("release") == rel["tag"] and prev.get("solidcraft") == version:
            results[p["slug"]] = prev
            continue
        print(f"{p['slug']} {rel['tag']} on SolidCraft {version}", file=sys.stderr)
        try:
            r = try_plugin(build, rel["zip"])
        except Exception as e:
            r = {"loads": False, "ran": [], "entries": 0, "error": f"{type(e).__name__}: {e}"[:300]}
        r.update(release=rel["tag"], solidcraft=version,
                 tested=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        print(f"  {r}", file=sys.stderr)
        results[p["slug"]] = r
    with open(path, "w") as f:
        json.dump({"solidcraft": version, "plugins": results}, f, indent=1, sort_keys=True)
        f.write("\n")
    # put the results on the cards and pages
    import build_site
    with open(os.path.join(DATA, "plugins.json")) as f:
        data = json.load(f)
    build_site.build(data["plugins"])
    with open(os.path.join(DATA, "plugins.json"), "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()
