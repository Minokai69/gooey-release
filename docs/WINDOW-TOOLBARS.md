> Historical design notes. For the current release interface and screenshots,
> see the [Gooey user guide](USER-GUIDE.md).

# Attached window controls

Gooey adds a full-width native window strip and Quickshell action menu to each eligible
application window. Hyprland continues to own tiling, scrolling, workspaces, focus,
and move/resize grabs. The controls provide mouse access to those native operations.

The implementation is split between `companions/hyprland/` and
`experience/plugins/gooey.window-tools/`. Stock Omarchy hosts the QML plugins;
`base/` is an unchanged reference snapshot used only in the private development home.

## Placement and appearance

The header spans its window’s width inside the native border, with a centered app
name and icon-only Actions, Resize, Shelf, Workspace, Maximize/Restore, and Close.
The left side holds the resize grip and layout-specific sizing icons; the right
side holds window actions. Empty space moves the window. Narrow frames retain Actions/Resize and expose the
other operations in the menu. It matches the actual Omarchy bar thickness, including font scaling
and bar orientation. Hyprland reserves that height as native decoration space,
slightly reducing the client's tile to make room. The strip does not overlap the
client header or the desktop bar. Narrow clients use icons and elide the name.
Partly offscreen strips keep their name and controls inside the owner's visible
monitor area; a sliver narrower than one control hides the strip.

The app name stays visible. Buttons reveal when the pointer is over the owner or
its strip and remain usable during a native grab. Hover changes only the controls;
the reserved space stays constant. Menus preserve their owner and remain usable
when the pointer moves from the strip into the popup.

The native companion handles stacking, clipping, pointer occlusion, movement, and
output scaling. Input outside the strip remains normal desktop/application input.
Fullscreen and undecorated windows omit it; maximized windows retain it. This is a
native decoration, not a polling-positioned layer-shell overlay.

The resolved Omarchy `Color`, `Style`, and public `Border` values style the menus,
launcher, and native bridge. Colors update through Omarchy's existing theme pipeline;
user shell.toml overrides keep their usual precedence. Hyprland draws its original border around the combined header and client, retaining
active/inactive gradients and border animations. Header rounding follows the window;
its inner bottom corners are square. Buttons have no permanent fill or outline.
The native app-name font
follows Omarchy’s resolved bar font family and body size. Native flat surfaces
resolve gradients to their first color and side borders to one width; QML keeps
the complete border treatment. Zero rounding is respected. No independent Gooey theme file,
per-theme edits, or theme-set hook is necessary.

## Interaction contract

| Control | Behavior |
| --- | --- |
| Move grip | Native Super+left-drag behavior after a five-pixel movement threshold |
| Diagonal resize icon | Click for layout and sizing options; drag for a native resize grab (inward-facing edges in dwindle; bottom-right for floating windows and scrolling) |
| Actions or right-click | Open the owning window's menu; retain that identity across focus changes |
| Shelf / Take off shelf | Move only the captured window to/from Omarchy's scratchpad |
| Send to workspace | Choose numbered, named, configured, or existing destinations; optional Follow window |
| Float / Tile | Toggle the captured window's participation in the native layout |
| Maximize / Restore | Use native maximized mode while retaining desktop controls |
| Close | Request the owner's normal close path, including application save dialogs |

Buttons activate on release and cancel if the pointer moves away. The QML bridge
serializes requests and rejects stale compositor/window identities. Capabilities
come from current native state and are rechecked when the action executes.

Resize opens **Arrange & resize** or scrolling **Column controls** directly.
Dragging uses Hyprland's layout rules: dwindle tiles need a neighboring tile to
share space with, so a lone tiled window may not visibly resize. Floating windows
resize freely. All frame buttons are icon-only. Menus follow their specific opener,
including when the window moves or the frame is clipped by a scrolling viewport.
The launcher and Shelf buttons on Omarchy’s Quickshell bar are also icon-only;
hover hints and the Shelf count remain.

## Layout-specific controls

| Layout/state | Additional controls |
| --- | --- |
| Dwindle tile | Change split; swap left/right/up/down; tile resize increments |
| Scrolling tile | Half/85%/Full column size; Previous/Center/Next column; native resize |
| Floating window | Shared actions and native size controls |
| Other layouts | Shared supported actions; dwindle/scrolling controls are hidden |

Scrolling Half/85%/Full controls are manual. They change the owner's **column**, which
can contain several stacked windows. Full size keeps the column in the scrolling
tape; it does not enter maximize/fullscreen. Horizontal layouts show width labels;
vertical layouts show height labels. Neighbor navigation explicitly brings the
next/previous column into view even with `follow_focus` disabled. The end of the tape
disables the unavailable direction.

No application defaults, persistent sizing rules, or automatic layout switching are
installed. Existing Hyprland preferences still decide initial column sizes. An open
menu adapts when its owning workspace changes layout. Grouped, maximized/fullscreen,
and scrolling-inhibited targets disable operations that would be unsafe or ambiguous.

## Shelf and workspace ownership

Shelf is Omarchy's `special:scratchpad`: Super+S remains its visibility shortcut.
The bar has a visible Shelf list for mouse retrieval. Membership comes from live
compositor state, including windows moved by existing keyboard shortcuts. Saved
origin metadata assists restoration but is not required to retrieve windows.

Workspace selection retains its owner and chosen Follow setting across focus changes.
Named destinations containing spaces are supported. Shelf restoration uses a valid
normal workspace rather than inventing an arbitrary number. Actions which could
silently affect grouped neighbors are disabled.

## Maintenance and limits

The supported tuple is Omarchy 4.0.2-1, Quickshell 0.3.1, and Hyprland 0.56.2 at
`efb50993780079460b0cbed1363e2166a2de1d9f`. Native headers and runtime must match.
Rebuild and validate after compatible compositor updates; retain stock Omarchy if
there is no matching companion. Never replace a binary inside a running compositor.

The private suite covers real pointer actions, theme changes, layout switching,
scaled outputs, target retention, and native unload/recovery. The detailed tested
matrix and remaining gaps are in [VALIDATION.md](VALIDATION.md). Public distribution,
broader toolkit/display coverage, touch, fullscreen entry with a mouse exit, and Niri
support remain future work. Niri requires its own attached-decoration solution;
its IPC commands alone do not establish parity.

The native bridge is documented in [the companion README](../companions/hyprland/README.md).
Primary references: [pinned Hyprland scrolling implementation](https://github.com/hyprwm/Hyprland/blob/efb50993780079460b0cbed1363e2166a2de1d9f/src/layout/algorithm/tiled/scrolling/ScrollingAlgorithm.cpp),
[official hyprbars](https://github.com/hyprwm/hyprland-plugins/tree/main/hyprbars), and
[Niri's design principles](https://niri-wm.github.io/niri/Development:-Design-Principles.html).

## Left-side tile sizing

The integrated frame is the approved visual baseline. Dwindle tiles expose icon-only native 200-pixel adjustments only on resizable
axes: narrower/wider for horizontal splits and shorter/taller for vertical
splits. Ancestor splits count, so a nested tile can expose both pairs. A lone
tile exposes neither pair. The resize menu follows the same capabilities;
floating windows retain both axes, and single-app scrolling columns hide
secondary-axis resizing.
Scrolling tiles instead expose three filled-column icons for Half, 85%, and Full.
The current owner and layout are checked again on activation. No app rules or
global layout preferences change. A lone dwindle tile may have no neighboring
space to exchange.

The resize grip stays on the left for click-to-open sizing and native drag resizing.
Its popup opens inward from that button. Floating and maximized windows omit
layout-specific presets. Narrow frames retain the sizing menu rather than crowding
out the app name and window actions.
