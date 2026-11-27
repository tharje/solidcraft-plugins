# SolidCraft Plugins

A list of community plugins for the [SolidCraft](https://github.com/tangency-labs/solidcraft) CAD
app, as a web page: search, categories, and a download button for each plugin's zip.

## Get your plugin listed
The list updates itself every day. A plugin is listed when its public GitHub repository:

1. holds its SolidCraft `plugin.json` manifest (with `id` and `runtime`), and
2. has the topic `solidcraft-plugin` (the ⚙ next to *About* on the repository page).

Publish a release with the plugin zip attached to get a **Download .zip** button. The first
picture in the README becomes the card's picture; the name, description, version and menu
entries come from the manifest.

A plugin without the topic can be added to [repos.txt](repos.txt) with a pull request. Every
plugin on the [SolidCraft Workshop](https://workshop.solidcraft.io) is listed too, and gets a
**Workshop** button. A theme or shader plugin (no `runtime`) is listed when its release has a zip
named after its id.

The example plugins in SolidCraft's own [plugin guide](https://docs.solidcraft.io/dev/plugins.html)
are listed under **Examples**, with a link to the guide instead of a download.

Give your commands an icon (`x-solidcraft-icon`, SolidCraft 0.44) and the first one is shown on
the card too. It must be a plain SVG: one with scripts, event handlers or outside links is left out.

## Tested in SolidCraft
After each update, `scripts/compat.py` downloads the newest SolidCraft release for Linux (checked
against its `SHA256SUMS.txt`) and each plugin's latest release zip. SolidCraft loads the plugin
and runs each of its commands with their default values, headless with `solidcraft-cli`. A card
then says **✓ Runs in SolidCraft x.y** (every command ran) or **✓ Loads in SolidCraft x.y**
(loaded, but its commands need something picked first, or it asks for file access or sensitive
commands and so isn't run). Nothing is shown when it doesn't load: that may be the test's fault.
A plugin is tested again when its release or SolidCraft's changes. The results are in
`data/compat.json`. The plugins run in a job that can't push to this repository.

## Quality checked
A plugin with the green **✓ Quality checked** badge has been tested by hand, one version at a time.
It passed when:

1. it installs and loads in the newest SolidCraft;
2. every command runs without errors, with its default values and with real settings;
3. it makes whole, valid bodies that can be edited in SolidCraft;
4. it asks for no more than it needs, and never for the network;
5. it has an open source licence, a README that says how to use it, and a release with its zip;
6. its repository takes issues, for questions and bugs.

Anyone can ask for a check with the [Request a quality check](../../issues/new?template=quality-check.yml)
form. The plugin is tested, a short report goes into the issue and [checks/](checks/), and the
check is added to [verified.json](verified.json): the version, the date, who tested it and in which
SolidCraft. After a newer release the badge turns grey and names the version that was checked,
until the new one is checked too. The **✓ Quality checked** button above the list shows only these
plugins.

## Report a problem
Each card has a **Report a problem** link to an issue form here, for a plugin that crashes
SolidCraft, harms designs, won't install or looks unsafe. Ordinary bugs go to the plugin's author.

## How it works
`scripts/update.py` (Python, no dependencies) asks the GitHub API for the repositories, checks
each for a plugin manifest and writes `data/plugins.json`. Each plugin gets a category from its
words (`CATEGORIES`, with `CATEGORY_OF` for the ones words get wrong). A GitHub Action runs it every day and
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
