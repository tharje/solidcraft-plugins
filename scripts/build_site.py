#!/usr/bin/env python3
"""Build the static parts of the site from data/plugins.json, so search engines see every plugin.

- index.html: the plugin cards between the plugins markers (app.js redraws them for search and
  sorting) and the ItemList structured data between the jsonld markers.
- plugins/<slug>/index.html: one page per plugin.
- sitemap.xml.
Nothing here depends on today's date, so the files only change when a plugin does.
"""
import html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://tharje.github.io/solidcraft-plugins/"
e = html.escape


def slugs(plugins):
    """A short, stable address per plugin: its manifest id, with the owner added when two collide."""
    seen = set()
    for p in plugins:
        base = re.sub(r"[^a-z0-9]+", "-", (p.get("id") or p["repo"].split("/")[1]).lower()).strip("-")
        slug = base if base not in seen else f"{base}-{p['owner'].lower()}"
        seen.add(slug)
        p["slug"] = slug


def card(p, prefix=""):
    """The same markup as the card template in index.html."""
    pic = (f'<img src="{e(p["image"])}" alt="{e(p["name"])}: SolidCraft plugin" loading="lazy">'
           if p.get("image") else "")
    first = e((p["name"].strip() or "?")[0].upper())
    zip_ = p.get("release") and p["release"].get("zip")
    download = (f'<a class="btn primary zip" href="{e(zip_)}">Download .zip</a>' if zip_
                else '<a class="btn primary zip disabled">No release yet</a>')
    chips = "".join(f"<span>{e(t)}</span>" for t in p.get("topics", [])[:5])
    entries = ("Menu: " + " · ".join(e(x) for x in p["entries"])) if p.get("entries") else ""
    page = f'{prefix}plugins/{p["slug"]}/'
    return f'''<article class="card">
    <a class="pic{"" if p.get("image") else " empty"}" href="{page}">{pic}<span class="ph">{first}</span></a>
    <div class="body">
      <h3><a class="name" href="{page}">{e(p["name"])}</a> <span class="ver">{"v" + e(p["version"]) if p.get("version") else ""}</span></h3>
      <a class="by" href="https://github.com/{e(p["owner"])}" target="_blank" rel="noopener"><img src="{e(p["avatar"])}&amp;s=40" alt="" loading="lazy"><span>{e(p["owner"])}</span></a>
      <p class="desc">{e(p["description"])}</p>
      <p class="entries">{entries}</p>{f"""
      <p class="note">{e(p["note"])}</p>""" if p.get("note") else ""}
      <div class="chips">{chips}</div>
      <div class="meta">
        <span class="stars" title="GitHub stars">★ {p["stars"]}</span>
        <span class="dl" title="Downloads of all releases">⬇ {p["downloads"]}</span>
      </div>
      <div class="actions">
        {download}
        <a class="btn gh" href="{e(p["url"])}" target="_blank" rel="noopener">GitHub</a>
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


def plugin_page(p, others):
    url = SITE + f"plugins/{p['slug']}/"
    title = f"{p['name']}: SolidCraft plugin by {p['owner']}"
    desc = short(f"{p['description'].rstrip('.')}. A free plugin for SolidCraft CAD: download the zip and install it from Plugins › Install plugin.")
    rel = p.get("release") or {}
    facts = [f"<dt>Author</dt><dd><a href=\"https://github.com/{e(p['owner'])}\">{e(p['owner'])}</a></dd>"]
    if p.get("version"):
        facts.append(f"<dt>Version</dt><dd>{e(p['version'])}</dd>")
    if rel.get("tag"):
        facts.append(f"<dt>Latest release</dt><dd><a href=\"{e(rel['url'])}\">{e(rel['tag'])}</a>"
                     + (f" ({e(rel['date'][:10])})" if rel.get("date") else "") + "</dd>")
    if p.get("license") and p["license"] != "NOASSERTION":
        facts.append(f"<dt>Licence</dt><dd>{e(p['license'])}</dd>")
    facts.append(f"<dt>GitHub</dt><dd>★ {p['stars']} stars · ⬇ {p['downloads']} downloads</dd>")
    entries = "".join(f"<li>{e(x)}</li>" for x in p.get("entries", []))
    tags = "".join(f"<span>{e(t)}</span>" for t in p.get("topics", []))
    zip_ = rel.get("zip")
    download = (f'<a class="btn primary" href="{e(zip_)}">Download .zip</a>' if zip_
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
      <a href="../../#install">Install</a>
      <a href="https://github.com/tangency-labs/solidcraft">SolidCraft</a>
    </nav>
  </div>
</header>

<main class="wrap page">
  <p class="crumbs"><a href="../../">SolidCraft Plugins</a> › {e(p["name"])}</p>
  <h1>{e(p["name"])} <span class="ver">{"v" + e(p["version"]) if p.get("version") else ""}</span></h1>
  <p class="lead">{e(p["description"])}</p>{f"""
  <p class="note">{e(p["note"])}</p>""" if p.get("note") else ""}
  <div class="actions">
    {download}
    <a class="btn gh" href="{e(p["url"])}">Source on GitHub</a>
  </div>
  {pic}
  <div class="cols">
    <section>
      <h2>What it adds to SolidCraft</h2>
      {f"<ul>{entries}</ul>" if entries else "<p>See the plugin's README on GitHub.</p>"}
      <h2>Install {e(p["name"])}</h2>
      <ol>
        <li>{"Download the zip above (from release " + e(rel["tag"]) + ")." if zip_ else "Build or download the plugin as described in its README on GitHub."}</li>
        <li>In SolidCraft: <b>Plugins › Install plugin…</b> and pick the zip.</li>
        <li>Run it from the <b>Plugins</b> menu, or its button in the ribbon (SolidCraft 0.42 and later).</li>
      </ol>
      <p>Questions and bug reports go to the plugin's author, in the
        <a href="{e(p["url"])}/issues">issues on GitHub</a>.</p>
    </section>
    <aside>
      <dl class="facts">{"".join(facts)}</dl>
      {f'<div class="chips">{tags}</div>' if tags else ""}
    </aside>
  </div>
  <section class="more">
    <h2>More SolidCraft plugins</h2>
    <ul>{more}</ul>
    <p><a href="../../">All SolidCraft plugins ›</a></p>
  </section>
</main>

<footer class="wrap foot">
  <span>A community list of <a href="https://github.com/tangency-labs/solidcraft">SolidCraft</a> plugins, not made by Tangency Labs. Each plugin belongs to its author.</span>
</footer>
</body>
</html>
'''


def replace(text, name, new):
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    i, j = text.index(start) + len(start), text.index(end)
    return text[:i] + "\n" + new + "\n" + text[j:]


def build(plugins):
    slugs(plugins)
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
        others = [o for o in plugins if o is not p]
        others = (others[i:] + others[:i])[:6]  # a different handful on each page
        d = os.path.join(out, p["slug"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write(plugin_page(p, others))
        keep.add(p["slug"])
    for old in os.listdir(out):  # plugins that left the list
        if old not in keep:
            os.remove(os.path.join(out, old, "index.html"))
            os.rmdir(os.path.join(out, old))

    newest = max((p.get("updated") or "")[:10] for p in plugins)
    urls = [(SITE, newest)] + [(SITE + f"plugins/{p['slug']}/", (p.get("updated") or "")[:10]) for p in plugins]
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
