# Source attribution

`Menu.qml`, `MenuModel.js`, and the logo/button pattern in `BarWidget.qml` derive
from Omarchy's `shell/plugins/menu/` in the captured Omarchy 4.0.2-1 reference
recorded by this repository's `UPSTREAM.json`. Copyright (c) David Heinemeier
Hansson; the full MIT license is included in `LICENSE`.

Gooey changes replace the centered menu surface with `qs.Ui.KeyboardPanel`,
add explicit button/output selection and lifetime handling, shared owned IPC,
pointer Back/Clear controls, and preserve the host's shared application engine.

The plugin imports Omarchy's `qs.Commons` and `qs.Ui` modules. It intentionally
declares no `clonedFrom` metadata and does not replace the stock menu's utility,
select, or input routes. Its host-module compatibility is scoped to the captured
reference until tested against additional releases.
