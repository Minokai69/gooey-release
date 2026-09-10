# Validation evidence

The source installer adds read-only host/dependency checks, failure-path coverage,
and a fresh-profile test using the built payload. The updated Python suite passes
**53 tests**. Fresh-profile testing covers deployment, repeat deployment, profile
selection, restoration with user edits preserved, and payload removal in a path
containing spaces. These checks do not boot a clean OS or test a fresh login.

The source installer also completed `./install --validate`: native build, input
helper build, launcher checks, fresh-profile test, isolation, smoke, and **174
headless desktop checks** passed. This run did not deploy to the main session.

## Preview 2 baseline

The September 8, 2026 preview is tested on **Omarchy 4.0.3-1**, Quickshell
**0.3.1**, and the Hyprland **0.56.2** revision recorded in `HOST.json` and
`companions/hyprland/PIN.json`. The current tested payload is
`0.1.0-dev-ba91a43d0d1b` (application source commit `7ffec4b`).

The latest isolated integration run passed **170 checks**, including real pointer
clicks, native drag resizing/moving, fullscreen and restore, dwindle/scrolling,
Shelf, workspace moves, anchored menus, hover tooltips, and multiple output scales.
The full app label was also visually checked on the main session at 160% scaling.
The packaging/session suite passes **40 Python tests**, with **11 native app-name
cases** and **6 launcher anchor-policy checks**.
Fresh-login behavior and broad hardware/application combinations have not been
retested for this preview. These checks establish the tested host, not arbitrary
Omarchy or Hyprland compatibility.

Release images are captured from isolated sample apps with `dev/run release-capture`.
No personal desktop screenshots are included. The capture manifest records the
payload and each screen region. Machine-specific historical reports are excluded from this public snapshot.
