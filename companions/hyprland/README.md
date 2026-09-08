# Gooey Hyprland companion

Native attached window controls derived from official hyprbars. Upstream
BSD-3-Clause attribution is in `LICENSE.upstream`; the exact source is in `PIN.json`.
The companion runs alongside stock Omarchy and uses Hyprland's own window and
layout operations. It does not implement another tiling engine.

Build with `./build.sh` using C++23, pkg-config, Cairo, and matching Hyprland
headers. Output: `build/gooey.so` and `build/build-info.json`. The build refuses
untested headers; loading also checks Hyprland's API/header hash. Test with the root
`dev/run` harness, then use the guarded session deployment workflow. Never overwrite
a loaded binary or copy the companion into the installed Omarchy tree.

## Integrated window frame

Each eligible window gets a full-width header inside its native border, showing a
centered app name with an adjacent Resize grip and icon-only Actions, Shelf, Workspace, Fullscreen,
and Close controls. Empty header space remains a move handle. Its sticky native decoration reserves one
Omarchy bar-height so the client and desktop bar remain clear. It has no inset
fallback over application content. Narrow clients use icons and elide text. The strip
clips horizontally to the owner's usable monitor area and arranges its contents in
that visible intersection. A sliver narrower than one control hides the strip.

A priority-11000 reservation places the header inside Hyprland’s priority-10000
border. The native border retains its active/inactive gradient and animation around
the combined frame. PART_OF_MAIN_WINDOW includes the header in native shadows.
The header uses the window’s outer rounding, square inner corners, and no separate
button outlines. Popups track the specific opener’s current rectangle.

The strip/name remain visible while controls respond to the pointer over the owner
or strip. Hover never changes the reserved height. `decorationVisible` represents
durable window eligibility; `controlsShown` represents pointer context. Quickshell
menus remain anchored when the pointer leaves the strip for their popup.

Logical geometry is independent of output scale. Native move starts after five
logical pixels. Clicking the diagonal resize icon opens the existing layout
menu; dragging it uses Hyprland's bottom-right grab. Dwindle resizing needs an
adjacent tile to share space with. Narrow frames collapse to Actions and Resize;
the remaining operations stay available in the Actions menu. Buttons activate on release
and cancel when dragged away. Right-click opens the owner's menu. Fullscreen and
undecorated windows have no strip hit area; maximized windows retain their controls.
Touch is not implemented.

`NativeThemeBridge.qml` supplies the resolved Omarchy palette, control states,
borders, rounding, spacing, actual bar thickness, and app-name font. `fontSize` is
the canonical body size; `fontFamilyHex` carries UTF-8 bytes as one validated token.
No theme files are rewritten and no theme hook is required. Native flat surfaces
use the first gradient stop and largest side border; QML uses full BorderSurface
styling. Zero rounding is honored.

## Bridge version 1

- `hyprctl gooey:state`: JSON with compositor instance, stable window IDs, state,
  per-window capabilities, logical geometry, visible button rectangles, workspace
  destinations, monitors, and resolved native theme diagnostics.
- `hyprctl gooey:window '--instance SIGNATURE ACTION ID [ARGS]'`: JSON success or
  error. Check `ok`; compositor errors may still return process exit status zero.
  Missing owners and stale instances fail without retargeting.
- `hyprctl gooey:shelf`: toggle Omarchy's `special:scratchpad`, as Super+S does.
- `hyprctl gooey:theme '--instance SIGNATURE KEY VALUE ...'`: atomic theme update.
  Requires every supported field once. Unknown/missing/duplicate keys, stale
  instances, malformed AARRGGBB colors, and invalid dimensions are rejected.
- Exact dispatch aliases exist for state and Shelf; use raw commands for window
  actions because this pinned compositor uses Lua dispatch grammar.

Shared actions: `close`, `focus`, `shelf [normal-destination]`, `float`, `fullscreen` (Super+F), `maximize`,
`workspace FOLLOW DESTINATION`, `resize DX DY`, `menu-workspace`, `menu-actions`,
`menu-layout`.
FOLLOW is 0/1. Destinations are normal numeric IDs or `name:Workspace name`; names
with spaces are supported. Workspace selection can create a chosen empty workspace;
Shelf retrieval does not invent a destination.

Dwindle tiles expose `split` and `swap l|r|u|d`. Split synchronously focuses the
captured owner before the native layout message. Scrolling tiles expose:

- `column-width half|85|full|third|two-thirds`: set the owner's normalized column size.
- `column-center`: center that column in the scrolling viewport.
- `column-focus previous|next`: focus and bring the adjacent column into view,
  including when the user's `follow_focus` preference is disabled.

The public UI offers Half/85%/Full sizes. A full column remains tiled and can be
scrolled past; it is distinct from Maximize. Vertical scrolling labels these sizes
as heights. Column actions act on the entire native column, including other windows
stacked in it. State includes column index/count, size, direction, and member count.
There are no automatic app rules, selected-app defaults, or layout switching.
Floating, grouped, maximized/fullscreen, inhibited, and unsupported targets are
capability restricted. Native methods revalidate every action independently of QML.

Shelf membership is always reconstructed from live workspace state, including
windows shelved through existing shortcuts. Origin metadata under the compositor's
runtime directory assists restoration but is never required to find a window.
Grouped windows refuse actions that could silently affect the group.

The bridge accepts fixed actions, never configurable command strings. Menu launch
calls `gooey.window-tools.openMenuForInstance(ID, KIND, INSTANCE)` with validated
IDs and a quoted shell path. `GOOEY_SHELL_PATH` selects the QML host; otherwise
`$OMARCHY_PATH/shell` is used. Menus preserve the captured owner across focus changes.
Fullscreen entry and group manipulation remain absent from Gooey's menu.

Frame controls show a themed tooltip after a 400 ms hover. Hints explain native
window actions and click-versus-drag behavior. The tooltip follows its button
and output, ignores pointer input, and hides when clicking or opening a menu.
