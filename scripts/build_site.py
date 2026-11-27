#!/usr/bin/env python3
"""Build the static parts of the site from data/plugins.json, so search engines see every plugin.

- index.html: the plugin cards between the plugins markers (app.js redraws them for search and
  sorting) and the ItemList structured data between the jsonld markers.
- plugins/<slug>/index.html: one page per plugin.
- sitemap.xml.
Nothing here depends on today's date, so the files only change when a plugin does.
"""
import html, json, os, re, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://tharje.github.io/solidcraft-plugins/"
REPORT = "https://github.com/tharje/solidcraft-plugins/issues/new?template=plugin-problem.yml"
e = html.escape


def report_url(p):
    q = urllib.parse.urlencode({"title": f"[Plugin problem] {p['name']}", "plugin": f"{p['name']} ({p['url']})"})
    return f"{REPORT}&{q}"


def author_report_url(p):
    """A new issue in the plugin's own repository, or None if it has issues turned off."""
    if p.get("issues") is False:
        return None
    q = urllib.parse.urlencode({"title": f"{p['name']}: "})
    return f"https://github.com/{p['repo']}/issues/new?{q}"


def report_menu(p):
    """Report a problem: to the plugin's author (bugs, questions) or to this list (warnings)."""
    author = author_report_url(p)
    to_author = (f'<a class="to-author" href="{e(author)}" target="_blank" rel="noopener"><b>To the author</b>'
                 f'<span>Bugs, questions and ideas</span></a>') if author else ""
    return (f'<details class="report"><summary>Report a problem</summary><div class="menu">{to_author}'
            f'<a class="to-list" href="{e(report_url(p))}" target="_blank" rel="noopener"><b>To this list</b>'
            f'<span>Crashes SolidCraft, harms a design, won\'t install or looks unsafe</span></a></div></details>')


# What each permission means to someone installing the plugin; clock (the time of day) is left out.
ASKS = {"files": "files", "input_folder": "a folder", "net": "the network", "command_groups": "extra SolidCraft commands"}


def asks(p):
    """The permissions a plugin asks for, in words, or None."""
    words = [w for x, w in ASKS.items() if x in p.get("permissions", [])]
    return {"label": "Asks for: " + ", ".join(words),
            "title": "SolidCraft asks you to allow this when you install the plugin."} if words else None


def similar(p, plugins, i, n=6):
    """Other plugins for the page's end: the same category first, then a different handful of the rest."""
    same = [o for o in plugins if o is not p and o.get("category") == p.get("category")]
    rest = [o for o in plugins if o is not p and o not in same]
    rest = rest[i % len(rest):] + rest[:i % len(rest)] if rest else []
    return (same + rest)[:n]


def tested(p, compat):
    """What the newest SolidCraft made of the plugin's latest release (scripts/compat.py), as the
    card's line and its tooltip, or None. Only good news is shown: a command that needs something
    picked first can't run on its own, which says nothing about whether it works."""
    c = compat.get(p["slug"])
    rel = p.get("release") or {}
    if not c or not c.get("loads") or c.get("release") != rel.get("tag"):
        return None
    v, when = c["solidcraft"], c["tested"]
    if c.get("entries", 0) > 0 and len(c.get("ran", [])) == c["entries"]:
        return {"label": f"✓ Runs in SolidCraft {v}", "date": when,
                "title": f"Tested {when} on Linux: SolidCraft {v} loaded this release and ran every command with its default values."}
    why = ("It asks for file access or sensitive commands, so it wasn't run." if c.get("skipped")
           else "Its commands need something picked or set up first, so they weren't all run.")
    return {"label": f"✓ Loads in SolidCraft {v}", "date": when,
            "title": f"Tested {when} on Linux: SolidCraft {v} loaded this release. {why}"}


QUALITY = "https://github.com/tharje/solidcraft-plugins#quality-checked"
# What a quality check looks at, in order: verified.json's "criteria" uses these keys.
CRITERIA = [
    ("installs", "Installs and loads in the newest SolidCraft"),
    ("runs", "Every command runs, with its defaults and with real settings"),
    ("valid", "Makes whole, valid bodies that can be edited"),
    ("permissions", "Asks for no more than it needs, and never for the network"),
    ("release", "Open source licence, a README, and a release with its zip"),
    ("issues", "Takes issues, for questions and bugs"),
]
RESULT = {"passed": "Passed", "not passed": "Not passed", "not checkable": "Could not be checked"}


def checked(p, verified):
    """The plugin's quality check (verified.json), or None: the badge's text, its tooltip and the
    report. A check is for one version; after a newer release the badge names the version checked.
    A check that did not pass is shown too, so anyone can read what failed."""
    v = next((x for x in verified if x["repo"].lower() == p["repo"].lower() and x["id"] == p.get("id")), None)
    if not v:
        return None
    current = v["version"] == p.get("version")
    passed = v.get("result", "passed") == "passed"
    q = {"current": current, "passed": passed, "report": f"{SITE}plugins/{p['slug']}/#quality", "date": v["date"],
         "version": v["version"], "result": v.get("result", "passed"), "data": v}
    if passed:
        q["label"] = "✓ Quality checked" if current else f"✓ Quality checked (v{v['version']})"
        q["title"] = (f"Version {v['version']} was checked {v['date']} by {v['by']} in SolidCraft {v['solidcraft']}: it installs, "
                      "every command runs with its defaults and with real settings, it makes valid bodies you can edit, "
                      "and it asks for no more than it needs." + ("" if current else " The newer version has not been checked yet."))
    else:
        q["label"] = ("Quality check: not passed" if v["result"] == "not passed" else "Quality check: could not be checked") + f" (v{v['version']})"
        q["title"] = f"Version {v['version']}, checked {v['date']} in SolidCraft {v['solidcraft']}: {v.get('summary', '')} Click for what was tested."
    return q


def slugs(plugins):
    """A short, stable address per plugin: its manifest id, with the owner added when two collide."""
    seen = set()
    for p in plugins:
        base = re.sub(r"[^a-z0-9]+", "-", (p.get("id") or p["repo"].split("/")[1]).lower()).strip("-")
        slug = base if base not in seen else f"{base}-{p['owner'].lower()}"
        seen.add(slug)
        p["slug"] = slug


def qc_badge(p, page=False):
    """The quality check badge, on a card or (bigger) on a plugin's page."""
    q = p.get("checked")
    if not q:
        return ""
    cls = "qc" + ("" if q["passed"] else " fail") + ("" if q["current"] or not q["passed"] else " old") + (" big" if page else "")
    href = "#quality" if page else q["report"]
    return f'\n      <a class="{cls}" href="{e(href)}" title="{e(q["title"])}">{e(q["label"])}</a>'


def card(p, prefix=""):
    """The same markup as the card template in index.html."""
    pic = (f'<img src="{e(p["image"])}" alt="{e(p["name"])}: SolidCraft plugin" loading="lazy">'
           if p.get("image") else "")
    first = e((p["name"].strip() or "?")[0].upper())
    zip_ = p.get("release") and p["release"].get("zip")
    download = (f'<a class="btn primary zip" href="{e(zip_)}">Download .zip</a>' if zip_
                else f'<a class="btn primary zip" href="{e(p["example"])}" target="_blank" rel="noopener">Plugin guide</a>' if p.get("example")
                else '<a class="btn primary zip disabled">No release yet</a>')
    chips = "".join(f"<span>{e(t)}</span>" for t in p.get("topics", [])[:5])
    entries = ("Menu: " + " · ".join(e(x) for x in p["entries"])) if p.get("entries") else ""
    page = f'{prefix}plugins/{p["slug"]}/'
    icon = f'<img class="icon" src="{prefix}{e(p["icon"])}" alt="" loading="lazy">' if p.get("icon") else ""
    return f'''<article class="card">
    <a class="pic{"" if p.get("image") else " empty"}" href="{page}">{pic}<span class="ph">{first}</span></a>
    <div class="body">
      <p class="cat">{e(p.get("category") or "")}</p>
      <h3>{icon}<a class="name" href="{page}">{e(p["name"])}</a> <span class="ver">{"v" + e(p["version"]) if p.get("version") else ""}</span></h3>
      <a class="by" href="https://github.com/{e(p["owner"])}" target="_blank" rel="noopener"><img src="{e(p["avatar"])}&amp;s=40" alt="" loading="lazy"><span>{e(p["owner"])}</span></a>{qc_badge(p)}
      <p class="desc">{e(p["description"])}</p>
      <p class="entries">{entries}</p>{f"""
      <p class="note">{e(p["note"])}</p>""" if p.get("note") else ""}
      <div class="chips">{chips}</div>
      <p class="tested"{f' title="{e(p["tested"]["title"])}"' if p.get("tested") else " hidden"}>{e(p["tested"]["label"]) if p.get("tested") else ""}</p>
      <p class="asks"{f' title="{e(p["asks"]["title"])}"' if p.get("asks") else " hidden"}>{e(p["asks"]["label"]) if p.get("asks") else ""}</p>
      <div class="meta">
        <span class="stars" title="GitHub stars">★ {p["stars"]}</span>
        <span class="dl" title="Downloads of all releases">⬇ {p["downloads"]}</span>
        {report_menu(p)}
      </div>
      <div class="actions">
        {download}
        <a class="btn gh" href="{e(p["url"])}" target="_blank" rel="noopener">GitHub</a>{f"""
        <a class="btn ws" href="{e(p["workshop"])}" target="_blank" rel="noopener" title="Its page on the SolidCraft Workshop: Open in SolidCraft installs it">Workshop</a>""" if p.get("workshop") else ""}
      </div>
    </div>
  </article>'''


def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def app(p):
    """schema.org SoftwareApplication for one plugin."""
    a = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": p["name"],
        "description": p["description"],
        "url": SITE + f"plugins/{p['slug']}/",
        "applicationCategory": "DesignApplication",
        "applicationSubCategory": "SolidCraft plugin",
        "operatingSystem": "Windows, macOS, Linux",
        "author": {"@type": "Person", "name": p["owner"], "url": f"https://github.com/{p['owner']}"},
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "sameAs": p["url"],
    }
    if p.get("version"):
        a["softwareVersion"] = p["version"]
    if p.get("image"):
        a["image"] = p["image"]
    if p.get("release") and p["release"].get("zip"):
        a["downloadUrl"] = p["release"]["zip"]
    if p.get("license") and p["license"] != "NOASSERTION":
        a["license"] = f"https://spdx.org/licenses/{p['license']}"
    if p.get("updated"):
        a["dateModified"] = p["updated"]
    return a


def short(text, n=155):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


LINK = re.compile(r"!?\[([^\]]*)\]\(\s*<?([^)\s>]+)>?[^)]*\)|(https?://[^\s<>()]+[^\s<>().,:;!?'\"])|`([^`]+)`|\*\*(.+?)\*\*|__(.+?)__")


def inline(text):
    """One line of Markdown as HTML: links (http and https only), code and bold. Pictures are left
    out, everything else is shown as text."""
    out, i = [], 0
    for m in LINK.finditer(text):
        out.append(e(text[i:m.start()]))
        i = m.end()
        label, url, bare, code, bold = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5) or m.group(6)
        if m.group(0).startswith("!"):
            continue
        if url is not None:
            out.append(f'<a href="{e(url)}" rel="nofollow noopener">{inline(label)}</a>' if url.startswith(("http://", "https://")) else inline(label))
        elif bare:
            # GitHub's own short form for pull requests and issues: #34
            short_ = re.fullmatch(r"https://github\.com/[^/]+/[^/]+/(?:pull|issues)/(\d+)", bare)
            out.append(f'<a href="{e(bare)}" rel="nofollow noopener">{"#" + short_.group(1) if short_ else e(bare)}</a>')
        elif code is not None:
            out.append(f"<code>{e(code)}</code>")
        else:
            out.append(f"<b>{inline(bold)}</b>")
    out.append(e(text[i:]))
    return "".join(out)


def notes_html(md, limit=1800):
    """The start of a release's notes (Markdown) as HTML: headings, lists and paragraphs. Returns the
    HTML and whether some was left out."""
    blocks, para, items, size, cut = [], [], [], 0, False

    def flush():
        if para:
            blocks.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()
        if items:
            blocks.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            items.clear()

    lines = md.replace("\r", "").split("\n")
    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or re.match(r"\s*(<!--|<img|!\[)", line):
            continue
        size += len(line)
        if size > limit:
            cut = True
            break
        t = line.strip()
        h = re.match(r"(#{1,6})\s+(.*?)\s*#*$", t)
        li = re.match(r"(?:[-*+]|\d+[.)])\s+(.*)", t)
        if not t:
            flush()
        elif h:
            flush()
            blocks.append(f"<h3>{inline(h.group(2))}</h3>")
        elif li:
            if para:
                flush()
            items.append(li.group(1))
        elif items and line[:1] in " \t":
            items[-1] += " " + t
        else:
            if items:
                flush()
            para.append(t)
    flush()
    if cut and blocks and blocks[-1].startswith("<h3>"):  # a heading with nothing under it
        blocks.pop()
    return "\n".join(blocks), cut


def plugin_page(p, others):
    url = SITE + f"plugins/{p['slug']}/"
    title = f"{p['name']}: SolidCraft plugin by {p['owner']}"
    desc = short(f"{p['description'].rstrip('.')}. A free plugin for SolidCraft CAD: download the zip and install it from Plugins › Install plugin.")
    rel = p.get("release") or {}
    facts = [f"<dt>Author</dt><dd><a href=\"https://github.com/{e(p['owner'])}\">{e(p['owner'])}</a></dd>"]
    if p.get("category"):
        facts.append(f"<dt>Category</dt><dd><a href=\"../../?category={e(urllib.parse.quote(p['category']))}\">{e(p['category'])}</a></dd>")
    if p.get("version"):
        facts.append(f"<dt>Version</dt><dd>{e(p['version'])}</dd>")
    if rel.get("tag"):
        facts.append(f"<dt>Latest release</dt><dd><a href=\"{e(rel['url'])}\">{e(rel['tag'])}</a>"
                     + (f" ({e(rel['date'][:10])})" if rel.get("date") else "") + "</dd>")
    if p.get("license") and p["license"] != "NOASSERTION":
        facts.append(f"<dt>Licence</dt><dd>{e(p['license'])}</dd>")
    facts.append(f"<dt>GitHub</dt><dd>★ {p['stars']} stars · ⬇ {p['downloads']} downloads</dd>")
    if p.get("asks"):
        facts.append(f"<dt>Asks for</dt><dd title=\"{e(p['asks']['title'])}\">{e(p['asks']['label'][len('Asks for: '):])}</dd>")
    if p.get("checked"):
        q = p["checked"]
        verdict = {"passed": "Passed", "not passed": "Not passed", "not checkable": "Could not be checked"}.get(q["result"], q["result"])
        facts.append(f"<dt>Quality check</dt><dd title=\"{e(q['title'])}\"><a href=\"#quality\">{verdict}, v{e(q['version'])} ({e(q['date'])})</a></dd>")
    if p.get("tested"):
        t = p["tested"]
        facts.append(f"<dt>Tested</dt><dd title=\"{e(t['title'])}\">{e(t['label'])} ({e(t['date'])})</dd>")
    entries = "".join(f"<li>{e(x)}</li>" for x in p.get("entries", []))
    tags = "".join(f"<span>{e(t)}</span>" for t in p.get("topics", []))
    zip_ = rel.get("zip")
    download = (f'<a class="btn primary" href="{e(zip_)}">Download .zip</a>' if zip_
                else f'<a class="btn primary" href="{e(p["example"])}">Plugin guide</a>' if p.get("example")
                else '<a class="btn primary disabled">No release yet</a>')
    pic = (f'<img class="hero-pic" src="{e(p["image"])}" alt="{e(p["name"])} in SolidCraft">'
           if p.get("image") else "")
    more = "".join(f'<li><a href="../{o["slug"]}/">{e(o["name"])}</a> <span>{e(short(o["description"], 90))}</span></li>'
                   for o in others)
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "SolidCraft Plugins", "item": SITE},
        {"@type": "ListItem", "position": 2, "name": p["name"], "item": url}]}
    image = p.get("image") or SITE + "social.png"
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<link rel="icon" href="../../favicon.svg" type="image/svg+xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="SolidCraft Plugins">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{e(image)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="../../style.css">
<script data-goatcounter="https://tharje.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
{ld(app(p))}
{ld(crumbs)}
</head>
<body>
<header class="top">
  <div class="wrap">
    <a class="brand" href="../../">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 2v4H7a1 1 0 0 0-1 1v4a6 6 0 0 0 5 5.9V22h2v-5.1A6 6 0 0 0 18 11V7a1 1 0 0 0-1-1h-2V2h-2v4h-2V2z"/></svg>
      <span>SolidCraft Plugins</span>
    </a>
    <nav>
      <a href="../../">All plugins</a>
      <a href="../../quality/">Quality checks</a>
      <a href="../../#install">Install</a>
      <a href="https://github.com/tangency-labs/solidcraft">SolidCraft</a>
    </nav>
  </div>
</header>

<main class="wrap page">
  <p class="crumbs"><a href="../../">SolidCraft Plugins</a> › {e(p["name"])}</p>
  <h1>{f'<img class="icon" src="../../{e(p["icon"])}" alt="">' if p.get("icon") else ""}{e(p["name"])} <span class="ver">{"v" + e(p["version"]) if p.get("version") else ""}</span></h1>
  {qc_badge(p, page=True).strip()}
  <p class="lead">{e(p["description"])}</p>{f"""
  <p class="note">{e(p["note"])}</p>""" if p.get("note") else ""}
  <div class="actions">
    {download}
    <a class="btn gh" href="{e(p["url"])}">Source on GitHub</a>{f"""
    <a class="btn ws" href="{e(p["workshop"])}">On the SolidCraft Workshop</a>""" if p.get("workshop") else ""}
  </div>
  {pic}
  <div class="cols">
    <section>
      <h2>What it adds to SolidCraft</h2>
      {f"<ul>{entries}</ul>" if entries else "<p>See the plugin's README on GitHub.</p>"}
      <h2>Install {e(p["name"])}</h2>
      <ol>
        <li>{"Download the zip above (from release " + e(rel["tag"]) + ")." if zip_ else f'Build it as SolidCraft\'s <a href="{e(p["example"])}">plugin guide</a> describes.' if p.get("example") else "Build or download the plugin as described in its README on GitHub."}</li>
        <li>In SolidCraft: <b>Plugins › Install plugin…</b> and pick the zip.</li>
        <li>Run it from the <b>Plugins</b> menu, or its button in the ribbon (SolidCraft 0.42 and later).</li>
      </ol>{f"""
      <p>It is on the <a href="{e(p["workshop"])}">SolidCraft Workshop</a> too: its <b>Open in SolidCraft</b> button installs it, after SolidCraft shows what it asks for.</p>""" if p.get("workshop") else ""}
      <p>Questions and bug reports go to the plugin's author, in the
        <a href="{e(p["url"])}/issues">issues on GitHub</a>. If it crashes SolidCraft, harms a design
        or looks unsafe, please also <a href="{e(report_url(p))}">report it to this list</a>, so others can be warned.</p>
    </section>
    <aside>
      <dl class="facts">{"".join(facts)}</dl>
      {f'<div class="chips">{tags}</div>' if tags else ""}
    </aside>
  </div>
  {quality_section(p)}
  {notes_section(p)}
  <section class="more">
    <h2>Similar SolidCraft plugins</h2>
    <ul>{more}</ul>
    <p><a href="../../">All SolidCraft plugins ›</a></p>
  </section>
</main>

<footer class="wrap foot">
  <span>A community list of <a href="https://github.com/tangency-labs/solidcraft">SolidCraft</a> plugins, not made by Tangency Labs. Each plugin belongs to its author.
    <a href="https://github.com/tharje/solidcraft-plugins">This list on GitHub</a>.</span>
</footer>
</body>
</html>
'''


def quality_section(p):
    """What the quality check tested and found: the criteria ticked off, the runs, and how a plugin
    that did not pass could."""
    q = p.get("checked")
    if not q:
        return ""
    v = q["data"]
    crit = v.get("criteria", {})
    rows = []
    for key, text in CRITERIA:
        c = crit.get(key)
        if c is None:
            continue
        ok = c.get("ok")
        mark = "✓" if ok else "✗" if ok is False else "–"
        cls = "yes" if ok else "no" if ok is False else "na"
        note = f' <span class="why">{inline(c["note"])}</span>' if c.get("note") else ""
        rows.append(f'<li class="{cls}"><b>{mark}</b> {e(text)}{note}</li>')
    runs = "".join(
        f'<tr class="{"yes" if r.get("ok") else "no" if r.get("ok") is False else "na"}"><td>{e(r.get("entry", ""))}</td>'
        f'<td>{inline(r["settings"])}</td><td>{e(r.get("time", ""))}</td><td>{inline(r["result"])}</td></tr>'
        for r in v.get("runs", []))
    table = (f'<table class="runs"><thead><tr><th>Command</th><th>Settings</th><th>Time</th><th>Result</th></tr></thead>'
             f'<tbody>{runs}</tbody></table>') if runs else ""
    extra = "".join(f"<p>{inline(t)}</p>" for t in v.get("notes", []))
    fix = f'<h3>How it could pass</h3><p>{inline(v["fix"])}</p>' if v.get("fix") else ""
    older = "" if q["current"] else f'<p class="note">This check is for version {e(v["version"])}; version {e(p.get("version") or "")} has not been checked yet.</p>'
    return f'''<section class="quality" id="quality">
    <h2>Quality check: {RESULT.get(q["result"], q["result"]).lower()}</h2>
    <p class="meta-line">Version {e(v["version"])}, checked {e(v["date"])} by {e(v["by"])} in SolidCraft {e(v["solidcraft"])}{" on " + e(v["machine"]) if v.get("machine") else ""}.
      <a href="../../quality/">What a quality check is ›</a></p>
    {older}
    {f"<p>{inline(v['summary'])}</p>" if v.get("summary") and not q["passed"] else ""}
    <ul class="criteria">{"".join(rows)}</ul>
    {extra}
    {table}
    {fix}
  </section>'''


def quality_page(plugins):
    """quality/index.html: what a quality check is, and every check so far."""
    checked = sorted((p for p in plugins if p.get("checked")), key=lambda p: (not p["checked"]["passed"], p["name"].lower()))
    rows = "".join(
        f'<tr class="{"yes" if p["checked"]["passed"] else "na" if p["checked"]["result"] == "not checkable" else "no"}"><td><a href="../plugins/{p["slug"]}/#quality">{e(p["name"])}</a></td>'
        f'<td>{e(p["checked"]["version"])}</td><td>{e(p["checked"]["date"])}</td>'
        f'<td>{RESULT.get(p["checked"]["result"], "")}</td><td>{inline(p["checked"]["data"].get("summary", ""))}</td></tr>'
        for p in checked)
    crit = "".join(f"<li>{e(t)}</li>" for _, t in CRITERIA)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quality checks: SolidCraft plugins tested by hand</title>
<meta name="description" content="Which SolidCraft plugins were tested by hand, what was tested, and what passed or failed.">
<link rel="canonical" href="{SITE}quality/">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="../style.css">
<script data-goatcounter="https://tharje.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
</head>
<body>
<header class="top">
  <div class="wrap">
    <a class="brand" href="../">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 2v4H7a1 1 0 0 0-1 1v4a6 6 0 0 0 5 5.9V22h2v-5.1A6 6 0 0 0 18 11V7a1 1 0 0 0-1-1h-2V2h-2v4h-2V2z"/></svg>
      <span>SolidCraft Plugins</span>
    </a>
    <nav>
      <a href="../">All plugins</a>
      <a href="./">Quality checks</a>
      <a href="https://github.com/tangency-labs/solidcraft">SolidCraft</a>
    </nav>
  </div>
</header>
<main class="wrap page">
  <p class="crumbs"><a href="../">SolidCraft Plugins</a> › Quality checks</p>
  <h1>Quality checks</h1>
  <p class="lead">Some plugins on this list have been tested by hand, one version at a time. A plugin that
    passes gets the green <span class="qc">✓ Quality checked</span> badge. One that doesn't is listed too,
    with what failed, so you can judge for yourself, and its author can see what to fix.</p>
  <div class="cols">
    <section>
      <h2>What is tested</h2>
      <p>A plugin passes when all of these hold for the version checked:</p>
      <ol>{crit}</ol>
      <h2>How</h2>
      <p>The plugin's release zip is installed in the newest SolidCraft. Every command is run with its
        default values, and then with settings someone would really use: other sizes, the choices in
        its dialog, the largest and smallest values it allows, and on parts it is meant to work on.
        Each run is timed, and the bodies it makes are measured: they must be closed solids. Runs go
        through SolidCraft's own <code>solidcraft-cli plugin test</code> and the desktop app.</p>
      <p>A plugin's page shows the result: each point ticked off or not, and a table of the runs with
        their settings, times and results. A check is for one version: after a newer release the
        badge turns grey until that one is checked too.</p>
      <h2>Ask for a check</h2>
      <p>Anyone can ask, authors too: use the <a href="https://github.com/tharje/solidcraft-plugins/issues/new?template=quality-check.yml">Request a quality check</a> form.</p>
    </section>
  </div>
  <h2>Checked so far</h2>
  <table class="runs overview"><thead><tr><th>Plugin</th><th>Version</th><th>Checked</th><th>Result</th><th>Summary</th></tr></thead>
    <tbody>{rows}</tbody></table>
</main>
<footer class="wrap foot">
  <span>A community list of <a href="https://github.com/tangency-labs/solidcraft">SolidCraft</a> plugins, not made by Tangency Labs. Each plugin belongs to its author.
    <a href="https://github.com/tharje/solidcraft-plugins">This list on GitHub</a>.</span>
</footer>
</body>
</html>
'''


def notes_section(p):
    rel = p.get("release") or {}
    body, cut = notes_html(rel.get("notes") or "")
    if not body:
        return ""
    when = f" ({e(rel['date'][:10])})" if rel.get("date") else ""
    more = (f'<p><a href="{e(rel["url"])}">Read all of it on GitHub ›</a></p>' if cut
            else f'<p><a href="{e(rel["url"])}">The release on GitHub ›</a></p>')
    return f'''<section class="notes">
    <h2>What's new in {e(rel["tag"])}{when}</h2>
    {body}
    {more}
  </section>'''


def replace(text, name, new):
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    i, j = text.index(start) + len(start), text.index(end)
    return text[:i] + "\n" + new + "\n" + text[j:]


def icons(plugins):
    """icons/<slug>.svg from the icon text update.py fetched; the text itself isn't kept in the data.
    Rebuilt from data/plugins.json alone (no icon text in it), the icons already written are kept."""
    out = os.path.join(ROOT, "icons")
    os.makedirs(out, exist_ok=True)
    keep = set()
    for p in plugins:
        fetched = "icon_svg" in p
        svg = p.pop("icon_svg", None)
        name = f"{p['slug']}.svg"
        if svg:
            with open(os.path.join(out, name), "w") as f:
                f.write(svg)
        if svg or (not fetched and p.get("icon") and os.path.exists(os.path.join(out, name))):
            p["icon"] = f"icons/{name}"
            keep.add(name)
        else:
            p.pop("icon", None)
    for old in os.listdir(out):
        if old not in keep:
            os.remove(os.path.join(out, old))


def build(plugins):
    slugs(plugins)
    icons(plugins)
    try:
        with open(os.path.join(ROOT, "data", "compat.json")) as f:
            compat = json.load(f).get("plugins", {})
    except (OSError, ValueError):
        compat = {}
    try:
        with open(os.path.join(ROOT, "verified.json")) as f:
            verified = json.load(f).get("checked", [])
    except (OSError, ValueError):
        verified = []
    for p in plugins:
        p["checked"] = checked(p, verified)
        p["tested"] = tested(p, compat)
        p["asks"] = asks(p)
        p["report"] = report_url(p)
        p["report_author"] = author_report_url(p)
    path = os.path.join(ROOT, "index.html")
    with open(path) as f:
        page = f.read()
    page = replace(page, "plugins", "\n".join(card(p) for p in plugins))
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": "SolidCraft plugins",
             "numberOfItems": len(plugins), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "url": SITE + f"plugins/{p['slug']}/", "name": p["name"]}
                 for i, p in enumerate(plugins)]}
    page = replace(page, "jsonld", ld(items))
    page = re.sub(r"(<p id=\"count\" class=\"count\">)[^<]*(</p>)", rf"\g<1>{len(plugins)} plugins\g<2>", page)
    with open(path, "w") as f:
        f.write(page)

    out = os.path.join(ROOT, "plugins")
    keep = set()
    for i, p in enumerate(plugins):
        others = similar(p, plugins, i)
        d = os.path.join(out, p["slug"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write(plugin_page(p, others))
        keep.add(p["slug"])
    for old in os.listdir(out):  # plugins that left the list
        if old not in keep:
            os.remove(os.path.join(out, old, "index.html"))
            os.rmdir(os.path.join(out, old))

    os.makedirs(os.path.join(ROOT, "quality"), exist_ok=True)
    with open(os.path.join(ROOT, "quality", "index.html"), "w") as f:
        f.write(quality_page(plugins))

    newest = max((p.get("updated") or "")[:10] for p in plugins)
    urls = [(SITE, newest), (SITE + "quality/", newest)] + [(SITE + f"plugins/{p['slug']}/", (p.get("updated") or "")[:10]) for p in plugins]
    with open(os.path.join(ROOT, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u, mod in urls:
            f.write(f"  <url><loc>{u}</loc>" + (f"<lastmod>{mod}</lastmod>" if mod else "") + "</url>\n")
        f.write("</urlset>\n")


if __name__ == "__main__":
    with open(os.path.join(ROOT, "data", "plugins.json")) as f:
        data = json.load(f)
    build(data["plugins"])
    with open(os.path.join(ROOT, "data", "plugins.json"), "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
