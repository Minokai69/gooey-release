> Historical design notes. For the current release interface and screenshots,
> see the [Gooey user guide](USER-GUIDE.md).

# Gooey button-anchored launcher

Status: implemented in experience/plugins/gooey.launcher/ and exercised in the
nested desktop. See VALIDATION.md for coverage, remaining limits, and separately
recorded main-session activations.

## Required behavior

Clicking the Omarchy logo button in the menu bar opens the launcher next to that
exact button. Pressing the right Super key opens the same launcher at the button
on the selected display. Both routes share one menu state and toggle it closed on
repeat activation.

The installed Omarchy implementation is its own Quickshell menu, not Rofi.
`base/shell/plugins/menu/BarWidget.qml` invokes `omarchy.menu`, whose `Menu.qml`
already provides the root menu and the application list through the shared
`AppLibrary`. Its current card is centered in an overlay. Reuse the menu data,
application discovery, and useful routes; replace centered placement for the
Gooey launcher with a live button anchor.

## Placement

| Bar position | Launcher position |
| --- | --- |
| Top | Below the button |
| Bottom | Above the button |
| Left | To the right of the button |
| Right | To the left of the button |

Use the button's current surface, output, and logical rectangle as the anchor.
Do not hardcode screen coordinates or anchor only to the bar edge. Moving the
button within a bar must move its menu origin too. Clamp the card inside the
output's usable bounds, preserve a small gap, and scroll overflowing content.

While open, track bar position, button layout, panel size, output geometry, and
scaling changes. Avoid jumps when filtering changes the menu height: keep the
appropriate anchored edge fixed. If a bar drag requires recreating its Wayland
surface, preserve menu state and reopen/reanchor only when the replacement anchor
is valid. A removed button or disconnected output closes the menu safely; never
retain a popup with a dangling anchor.

Pointer activation selects the clicked button's display. Keyboard activation uses
the focused display's valid button, with a deterministic fallback to an available
button when necessary. It must not choose an arbitrary QML instance on a different
monitor. Keep only one Gooey launcher open across displays.

For an automatically hidden bar, reveal and hold the anchor while the launcher is
open. If every bar/button is disabled, keyboard activation needs an explicit
documented fallback; it cannot pretend to be attached to an absent button.

## Input and menu behavior

- A right-Super tap toggles the launcher. A right-Super modifier chord must not
  accidentally open it on release. Preserve existing Super shortcuts unless the
  user explicitly chooses otherwise; verify the compositor's tap/release behavior.
- Clicking the logo provides the full mouse route. No keyboard shortcut is required.
- Search takes focus when open; browsing applications by mouse remains available.
- Outside click and Escape dismiss it; menu clicks never leak into an app beneath it.
- The logo displays its open state and toggles the same visible instance.
- Switching launcher outputs or rebuilding the bar preserves search/navigation
  only when that state still has a valid destination.
- Retain normal app-launch feedback. Prevent one click from launching twice.

## Implementation boundary

Package as an owned Gooey menu button/popup plugin, using the stock bar's widget
and popup interfaces where possible. Keep the installed Omarchy menu available for
recovery. The stock menu's broader command/select/input roles are separate from
this placement requirement; avoid blindly rerouting all modal utilities to a bar
popup as part of the first launcher change.

The existing `qs.Ui.KeyboardPanel` is a strong reuse point: it accepts the actual
`anchorItem` and `bar`, selects the anchor window's screen, tracks transforms and
layout changes through `TransformWatcher`, and positions its card for all four bar
edges. Keep `centerOnBar: false`. Its focus and outside-click coordination already
serve keyboard- and mouse-opened panels. Verify bar reconstruction and hotplug
behavior rather than assuming every lifetime case is covered.

Use an `gooey.launcher` button and route-aware panel, or explicitly separate
button and panel IDs. The stock host discards payloads on its bar-widget-only
summon path (`shell.qml:455`), so preserve root/apps route payloads through a panel
or an owned routing method. A blanket clone redirect could unintentionally change
system or dmenu calls. No stock host edit appears necessary for this feature.

Stage the experience and a right-Super binding in the private development profile.
Production activation records only the plugin/layout/binding changes it owns, with
restore behavior that preserves subsequent user edits. No Rofi dependency is
needed merely to implement anchored placement.

## Acceptance checks

1. Open with the logo and right Super; both control the same anchored launcher.
2. Move the bar to each edge, while closed and while open. Reopen beside the button.
3. Reorder the logo between sections and move neighboring widgets; follow its new
   location without hardcoded offsets.
4. Use two monitors with different scales; click each button and invoke from each
   focused monitor. Never open on the wrong display.
5. Filter to a short and long result list near every screen corner; preserve the
   anchor, fit the screen, and keep all rows reachable by scrolling.
6. Hide/show the bar, unplug its output, reload the plugin, and remove the button
   while open. No stuck input grab or orphaned menu remains.
7. Use right Super in another shortcut, then release it; the launcher stays closed.
8. Click to launch once, cancel by outside click, and navigate submenus by mouse.
9. Restore the prior profile in the private home; other bindings and widgets remain.

## Inspected source

- `base/shell/plugins/menu/BarWidget.qml`: logo-button invocation.
- `base/shell/plugins/menu/Menu.qml:21`: route payload handling.
- `base/shell/plugins/menu/Menu.qml:1017`: overlay window and centered card.
- `base/shell/plugins/bar/Bar.qml:468`: widget instances and focused-output routing.
- `base/shell/Ui/KeyboardPanel.qml:40`: live anchor, output, popup positioning and focus.
- `base/shell/shell.qml:455`: payload-free bar-widget summon path.
- `base/default/hypr/bindings/utilities.lua`: stock menu shortcuts.
