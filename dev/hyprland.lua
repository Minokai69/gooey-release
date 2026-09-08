-- Only the nested desktop. Never import the installed Omarchy autostart.
hl.monitor({ output = "", mode = "1280x800@60", position = "auto", scale = 1 })
hl.config({
  general = { gaps_in = 5, gaps_out = 10, border_size = 2, resize_on_border = true },
  decoration = { rounding = 8 },
  ecosystem = { no_update_news = true },
  misc = { disable_hyprland_logo = true, disable_splash_rendering = true },
})
hl.bind("SUPER + Escape", hl.dsp.exit())
hl.bind("SUPER + Super_R", hl.dsp.exec_cmd("qs ipc -p \"$OMARCHY_PATH/shell\" call gooey.launcher toggle root"), { release = true })
hl.bind("SUPER + S", hl.dsp.workspace.toggle_special("scratchpad"))
hl.bind("SUPER + ALT + S", hl.dsp.window.move({ workspace = "special:scratchpad", follow = false }))
hl.bind("SUPER + T", hl.dsp.window.float({ action = "toggle" }))
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })
hl.on("hyprland.start", function()
  hl.exec_cmd("/opt/omarchy-mouse-shell/dev/session")
end)
