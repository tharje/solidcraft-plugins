// SolidCraft Plugins: cards from data/plugins.json, with search, category filter and sorting.
const $ = (s) => document.querySelector(s);
let plugins = [];
let category = new URLSearchParams(location.search).get("category");

function ago(iso) {
  if (!iso) return "";
  const days = Math.floor((Date.now() - new Date(iso)) / 86400000);
  if (days < 1) return "updated today";
  if (days < 2) return "updated yesterday";
  if (days < 31) return `updated ${days} days ago`;
  const months = Math.floor(days / 30.4);
  if (months < 12) return `updated ${months} month${months > 1 ? "s" : ""} ago`;
  return `updated ${Math.floor(months / 12)} year${months >= 24 ? "s" : ""} ago`;
}

function text(p) {
  return [p.name, p.description, p.owner, p.repo, p.category, ...(p.entries || []), ...(p.topics || [])].join(" ").toLowerCase();
}

function message(s) {
  const e = document.createElement("p");
  e.className = "empty-list";
  e.textContent = s;
  return e;
}

function card(p) {
  const t = $("#card").content.cloneNode(true);
  const page = `plugins/${p.slug}/`;
  const pic = t.querySelector(".pic");
  pic.href = page;
  pic.querySelector(".ph").textContent = (p.name || "?").trim()[0].toUpperCase();
  const img = pic.querySelector("img");
  if (p.image) {
    img.src = p.image;
    img.alt = `${p.name}: SolidCraft plugin`;
    img.onerror = () => pic.classList.add("empty");
  } else {
    pic.classList.add("empty");
  }
  t.querySelector(".cat").textContent = p.category || "";
  if (p.icon) {
    const i = document.createElement("img");
    i.className = "icon";
    i.src = p.icon;
    i.alt = "";
    t.querySelector("h3").prepend(i);
  }
  const name = t.querySelector(".name");
  name.textContent = p.name;
  name.href = page;
  t.querySelector(".ver").textContent = p.version ? `v${p.version}` : "";
  const by = t.querySelector(".by");
  by.href = `https://github.com/${p.owner}`;
  by.querySelector("img").src = `${p.avatar}&s=40`;
  by.querySelector("span").textContent = p.owner;
  t.querySelector(".desc").textContent = p.description;
  t.querySelector(".entries").textContent = p.entries && p.entries.length ? "Menu: " + p.entries.join(" · ") : "";
  if (p.note) {
    const n = document.createElement("p");
    n.className = "note";
    n.textContent = p.note;
    t.querySelector(".entries").after(n);
  }
  const chips = t.querySelector(".chips");
  for (const x of (p.topics || []).slice(0, 5)) {
    const s = document.createElement("span");
    s.textContent = x;
    chips.append(s);
  }
  if (p.tested) {
    const el = t.querySelector(".tested");
    el.hidden = false;
    el.textContent = p.tested.label;
    el.title = p.tested.title;
  }
  t.querySelector(".report").href = p.report;
  t.querySelector(".stars").textContent = `★ ${p.stars}`;
  t.querySelector(".dl").textContent = `⬇ ${p.downloads}`;
  t.querySelector(".upd").textContent = ago(p.updated);
  const zip = t.querySelector(".zip");
  if (p.release && p.release.zip) {
    zip.href = p.release.zip;
    zip.title = `${p.release.tag}: the zip from the latest release`;
  } else {
    zip.classList.add("disabled");
    zip.textContent = "No release yet";
  }
  t.querySelector(".gh").href = p.url;
  return t;
}

function show() {
  const q = $("#q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const cmp = {
    stars: (a, b) => b.stars - a.stars || b.downloads - a.downloads,
    downloads: (a, b) => b.downloads - a.downloads,
    updated: (a, b) => (b.updated || "").localeCompare(a.updated || ""),
    created: (a, b) => (b.created || "").localeCompare(a.created || ""),
    name: (a, b) => a.name.localeCompare(b.name),
  }[$("#sort").value];
  const list = plugins
    .filter((p) => q.every((w) => text(p).includes(w)) && (!category || p.category === category))
    .sort(cmp);
  $("#list").replaceChildren(...(list.length ? list.map(card) : [message("No plugins match.")]));
  $("#count").textContent = `${list.length} of ${plugins.length} plugins`;
}

// The categories, in the order update.py gives them (the order plugins first show up in), largest first.
function categories() {
  const n = {};
  for (const p of plugins) if (p.category) n[p.category] = (n[p.category] || 0) + 1;
  if (category && !n[category]) category = null;
  const box = $("#tags");
  for (const x of [null, ...Object.keys(n).sort((a, b) => n[b] - n[a] || a.localeCompare(b))]) {
    const b = document.createElement("button");
    b.className = "tag" + (x === category ? " on" : "");
    b.textContent = x ? `${x} (${n[x]})` : "All";
    b.onclick = () => {
      category = x;
      box.querySelectorAll(".tag").forEach((e) => e.classList.toggle("on", e === b));
      const url = new URL(location.href);
      if (x) url.searchParams.set("category", x); else url.searchParams.delete("category");
      history.replaceState(null, "", url);
      show();
    };
    box.append(b);
  }
}

fetch("data/plugins.json")
  .then((r) => r.json())
  .then((d) => {
    plugins = d.plugins;
    $("#updated").textContent = `List updated ${new Date(d.generated).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}`;
    categories();
    show();
  })
  .catch(() => $("#list").replaceChildren(message("Could not load the plugin list.")));
$("#q").addEventListener("input", show);
$("#sort").addEventListener("change", show);
