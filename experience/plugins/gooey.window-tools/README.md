# Gooey window tools

Development plugin hosted by stock Omarchy. It provides menus for an explicitly
identified window and a visible Shelf list. Hyprland remains responsible for
window layout, movement, resizing, focus, and workspace policy; this plugin invokes
the companion's owner-bound routes to those existing operations.

The manifest ID is `gooey.window-tools`. It declares `service`, `panel`, and
`bar-widget`: putting that ID in the bar layout loads one service, the persistent
menu host, and one Shelf button per bar output. The same plugin can also be enabled
through `plugins[]`, but its bar entry is needed for the visible Shelf opener.
There is no clone metadata or replacement of stock session services.

The root stage helper owns installation in the private development home. Do not
copy this plugin into the real user's config or run an installed-shell restart as
part of development. This package uses tested `qs.Commons`/`qs.Ui` host modules and
does not depend on relative imports into the reference `base/` tree.

## Native protocol

The compatible companion must provide protocol version 1:

```text
hyprctl gooey:state
hyprctl gooey:window ' --instance INSTANCE ACTION WINDOW_ID [arguments]'
hyprctl gooey:shelf
hyprctl gooey:theme ' --instance INSTANCE KEY VALUE ...'
```

State is a JSON object with `protocolVersion`, `instance`, `windows`, `workspaces`,
`monitors`, and optional `configuredWorkspaces`. IDs are native decimal strings;
the instance token prevents an ID being reused after a compositor restart.
Window objects include state, capabilities, output, and a global logical `anchor`
rectangle supplied by the native strip. Actions return `{ "ok": true }` or an
error object. Every command uses argv, without executing a shell.
The leading space before `--instance` is intentional: this Hyprland version's
`hyprctl` otherwise treats it as its own command-line flag. The companion trims
the payload before parsing its instance guard.

The theme route receives resolved `background`, `foreground`, `accent`, `muted`,
`danger`, `border`, `normal`, `hover`, `pressed`, `normalBorder`, `hoverBorder`,
`normalBorderWidth`, `hoverBorderWidth`, `radius`, `scale`, `height`, `fontSize`,
and `fontFamilyHex` fields.
Colors are eight-digit `AARRGGBB`; geometry is logical pixels except `scale`, which
is a multiplier. `fontFamilyHex` encodes the font family's UTF-8 bytes as one hex
token, preserving spaces and non-ASCII names without a quoting grammar.
State includes `theme.ready` and `theme.revision` so a reloaded companion can
request its appearance again without restarting the shell.

Workspace action arguments are `0|1 DESTINATION` where `1` means follow. Numeric
destinations and `name:Workspace name` are supported. Empty configured workspaces
remain visible. Special workspaces are excluded from the destination picker;
Shelf uses Omarchy's existing `special:scratchpad` separately. Regular named
workspaces may have negative internal IDs and are addressed by name.

Each window also reports `layout` (`dwindle`, `scrolling`, or `other`). Scrolling
tiles include column membership, normalized size, direction, and capability flags
`columnWidth`, `columnCenter`, `columnPrevious`, and `columnNext`. The owned UI
submits `column-width half|85|full`, `column-center`, or
`column-focus previous|next` through the same instance-guarded window route.
The direction-specific capability is checked before requesting column focus.

The companion opens menus through the panel's single IPC target:

```text
qs ipc -p "$OMARCHY_PATH/shell" call gooey.window-tools openMenu WINDOW_ID workspace
qs ipc -p "$OMARCHY_PATH/shell" call gooey.window-tools openMenu WINDOW_ID actions
qs ipc -p "$OMARCHY_PATH/shell" call gooey.window-tools openMenu WINDOW_ID layout
qs ipc -p "$OMARCHY_PATH/shell" call gooey.window-tools openMenuForInstance WINDOW_ID workspace INSTANCE
qs ipc -p "$OMARCHY_PATH/shell" call gooey.window-tools shelf
qs ipc -p "$OMARCHY_PATH/shell" call gooey.window-tools status
```

The host `shell summon gooey.window-tools` path accepts JSON
`{"kind":"shelf","screen":"OUTPUT"}` or `{"kind":"workspace","id":"ID"}`.
The combined panel + bar-widget kinds preserve these payloads. The menu waits for
a fresh native snapshot before mapping. Window identity stays fixed while open;
closing the target or changing compositor instances cancels the menu.
The companion uses `openMenuForInstance` so a delayed launcher command cannot open
a different window after the compositor restarts; `openMenu` remains a development
entry point for explicitly addressing a window in the current session.

## Behavior

- Frame and Shelf-bar controls are icon-only. Shelf, Workspace, Maximize/Restore,
  and Close are directly available in wide frames. Native owner popups track the
  specific opener rectangle while preserving that opener across internal pages.

- Workspace picker combines defaults 1–10, configured Hyprland destinations, and
  live normal workspaces. `Follow window` starts off. The current workspace is
  marked and cannot trigger an unnecessary move. Numbered destinations form a
  five-column grid; named destinations have full-width labels. A visible Follow
  switch explains whether the current workspace will change.
- Shelf lists live scratchpad membership, including windows shelved before the UI
  started. It offers Show window, Take off shelf, and Show/hide Shelf workspace.
  Taking a window back captures a normal workspace when opening the view; if no
  destination is available, the picker opens instead.
- The integrated window frame keeps the centered application name visible and opens a compact
  Window controls card with Shelf, Workspace, Float/Tile, Maximize/Restore size,
  and normal application close. Clicking the diagonal resize icon opens the
  layout and sizing menu directly; dragging it performs native resizing. On dwindle
  tiles, Arrange & resize opens split, directional swap, and 200-pixel resize
  increments. A visible hint explains the drag gesture and neighboring-tile sizing.
  A fixed Back button returns to the main card. Native capability
  flags gate actions. Grouped movement is blocked; unknown capabilities default
  off.
- Only scrolling tiles offer Half, 85%, and Full column sizes, with the current
  fraction selected. The same size controls appear in the main card and directly
  in Column controls. Vertical scrolling layouts use height labels.
  These are manual changes to the owner's entire native column, including any
  stacked windows. Column controls offers Previous, Center, and Next with arrows
  following the scrolling direction; unavailable neighbors are disabled. Focusing
  another column closes the menu. Split/swap controls are hidden on scrolling
  layouts, and floating windows keep only shared controls. There are no automatic
  application rules, per-app sizing defaults, or changes to the user's layout.
- The right frame button enters true fullscreen, matching Super+F. Hyprland hides
  the frame in fullscreen; Super+F restores the window and its controls.
  Maximize in the actions menu uses Hyprland's maximized mode and retains desktop controls; scrolling
  Full width changes a column's size without entering maximized mode.
- Native anchors position window menus. The Shelf button uses its actual bar
  widget geometry on all four edges. Output removal closes the popup and releases
  input. Menus scroll inside their output bounds, with a fixed title and Close
  button. Opening a menu or switching between actions and workspaces resets the
  scroll position.
- Native window menus close when their decoration is no longer visible or the
  owner moves to another output. The Shelf's fallback destination picker keeps
  its visible Shelf anchor so shelved windows remain accessible without a native
  decoration.
- The strip reserves a fixed area above its application. The name remains visible
  while controls reveal over the owner or strip, without changing the window's
  layout. Native `decorationVisible` means the strip is eligible; transient
  `controlsShown` does not dismiss an open menu when the pointer enters it.
- Popups use Omarchy's popup surface, readable type, vector icons, and action rows
  based on 44 logical pixels at the default spacing scale. Tiling, swap, and resize
  controls are grouped by purpose. Shelf entries have separate Show and Take off
  shelf actions; the empty state explains
  how to set a window aside. The bar shows a count when the Shelf has windows.
- While a command is pending, further actions are disabled until a snapshot taken
  after the command updates authoritative state. This prevents double-clicking
  Shelf from immediately undoing the first request.

## Omarchy theming

Window cards and action controls use the host's `Color`, `Style`, `Border`, and
`BorderSurface` components. They follow theme `shell.toml` surface colors,
opacity, gradients, and per-side borders, the shared font and spacing scales, and
Hyprland-derived `Style.cornerRadius`, including square themes. The watched user
`~/.config/omarchy/shell.toml` overrides remain authoritative.

`NativeThemeBridge` sends the same resolved host state to the companion. The strip
uses the bar's background and foreground and its actual current `barSize`, so
moving the menu bar to a vertical edge or changing its font/size updates the strip's
thickness too. Interactive fills and borders use the shared control tokens.
Native title text uses `Style.font.body` and the bar's font family. For Omarchy's
default `monospace` alias, the bridge sends `Style.resolvedFontFamily`, including
updates after the host reloads its fontconfig selection.
The native strip uses a flat first color stop and the largest side width for
gradient or asymmetric border specifications; its QML menus retain the complete
Omarchy border specification.

Updates are coalesced for 100 ms and serialized on their own process, independently
of window actions. Theme changes during a request submit only the latest resolved
state afterward. A failed request is retried on the next native state refresh;
an unavailable or reloaded companion is synchronized when it returns. The bridge
does not parse theme files again, rewrite Hyprland configuration, or install a
theme hook. The panel's `status` IPC exposes `theme.synced`, effective size tokens,
and the submitted palette for isolated integration checks.

Optional private preferences at `~/.config/gooey/windows.json` can set
`configuredWorkspaces` to values such as `[1, 2, "Research desk"]` or objects like
`{"value":"name:Research desk","label":"Research"}`. The service does not write
this file or edit Hyprland configuration.

QML formatting/parser validation and pure state-model assertions have passed.
Actual native IPC, input behavior, and rendering must also pass the root task's
nested integration tests before this is considered ready for activation.
