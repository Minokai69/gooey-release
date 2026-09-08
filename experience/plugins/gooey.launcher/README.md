# Gooey launcher

This owned menu/button plugin reuses Omarchy's menu routes and the shell's shared
`AppLibrary`, with the popup attached to the actual Omarchy-logo `WidgetButton`.
It imports the pinned host's `qs.Ui.KeyboardPanel` and `qs.Commons`; it has no
runtime import back into `base/` and makes no changes to package-owned files.

## Registration and invocation

Stage this whole directory as an owned plugin named `gooey.launcher`, and replace
the selected logo layout entry with `{ "id": "gooey.launcher" }`. Keep the stock
`omarchy.menu` plugin enabled for its utility, dmenu/input, and recovery routes.
There is deliberately no blanket clone/IPC redirection.

The menu entry uses `keepLoaded: true`, so all outputs and both activation routes
share one controller and menu state. After the plugin has loaded:

```sh
omarchy-shell gooey.launcher toggle root
omarchy-shell gooey.launcher summon apps
omarchy-shell gooey.launcher close
omarchy-shell gooey.launcher status
```

The right-Super binding should call the first command using the compositor's
tap-only semantics. Binding installation/restore is owned by the experience
profile, not by this QML plugin.

The normal host lifecycle also works and preserves the route payload:

```sh
omarchy-shell shell summon gooey.launcher '{"trigger":"keyboard","toggle":true,"menu":"root"}'
```

`status` reports the selected output, actual button rectangle, card rectangle,
orientation, route, search, and fallback state for nested verification.

## Behavior

- Left-click opens beside that precise button, even on an unfocused monitor;
  clicking it again closes. Right-click also toggles the menu.
- Keyboard opening chooses a drawn button on the focused output. If that output
  has no usable button, choose the first by output name and layout position. Never
  select a zero-sized center placeholder or silently reuse a stale pointer token.
- The top/bottom/left/right layout, screen, scale, and live ancestor transforms
  are resolved by `KeyboardPanel`, with `centerOnBar: false`.
- Top and bottom cards grow away from the bar. Side bars use a stable, fitted
  viewport so filtering does not shift the card vertically around the button.
- Search takes keyboard focus on open. Arrow keys, Enter, paging, search, app
  launch feedback, and pointer row browsing reuse the menu engine. Visible Back
  and Clear search buttons make navigation possible with the pointer. Escape or
  outside click closes. The card swallows clicks; a launch closes before dispatch.
- One controller keeps one launcher open. If it receives an explicit pointer
  request from a different output, it reanchors while retaining search/navigation.
  The current host's other-output dismissal overlay consumes the first click,
  so clicking another output's logo while open can require a second click. A
  one-click cross-output handoff needs a popup-host extension or packaged panel
  adaptation; it is not claimed by this first implementation.
- If a bar surface is rebuilt, release the input surface while reacquiring its
  button on the same output for up to 600 ms. Removing the button or losing that
  output closes safely. Full host/plugin reloads destroy the controller and close
  the launcher, as the stock plugin lifecycle requires.

## Omarchy theming

The launcher uses Omarchy's `[menu]` palette and selected-row border specifications,
including gradients and per-side widths. Header/search fonts, control sizes,
padding, and rounding follow `Style`; square themes remain square. The logo's
hover and selected surfaces use the shared `[controls]` tokens and the bar's text
color. Search and header actions retain the menu's foreground and font family.

The owned card honors `menu.background-alpha`. The pinned host's `KeyboardPanel`
also paints its popup background underneath and has no public background override,
so the final transparency combines the menu and popup surfaces. Gooey preserves
that host behavior; independently transparent menu cards need a public host API.

## Hidden/absent bar fallback

This captured host exposes a persistent manually hidden bar flag, with no
transient auto-hide reveal/hold interface. Gooey therefore does not change that
flag or overwrite `barHidden` at runtime. If all buttons are absent, disabled, or
manually hidden, keyboard opening explicitly falls back to the stock centered
Omarchy menu. `status.fallback` and the shell log identify this fallback; it is
not described as an anchored popup. If a future host supplies an auto-hide hold
API, integrate and test it before claiming automatic reveal support.

Modal select/input requests sent accidentally to this plugin are forwarded to
`omarchy.menu` with their original payload. Normal stock callers are unchanged.

## Validation boundary

Both QML files parse with the bundled Qt `qmlformat`; independent anchor-policy
checks cover focused-output choice, exact pointer tokens, stale-token rejection,
empty candidates, and deterministic fallback. Nested runtime, all four bar edges,
button reordering, hotplug/mixed-scale outputs, and tap-only right-Super handling
must be verified in the private development session before wider compatibility
claims. See the repository's `docs/ANCHORED-LAUNCHER.md` acceptance matrix.

Source attribution and MIT terms are in `NOTICE.md` and `LICENSE`.
