# Gooey development boundaries

This project is a separate Omarchy shell development copy. The user's installed
desktop must remain operational and independent.

Product scope and distribution boundaries are defined in PRODUCT.md. Prefer an
independently versioned UI plugin package hosted by stock Omarchy. The copied base
is a development/reference host, not a second Omarchy distribution to ship.
Implement installation and update workflows in the private home first; do not
activate them in the real session without an explicit activation request.

- Edit this repository, never `/usr/share/omarchy`, the user's real desktop
  settings, session startup, or installed packages as part of ordinary development.
- Run the shell through `dev/run`. Do not run `qs -p base/shell` on the host.
- Do not invoke host `omarchy restart`, `refresh`, `dev link`, or broad process kills.
- The private home is `.devhome/`; `seed/` provides first-launch defaults.
- Preserve sandbox boundaries. Exposing host IPC, audio, hardware-control services,
  or configuration requires an explicit integration task from the user.
- Keep `UPSTREAM.json` as the original snapshot record and preserve the MIT license.
- Run `dev/run check-isolation` and `dev/run smoke` after launcher changes.
  Smoke briefly opens a nested desktop and captures only that desktop.
- Hyprland is currently the development host. Niri support is an upcoming feature,
  not an existing capability of this copy.
