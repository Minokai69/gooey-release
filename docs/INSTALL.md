# Installation, updates, and recovery

Gooey supports personal daily use on the pinned host: Omarchy **4.0.3-1**,
Quickshell **0.3.1**, and Hyprland **0.56.2** at
`efb50993780079460b0cbed1363e2166a2de1d9f`. It uses the installed Omarchy shell,
user plugin registrations, and a separate native companion. The public source omits `base/`; nested tests mount installed Omarchy read-only.

This is deployment from reviewed source for the tested host. A public installer,
release/update channel, and compatibility with other versions remain future work.
These instructions describe activation; deployment alone does not enable the
main-session experience.

## Build and validate before deployment

Run from the repository root. Close any nested preview before staging its next
release. Build and inspect the isolated desktop:

```sh
./companions/hyprland/build.sh
./dev/stage
./preview
```

`build.sh` compiles the Hyprland companion against the installed development
headers and records its version, compositor revision, and binary hash in
`companions/hyprland/build/build-info.json`. The companion checks its match with the
running compositor when loaded. Build and test again after a compositor update.

Before main-session deployment, run the packaging/session tests and nested checks:

```sh
python3 -m unittest discover -s tests -v
node experience/plugins/gooey.launcher/tests/anchor-resolver.test.cjs
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run check-isolation
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run smoke
./dev/build-input
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run integration-headless
```

The current nested integration passes 170 checks covering attached-window input, live Omarchy themes,
dwindle/scrolling controls, scaled outputs, and companion unload during an active
move or resize. See [VALIDATION.md](VALIDATION.md) for the exact
coverage and remaining limits.

## Deploy and enable the main session

Run deployment from this reviewed source checkout:

```sh
./session/gooey-session deploy
```

This stages the built payload in `~/.local/share/gooey/releases/`, installs the
session runtime, adds `~/.local/bin/gooey`, and creates a **Restore stock Omarchy**
application entry. It does not enable the plugin selection or load native controls.
The installed `gooey` command is the session interface. The repository's
`./gooey` remains the lower-level packaging CLI used for private-profile testing.

From the intended unlocked Hyprland session, review and enable:

```sh
gooey enable --check
gooey enable
gooey status
```

Use `~/.local/bin/gooey` if the command is not yet on PATH. `enable --check`
reports the staged release, proposed shell entries, startup module, binding, and
recovery command without enabling them. Preflight refuses a locked or unavailable
session, existing Hyprland configuration errors, another hyprbars companion,
foreign integration files, conflicting right-Super bindings, or a mismatched host.

`enable` backs up `shell.json` and `hyprland.lua` under
`~/.local/share/gooey/backups/`, records the exact native binary and compositor
instance, then loads the companion and selects the owned plugins. It creates
`~/.config/hypr/gooey.lua` and a marked `require("hypr.gooey")` block in the
user's `hyprland.lua`. The owned module starts Gooey in later sessions and binds
right Super to the anchored launcher. Right Super must be unbound beforehand;
the existing stock Super+Space route is retained.

The wrapper waits for both native palette readiness and the UI theme acknowledgement
before accepting a themed-decoration release. It uses Omarchy's shell configuration reload
and plugin rescan, validates
Hyprland configuration, and waits for native and QML readiness. If the rescan
retains failed QML component loads, it checks the lock again and uses Omarchy's
official shell restart before repeating readiness checks. It does not replace
the installed shell or start a second lock/notification stack. Failed activation
attempts restore the tracked prior files and unload a newly loaded companion.

## Startup and status

The owned startup module runs `gooey start` only while an activation record
exists. Before native loading, startup verifies the staged payload's integrity,
the running Hyprland version and commit, the recorded Omarchy package and shell-file
hashes, and the exact Quickshell version. The companion also retains Hyprland's
API/header hash check. An unsupported host is refused; startup disables the owned
selection and notifies that stock Omarchy has been restored.

If startup is deferred because the shell is unavailable or the session is locked,
retry after the shell is ready and the session is unlocked:

```sh
gooey start
gooey status
```

`status` reports whether the profile is selected, the recorded binary/instance and
backup, and any interrupted native-load marker. It is recorded deployment state,
not a comprehensive live-health test. An interrupted load marker prevents an
automatic retry until the interruption is inspected.

The independent `native.json` ownership record survives profile rollback if a
native unload fails, so the recovery command can still identify the exact binary.

## Restore the main session

Choose **Restore stock Omarchy** from the launcher, or run:

```sh
gooey disable
```

Disable runs while unlocked. It unloads the exact owned native companion, restores
unchanged owned shell entries, removes the owned startup block/module, reloads
Hyprland, and refreshes the shell. If shell IPC is unavailable, it can use Omarchy's
official lock-aware shell restart. Applications, independent settings, release
files, and backups are retained. Gooey entries edited after activation are
preserved rather than overwritten; inspect those entries if you deliberately
customized the selection and want to remove it completely.

## Update the main session

Keep Omarchy's normal updater. Disable Gooey before changing Omarchy, Hyprland,
Quickshell, or the selected Gooey payload. The current update sequence is manual:

```sh
gooey disable
# Review the source update, then build and validate it in the nested desktop.
./companions/hyprland/build.sh
./dev/stage
python3 -m unittest discover -s tests -v
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run check-isolation
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run smoke
./dev/build-input
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run integration-headless
./session/gooey-session deploy
gooey enable --check
gooey enable
```

A new upstream host requires a reviewed source/compatibility baseline and passing
nested checks; rebuilding alone does not make a different host supported. The
build and startup guards will reject unreviewed version changes. `UPSTREAM.json`
remains the original snapshot record. There is no automatic download, post-update
hook, or public release channel in this personal workflow.

Keep the main companion disabled while replacing a selected release. Private
packaging rollback is available below; the installed session interface does not
yet offer a one-command main-session release rollback. `gooey disable` is the
immediate recovery path to stock Omarchy.

## Private-profile package operations

The remaining package commands target `.devhome`, never the main session. Close
the nested preview before changing its selected release.

`dev/stage` creates `.devhome` from `seed/` if necessary, then runs the two separate
package operations:

```sh
./gooey install --home .devhome
./gooey activate --home .devhome
```

`install` copies the two plugins, native binary, metadata, and licenses into a new
content-identified release directory. It writes a per-file integrity manifest and
records that release as staged. It does not change the profile's shell selection.

`activate` verifies the staged release and existing profile, then selects it with
owned symlinks and a small shell-layout change. It replaces the first stock menu
button when appropriate, adds the Shelf entry if missing, and registers the owned
plugins. Existing Gooey entries are retained. Stock `omarchy.menu` remains
available for utility routes and launcher recovery.

The CLI records the exact entries it inserted or replaced. It validates before
switching links and restores prior files/links if a subsequent write fails. It
refuses foreign plugin directories, foreign release links, malformed profiles,
symlinked `shell.json` files, and incomplete or modified releases.

### Update and roll back the private profile

After changing or obtaining a reviewed source revision, close the preview and run:

```sh
./companions/hyprland/build.sh
./gooey install --home .devhome
./gooey status --home .devhome
./gooey activate --home .devhome
./preview
```

The staged release has its own directory; the previously selected release remains
available. Repeating activation of the same release preserves the rollback target.
`status` distinguishes the staged release, current release link, and whether an
activation record exists. A current link can remain after restore, so `selected`
is the relevant profile-selection indicator.

To select the previous release, close the preview and run:

```sh
./gooey rollback --home .devhome
./preview
```

Rollback requires a valid previous release with an integrity manifest. Initial
prototype directories created before those manifests were introduced must be
restaged; they are not accepted as verified rollback targets. Rollback selects the
prior payload and retains current unrelated settings. General preference/schema
migration and compatibility matrices are still future work.

The packaging CLI verifies payload integrity. Main-session lock coordination,
host compatibility checks, and native lifecycle belong to the session wrapper
described above. A version match alone does not prove behavior.

### Restore or remove the private profile

To return the private profile's owned unchanged entries to their previous values:

```sh
./gooey restore --home .devhome
./preview
```

Restore preserves unrelated edits, pre-existing Gooey entries, and Gooey entries
whose settings you changed after activation. It does not overwrite the whole
`shell.json`. It removes the activation record but keeps release files for later
selection. Without that record, the nested session does not load the native
companion at startup.

To remove the package's owned files as well:

```sh
./gooey uninstall --home .devhome
```

Uninstall first performs restore, then removes owned registrations and releases.
If preserved current entries still refer to Gooey, it keeps their dependencies
and explains why. Remove those entries deliberately before repeating uninstall if
you intend to remove them too. Other files in the Gooey data directory and
separate preferences are retained.

The repository's packaging CLI never restarts a running shell, loads/unloads a
native companion, or edits keybindings. The nested launcher owns startup and its
private right-Super binding. Close and relaunch the nested desktop after a selection
change. Do not substitute these file-only commands for main-session `disable`.

## File ownership

Package paths below are relative to the selected home (`.devhome` for preview;
the real user home for personal deployment):

| Path | Purpose |
| --- | --- |
| `.local/share/gooey/releases/0.1.0-dev-<hash>/` | Immutable payload, metadata, checksums, and licenses |
| `.local/share/gooey/staged.json` | Release awaiting selection |
| `.local/share/gooey/current` | Current release link |
| `.local/share/gooey/previous` | Previous release link |
| `.local/share/gooey/activation.json` | Exact owned entry changes for restore |
| `.config/omarchy/plugins/gooey.launcher` | Owned launcher registration link |
| `.config/omarchy/plugins/gooey.window-tools` | Owned window-tools registration link |
| `.config/omarchy/shell.json` | Shared profile layout; modified by owned-entry operations |
| `.config/gooey/windows.json` | Optional preferences; retained on removal |

The personal session wrapper additionally owns:

| Path | Purpose |
| --- | --- |
| `.local/bin/gooey` | Link to the deployed session command |
| `.local/share/gooey/runtime/` | Session command, packaging support, and exact host compatibility record |
| `.local/share/gooey/runtime-files.json` | Deployed runtime file ownership hashes |
| `.local/share/gooey/session.json` | Exact loaded binary, compositor instance, and backup location |
| `.local/share/gooey/load-pending.json` | Interrupted-load marker, present only while a load is pending |
| `.local/share/gooey/backups/` | Timestamped pre-enable shell and Hyprland configurations |
| `.local/share/applications/gooey-restore.desktop` | Restore stock Omarchy application entry |
| `.config/hypr/gooey.lua` | Owned startup and right-Super module |
| `.config/hypr/hyprland.lua` | Shared file; only the marked Gooey startup block is added/removed |

Main-session `disable` removes activation/startup selection but retains the
deployed runtime, recovery entry, and backups. A full public uninstall workflow
for those session-runtime files is future work.

## Launcher recovery and runtime checks

Click the Omarchy logo for a pointer-only path. The right-Super route calls
`gooey.launcher toggle root`; both routes use the same menu controller. If no
visible button exists, the keyboard route uses the stock menu instead. A manually
hidden bar is respected. On another monitor, the existing popup's dismissal
surface can consume the first click, requiring a second click on that monitor's
logo.

Run verification from the repository root:

```sh
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run check-isolation
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run smoke
./dev/build-input
GOOEY_TEST_HOST=/usr/share/omarchy ./dev/run integration-headless
```

Results live under `.devhome/.cache/`, including `gooey-shell.log`,
`gooey-companion.log`, and `gooey-integration.log`. The preview uses sample apps
and an isolated compositor; a successful nested run does not establish every
application, layout, monitor, scale, or future upstream-version combination.

When enabling a different release, Gooey uses Omarchy’s supported shell restart
after checking the session is unlocked. A plugin rescan alone can retain old QML
at the unchanged plugin paths. Application windows and user configuration remain
in place. To check popup positions after updating, run
`python3 dev/verify-popup-anchors.py` from the source checkout; it briefly opens
and closes the three owner menus and compares them with native button rectangles.
