# SolidCraft Plugins

A list of community plugins for the [SolidCraft](https://github.com/tangency-labs/solidcraft) CAD
app, as a web page: search, tags, and a download button for each plugin's zip.

## Get your plugin listed
The list updates itself every day. A plugin is listed when its public GitHub repository:

1. holds its SolidCraft `plugin.json` manifest (with `id` and `runtime`), and
2. has the topic `solidcraft-plugin` (the ⚙ next to *About* on the repository page).

Publish a release with the plugin zip attached to get a **Download .zip** button. The first
picture in the README becomes the card's picture; the name, description, version and menu
entries come from the manifest.

A plugin without the topic can be added to [repos.txt](repos.txt) with a pull request.

## How it works
`scripts/update.py` (Python, no dependencies) asks the GitHub API for the repositories, checks
each for a plugin manifest and writes `data/plugins.json`. A GitHub Action runs it every day and
commits the list when a plugin changed. The page (`index.html`, `app.js`, `style.css`) is plain
HTML that reads that file.

Run it yourself:

```sh
GITHUB_TOKEN=... python3 scripts/update.py   # the token is optional, for a higher rate limit
python3 -m http.server                       # then open http://localhost:8000
```

This is a community list, not made by Tangency Labs. Each plugin belongs to its author.

## Licence
MIT, see [LICENSE](LICENSE).
