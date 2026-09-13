# Gooey — product direction

Gooey is an installable, mouse-friendly extension of Omarchy’s Quickshell
experience on Hyprland. Omarchy is the current product and support target.
Use **Gooey** as the display name and `gooey` for package, command,
and plugin namespaces.
Gooey works **with Hyprland**: it is a graphical route to the compositor operations
already exposed by keyboard shortcuts. Preserve the user's layouts, window policies,
and bindings. The native companion provides attached controls and exact-window
dispatch; it does not implement a competing layout engine or synthesize global keys.
Window controls must be attached to each ordinary application window, as explicitly
selected by the user. The implementation scope is in
[docs/WINDOW-TOOLBARS.md](docs/WINDOW-TOOLBARS.md).
Controls should express Hyprland behavior: **Send to shelf / Take off shelf** using
Omarchy's existing scratchpad, native hold-and-drag movement without modifier keys,
and visible tiling controls. Include a mouse-accessible Shelf opener and configurable
additional actions; do not model the feature as ordinary minimize/maximize buttons.
Expose Shelf, Workspace, Maximize/Restore, and Close directly in the frame. Include
a dedicated **Send to workspace** action with a
clickable workspace picker and an explicit Follow window option. Span the window's
width with a header inside the native border, center the visible app name, and reveal icon-only controls when the
pointer is over the owner or strip. Reserve a fixed native space so the strip
overlaps neither the application nor Omarchy’s bar, without rearranging windows
on hover. Match the bar’s thickness, font, and existing theme tokens. Clicking the
diagonal resize icon opens layout and sizing options; dragging it uses native
resizing. Explain that tiled resizing shares space with neighboring tiles.
Show split/swap for dwindle and manual 25%/Half/85%/Full column sizes and navigation for
scrolling. Do not install app-specific sizing rules or switch the user's layout.
Window popups follow their specific opener button. Launcher and Shelf bar buttons
show icons without permanent text labels. The launcher must open from the Omarchy menu-bar button or right Super and remain
anchored to the button as the bar moves or widgets are reordered. See
[docs/ANCHORED-LAUNCHER.md](docs/ANCHORED-LAUNCHER.md).
Users keep their existing Omarchy installation and normal Omarchy updates. They
can install, select, update, and remove this experience independently, and return
to their previous shell layout without reinstalling their desktop.

Attached controls, Quickshell menus, local release staging/selection/restore, and
personal main-session integration are implemented. Daily use currently targets
the pinned Omarchy 4.0.2-1, Quickshell 0.3.1, and Hyprland 0.56.2 host recorded in
the validation documentation. Source deployment and an explicit enable command
are available, with a graphical **Restore stock Omarchy** entry. A source installer now builds and validates the pinned host before optional
activation. Broader host support and automatic update integration remain
future work; see [docs/INSTALL.md](docs/INSTALL.md) for the current boundary.

## Distribution boundary

Prefer an experience package built from replacement bar, widget, and panel
plugins hosted by Omarchy's existing shell. Fork the interface where necessary;
reuse upstream session, lock, notification, and system integrations where possible.
Keep patches to the host narrowly scoped and propose upstream extension points
if a required capability cannot be implemented through plugins.

Attached window strips use a small, version-matched Hyprland decoration companion,
based on hyprbars, with Quickshell menus in normal Omarchy plugins. Geometry,
mouse input, and local release workflows are exercised in the nested desktop
before production activation.
This adds a separate native compatibility boundary; do not imply QML plugin updates
alone maintain it. Other Quickshell environments on Hyprland will need separate integration and
compatibility testing before support is offered.

The installed version inspected here supports:

- Full replacement bars selected by `bar.id`, with a stock-bar fallback for
  missing or invalid selections.
- User plugins in `~/.config/omarchy/plugins/`.
- Plugin clone metadata and routing of existing IPC calls to enabled clones.
- A `post-update` hook followed later by the stock shell restart.

These are implementation details of the inspected Omarchy release, not a promise
of a stable public API. A valid but malfunctioning custom bar may still require
explicit recovery; upstream's selection fallback is not a universal crash guard.

Do not globally redirect `OMARCHY_PATH`, shadow system commands on PATH, replace
package-owned files, or run a second lock/notification/polkit stack in production.
The existing Omarchy launch, restart, and update flow must continue to work.

## Installation and selection

1. Check the installed Omarchy, Quickshell, and compositor against the tested
   exact tested versions and shell files before activation.
2. Stage a versioned release in this project's own user data directory. Keep
   project-specific preferences in a separate user configuration directory.
3. Register only project-owned plugin IDs. Include every dependency needed by
   those plugins; do not assume copied QML relative imports survive relocation.
4. Capture the existing bar selection and only the shared configuration fields
   activation will change. Preserve unrelated user plugins and preferences.
5. Let the user explicitly select the new experience. Refuse switching during a
   locked session and use Omarchy's supported reload/restart flow.
6. Provide a graphical switch back to the previous experience and an independent
   recovery command that works when the custom interface fails.

Installation and activation are distinct operations. Source `deploy` stages a
release and installs the personal session runtime; `gooey enable --check`
reviews the proposed selection before `gooey enable` applies it. The runtime
backs up `shell.json` and `hyprland.lua`, adds its own `hypr/gooey.lua` startup
module, and binds a previously unbound right Super. Stock Super+Space remains.
`gooey disable` or the restore application entry unloads the exact owned native
binary and restores unchanged owned configuration entries. It preserves unrelated
edits and retains release/configuration backups.

## Updating alongside Omarchy

Omarchy continues to own system package updates. Gooey's local payloads have
independent content-identified versions. The current workflow is manual:
disable Gooey, build a reviewed source revision, validate it in the nested
desktop, deploy, and enable. There is no public update channel or post-update hook.

Personal-session startup checks the exact Omarchy package and captured shell-file
hashes, Quickshell version, and native Hyprland version/commit. A mismatch refuses
native loading and restores the stock selection. A deferred startup caused by a
locked or unavailable shell can be retried with `gooey start` after unlocking.
These guards constrain support to the tested host; they do not establish behavior
on a new upstream release. A changed host needs a reviewed compatibility baseline
and nested validation before it is accepted.

The broader release design must retain these boundaries:

- Stage updates in a new release directory; never overwrite QML currently in use.
- Validate manifests, dependency layout, configuration migrations, and compatibility
  before changing the active release pointer.
- Select the new release atomically and reload at a safe time. Retain the previous
  release and a matching configuration migration backup for rollback.
- An optional project-owned post-update hook can check compatibility after Omarchy
  updates. It must not silently fetch and execute new project code or edit
  unrelated settings.
- Define and test recovery from an unsupported Omarchy update, including the case
  where its restart would otherwise load an incompatible plugin. Do not assume
  version checking alone guarantees a safe fallback.
- Uninstallation removes only owned files and integration entries. Restore a
  shared field only when it still contains our installed value; otherwise preserve
  the user's subsequent change.

The release pipeline should test the minimum and current supported Omarchy versions
and record the tested Quickshell and compositor versions. Avoid promising support
for arbitrary Omarchy releases before those tests exist.

## Development repository versus user package

`base/` is the captured Omarchy reference and isolated development host. It is not
the intended user installation payload. Its bundled updater, system scripts, and
defaults should not become a second independently maintained Omarchy distribution.

User-facing code lives in `experience/plugins/` and `companions/hyprland/`;
`session/` owns personal session integration, with packaging and compatibility
tests alongside it. Keep an upstream baseline separate from local UI changes so
upstream fixes can be reviewed and merged deliberately.

`UPSTREAM.json` records the original installed snapshot. A differing hash means
upstream changed; it does not by itself prove incompatibility. Before release,
replace reliance on a package snapshot alone with a pinned upstream Git revision
and a reproducible import/update process.

## Supported environment and future options

Build and test Gooey for Omarchy on Hyprland first. Its current launcher, theme,
bar, session, and installation integration depend on Omarchy’s Quickshell setup.

Future options may support other Quickshell environments on Hyprland. Keep the
Hyprland window operations separate from the Omarchy shell integration so those
environments can receive their own launcher, theme, and session adapters.
No additional environment is currently supported; each will require its own
installation and compatibility tests.

## Delivery milestones

1. Isolated development host — implemented and smoke-tested.
2. Attached controls, launcher, workspace picker, and Shelf — implemented.
3. Versioned local releases and private-profile install/select/restore/rollback tests — implemented.
4. Personal daily-use integration for the pinned host, guarded startup, and graphical restore — implemented; main-session activation is an explicit operation.
5. Public packaging/update channel, broader compatibility, and graphical configuration — future work.
6. Other Quickshell environments on Hyprland, with dedicated integration and compatibility tests — future work.

## Local evidence

Inspected installed Omarchy package 4.0.2-1:

- `shell/README.md`: full-bar plugins, fallback, plugin configuration.
- `shell/services/PluginRegistry.qml`: plugin discovery and selection.
- `bin/omarchy-plugin-clone`: owned plugin copies and clone routing metadata.
- `bin/omarchy-launch-shell`: supervision and disabled production hot reload.
- `bin/omarchy-restart-shell`: IPC selection and lock-aware restart handling.
- `bin/omarchy-update` and `bin/omarchy-update-restart`: post-update ordering.

## Accepted frame baseline

The user approved the integrated native frame on September 6, 2026. Preserve its
continuous native border, icon-only controls, centered app name, fixed reservation,
and Omarchy styling. Keep sizing on the left and window actions on the right;
future changes should refine this design rather than replace it.
