# Developing Gooey

This public snapshot omits the private development history and `base/`.
The preview defaults to mounting `/usr/share/omarchy` read-only.

Gooey has two Quickshell plugins (`gooey.launcher`, `gooey.window-tools`) and a
native Hyprland decoration companion. `base/` and `UPSTREAM.json` preserve the
original Omarchy reference; `HOST.json` describes the currently reviewed host.
Read [AGENTS.md](../AGENTS.md) and [PRODUCT.md](../PRODUCT.md) before changing it.

## Build and test

Use a C++23 compiler, Python 3, Node.js, pkg-config, the matching Hyprland development
headers, and the development libraries requested by `companions/hyprland/build.sh`
(including Cairo and PangoCairo). The private desktop uses Bubblewrap, D-Bus,
Quickshell, Hyprland, and grim. `dev/build-input` builds the private virtual pointer
and keyboard helpers. They refuse to operate outside the nested desktop.

```sh
./companions/hyprland/build.sh
./dev/stage
./dev/build-input
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run integration-headless
python3 -m unittest discover -s tests -v
./companions/hyprland/test-app-identity.sh
node experience/plugins/gooey.launcher/tests/anchor-resolver.test.cjs
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run check-isolation
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run smoke
```

`GOOEY_TEST_HOST` mounts the reviewed host read-only for testing. Without it, the
preview uses the original reference in `base/`. Do not change `HOST.json` merely
to silence a failed compatibility check: review the upstream change and validate
it first. The native companion separately checks its header/API match.

`./preview` opens an interactive nested desktop. Close it before staging another
build. The private home is `.devhome/`; it contains only test state. Main-session
activation is separate and documented in [INSTALL.md](INSTALL.md).

## Capture release images

```sh
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run release-capture
```

This launches an isolated compositor with sample applications, sets its headless
output to 2560×1600 at scale 2, and uses native UI geometry with `grim -g` to capture
individual controls and menus. It also captures the real Style → Gooey entry,
registered with the session runtime’s own menu generator in the **private home**.
The capture does not click that toggle or change the installed desktop.

Output is `.devhome/.cache/release-media/`, including `capture.json`. Review every
image before copying it into `docs/media/release/`. Never substitute screenshots
of personal windows. Captures are documentation evidence, not a replacement for
the integration suite. The script uses the currently staged payload; rebuild and
stage first after changing application code.

## Project layout

| Path | Purpose |
| --- | --- |
| `experience/plugins/` | Owned launcher and window-tool plugins |
| `companions/hyprland/` | Native controls, pinned API boundary, build metadata |
| `session/gooey-session` | Main-session deploy, compatibility, enable, and recovery |
| `gooey` | Separate private-profile packaging CLI |
| `dev/` | Isolated compositor, fixtures, input drivers, checks, capture workflow |
| `tests/` | Packaging and session ownership/recovery tests |
| `seed/` | Initial private-home defaults |
| `base/`, `UPSTREAM.json` | Original read-only reference host |
| `HOST.json` | Current reviewed host package and shell-file hashes |
| `work/`, `.devhome/` | Ignored builds, local evidence, and private test state |

## Migrating from Omousey

Disable the old experience with `omousey disable` before deploying and enabling
Gooey. They use different plugin IDs and data directories; do not enable both.
Old backups remain under `~/.local/share/omousey/backups/`; new ones are under
`~/.local/share/gooey/backups/`. Retain old backups until you no longer need them.
