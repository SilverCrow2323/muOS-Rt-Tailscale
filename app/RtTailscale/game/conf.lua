function love.conf(t)
  t.identity = "rttailscale-m"
  t.version = "11.5"           -- the LOVE runtime bundled with the app (bin/love)
  t.window.title = "Rt:Tailscale-M"
  t.window.width = 640
  t.window.height = 480
  t.window.resizable = false
  t.window.vsync = 1
  t.console = false
  -- we only need graphics, input and timers
  t.modules.audio = false
  t.modules.sound = false
  t.modules.physics = false
  t.modules.video = false
  t.modules.thread = false
  t.modules.touch = false
end
