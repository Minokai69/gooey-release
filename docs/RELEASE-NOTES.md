# Gooey early preview — release notes

Gooey is for people who want Hyprland with Omarchy without memorizing dozens of
keybindings for daily navigation. Visible window controls and an anchored app menu
make the mouse useful alongside the shortcuts you already like.

This is a **source-install preview candidate**, not a general compatibility release.
This public snapshot is released as v0.1.0-preview.1, with marketplace review requested.

## Included

- Native, full-width window frames that follow Omarchy’s theme and bar sizing.
- Full app labels, a central click-or-drag resize grip, and hover explanations.
- Per-window Shelf, workspace, actions, true fullscreen, and close controls.
- Dwindle controls that hide ineffective resize axes.
- Scrolling 50%, 85%, and 100% column sizes and Previous/Center/Next navigation.
- Quickshell Apps & desktop menu anchored to the Omarchy logo.
- A persistent **Style → Gooey** toggle, configuration backups, and stock recovery.

## Read before installing

Tested host: Omarchy **4.0.3-1**, Quickshell **0.3.1**, and the pinned Hyprland
**0.56.2** native build. Gooey verifies exact shell files and native compatibility.
Do not bypass these guards to install on a different host. Updates require a
reviewed rebuild and validation; automatic updates and public binary packages are
not provided yet.

True fullscreen hides the frame; **Super+F** restores it. Use menu **Maximize** to
keep mouse controls visible. Grouped-window actions are restricted. Scrolling
sizes affect an entire native column. **Niri is not supported.**

## Evidence and release preparation

The application payload `0.1.0-dev-ba91a43d0d1b` passed 170 isolated desktop checks.
Documentation and screenshots describe that tested payload. Images contain only
sample windows, with exact region captures at 2× scale; see
[media provenance](media/release/README.md).

Before a wider public release, the project still needs a distributable installer,
a supported-version/update policy, clean-machine installation and fresh-login
acceptance testing, and broader application/display coverage. The native companion
must remain tied to compatible Hyprland headers and runtime APIs.

[Illustrated user guide](USER-GUIDE.md) · [Install and recover](INSTALL.md) ·
[Validation](VALIDATION.md)
