-- Hyprland (0.56+, Lua config) pieces for playing Radiance on a 144 Hz VRR monitor.
-- Adapt output names and workspace names to your setup.

-- Variable refresh for fullscreen windows only. Check the monitor supports it:
--   modetest -M nvidia-drm -c | grep -A3 vrr_capable
hl.config({ misc = { vrr = 2 } })

-- Direct scanout for windows tagged content = "game": the game's frames go straight to the display
-- without a compositing pass. Set back to 0 if a game flickers or shows black.
hl.config({ render = { direct_scanout = 2 } })

-- Minecraft: on the gaming workspace, compositor fullscreen while the game keeps a normal window
-- (no F11 needed, workspace switching keeps working), opaque, tagged as a game.
hl.window_rule({
    name = "minecraft-gaming-workspace",
    match = { class = "^([Mm]inecraft.*)$" },
    workspace = "name:gaming",
    content = "game",
    decorate = false,
    fullscreen_state = "2 0",
    sync_fullscreen = false,
    no_shortcuts_inhibit = true,
    opaque = true,
})

-- A way out of fullscreen games that works even when the game inhibits shortcuts.
hl.unbind("SUPER + TAB")
-- o.bind is Omarchy's helper; on plain Hyprland use hl.bind.
o.bind("SUPER + TAB", "Switch to previous workspace (leave/return to game)",
  hl.dsp.focus({ workspace = "previous_per_monitor" }), { dont_inhibit = true })
