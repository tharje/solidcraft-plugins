# Quality check: Gridfinity 1.7.0

**Plugin:** [tharje/gridfinity-solidcraft](https://github.com/tharje/gridfinity-solidcraft), release [v1.7.0](https://github.com/tharje/gridfinity-solidcraft/releases/tag/v1.7.0)
**Checked:** 2026-11-27 by tharje, in SolidCraft 0.50.0 on Linux
**Result:** passed

| Criterion | Result |
|---|---|
| Installs and loads in the newest SolidCraft | Yes: 0.50.0, also 0.49.1 (`solidcraft-cli plugin check`: no problems) |
| Every command runs with its defaults and with real settings | Yes: 30 of 30 test cases in `solidcraft-cli plugin test` (bins with dividers, scoops, labels, magnets, screws, eco and solid bins, lids, baseplates, drawer plates, the panel, Edit bin) |
| Valid bodies you can edit | Yes: every case checks the body count and volume; bins and plates are ordinary sketches and features in a timeline folder, with the height and labels as parameters |
| Asks for no more than it needs | Yes: SolidCraft modelling commands, its own storage and a panel; no files, no network |
| Open source licence, README, release zip | MIT; README with install and use; zip on every release |
| Issues open for questions and bugs | Yes |

Also checked by hand in the desktop app: the dialogs, Edit bin filling in a picked bin's settings, and a lid sitting in a bin's stacking lip (no overlap, resting on the lip).
