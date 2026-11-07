-- Rt:Tailscale-M :: on-device UI (LÖVE 11.x), styled after the Tailscale web client.
--
-- Rules of the house:
--   * the UI never blocks: every shell command is a background job that is polled;
--   * everything is drawn on a fixed 640x480 canvas that is scaled to the real screen;
--   * gamepad (SDL gamepad API; muOS provides the controller mapping) and keyboard both work;
--   * no words in the button legend: controller icons + glyphs only;
--   * leave with SELECT+START.
--
-- Environment (all optional):
--   RTTS_DIR       app directory (default: parent of this ui/ folder)
--   RTTS_FAKE_DIR  read status.json / prefs.json / summary.txt / urls.txt from here instead of running commands
--   RTTS_DEMO      path prefix: render every screen to <prefix>-<name>.png, then quit
--   RTTS_DEMO_REAL=1  demo against the real daemon (used by the integration checks)
local json = require("lib.json")
local model = require("lib.model")
local qr = require("lib.qr")
local themes = require("lib.theme")
local I = require("lib.icons")
local input = require("lib.input")

local W, H = 640, 480
local TOP, BOTTOM = 100, 438            -- scrolling content area
local TABS = {
  { "Status", "status" }, { "Devices", "peers" }, { "Settings", "options" }, { "Panel", "panel" }, { "System", "system" },
}

local APP, RT, TS, TMP, FAKE
local F = {}
local canvas
local S = {
  tab = 1, sel = { 1, 1, 1, 1, 1 }, scroll = { 0, 0, 0, 0, 0 },
  summary = {}, status = nil, prefs = nil, urls = {}, urlIdx = 1,
  modal = nil, view = nil, toast = nil, login = nil, pingResult = nil,
  nintendo = true, theme = "light", time = 0, polls = {}, sheet = false,
}
local function T() return themes[S.theme] end

-- ------------------------------------------------------------------ shell jobs
local function sq(s) return "'" .. (tostring(s):gsub("'", "'\\''")) .. "'" end

local jobs, jobseq = {}, 0

--- Run `cmd` in the background; `cb(output, rc)` is called from love.update when it finishes.
local function job(cmd, cb)
  jobseq = jobseq + 1
  local base = TMP .. "/ui-job-" .. jobseq
  os.execute(("rm -f %s %s.rc; ( ( %s ) >%s 2>&1 </dev/null; echo $? >%s.rc ) >/dev/null 2>&1 &")
    :format(sq(base), sq(base), cmd, sq(base), sq(base)))
  jobs[#jobs + 1] = { base = base, cb = cb }
end

local function poll_jobs()
  for i = #jobs, 1, -1 do
    local j = jobs[i]
    local f = io.open(j.base .. ".rc")
    if f then
      local rc = tonumber(f:read("*a"):match("%d+")) or -1
      f:close()
      local o = io.open(j.base)
      local out = o and o:read("*a") or ""
      if o then o:close() end
      os.remove(j.base); os.remove(j.base .. ".rc")
      table.remove(jobs, i)
      if j.cb then j.cb(out, rc) end
    end
  end
end

local function fake_cmd(file) return "cat " .. sq(FAKE .. "/" .. file) end
local function rt(args) return FAKE and fake_cmd("rt-ok.txt") or (sq(RT) .. " " .. args) end
local function ts(args) return FAKE and fake_cmd("rt-ok.txt") or (sq(TS) .. " " .. args) end

local function toast(text, kind)
  S.toast = { text = text, kind = kind or "ok", untilT = S.time + 3.5 }
end

-- ------------------------------------------------------------------ polling
local function refresh()
  if not S.polls.summary then
    S.polls.summary = true
    job(FAKE and fake_cmd("summary.txt") or (sq(RT) .. " summary"), function(out)
      S.polls.summary = false
      S.summary = model.parse_summary(out)
    end)
  end
  if S.summary.daemon == "1" or FAKE then
    if not S.polls.status then
      S.polls.status = true
      job(FAKE and fake_cmd("status.json") or (sq(TS) .. " status --json"), function(out)
        S.polls.status = false
        S.status = model.parse_status(out) or S.status
      end)
    end
    if not S.polls.prefs then
      S.polls.prefs = true
      job(FAKE and fake_cmd("prefs.json") or (sq(TS) .. " debug prefs"), function(out)
        S.polls.prefs = false
        S.prefs = model.parse_prefs(out) or S.prefs
      end)
    end
  else
    S.status, S.prefs = nil, nil
  end
  if not S.polls.urls then
    S.polls.urls = true
    job(FAKE and fake_cmd("urls.txt") or (sq(RT) .. " urls"), function(out)
      S.polls.urls = false
      S.urls = model.parse_urls(out)
    end)
  end
end

local function act(cmd, okmsg)
  job(cmd, function(out, rc)
    if rc == 0 then toast(okmsg or "Done")
    else toast((out:match("[^\r\n]+") or "Failed"):sub(1, 64), "bad") end
    refresh()
  end)
end

local function show_output(title, cmd)
  S.view = { title = title, lines = { "Running..." }, scroll = 0 }
  job(cmd, function(out)
    local lines = {}
    for l in (out .. "\n"):gmatch("(.-)\r?\n") do lines[#lines + 1] = l end
    if #lines == 0 then lines = { "(no output)" } end
    if S.view then S.view.lines = lines end
  end)
end

-- ------------------------------------------------------------------ login (QR)
local function login_start()
  local server = ""
  local sf = io.open(APP .. "/config/rt.conf")
  if sf then
    server = sf:read("*a"):match("\nLOGIN_SERVER=([^\r\n]+)") or ""
    sf:close()
  end
  local extra = server ~= "" and (" --login-server=" .. sq(server)) or ""
  S.login = { started = S.time }
  if FAKE then return end
  -- `up` blocks until the login completes; the URL it needs is read from `status --json`.
  os.execute(("sh -c 'echo $$ >%s; exec %s up --timeout=0%s' >%s 2>&1 </dev/null &")
    :format(sq(TMP .. "/up.pid"), sq(TS), extra, sq(TMP .. "/up.log")))
end

local function login_cancel()
  if not FAKE then
    os.execute("kill $(cat " .. sq(TMP .. "/up.pid") .. " 2>/dev/null) >/dev/null 2>&1")
  end
  S.login = nil
end

-- ------------------------------------------------------------------ settings
local function save_settings()
  love.filesystem.write("settings.txt", ("nintendo=%d\ntheme=%s\n"):format(S.nintendo and 1 or 0, S.theme))
end

local function load_settings()
  local d = love.filesystem.read("settings.txt")
  if not d then return end
  local n = d:match("nintendo=(%d)")
  if n then S.nintendo = n == "1" end
  local t = d:match("theme=(%a+)")
  if t and themes[t] then S.theme = t end
end

-- ------------------------------------------------------------------ rows
-- Every tab returns { rows = {...}, qr = url|nil }. Row kinds:
--   hero | header | info | toggle | action | peer ; rows with an `action` can be selected.
local function tab_status()
  local st, sm = S.status, S.summary
  local daemon = sm.daemon == "1" or FAKE ~= nil
  local state = st and st.state or sm.backend
  local rows = {}

  local hero = { kind = "hero" }
  hero.name = (st and st.self and st.self.name) or "This device"
  hero.sub = (st and st.self and #st.self.ips > 0) and table.concat(st.self.ips, "   ") or "Not connected"
  hero.tailnet = st and st.tailnet or nil
  if S.login then
    hero.mode, hero.action = "button", login_cancel
  elseif not daemon then
    hero.mode, hero.label = "button", "Start"
    hero.action = function() act(rt("daemon start"), "Daemon started") end
  elseif state == "NeedsLogin" then
    hero.mode, hero.label, hero.action = "button", "Log in", login_start
  elseif state == "Running" then
    hero.mode, hero.on, hero.label = "switch", true, "Connected"
    hero.action = function() act(ts("down"), "Disconnected") end
  elseif state == "Stopped" or state == "NoState" then
    hero.mode, hero.on, hero.label = "switch", false, "Disconnected"
    hero.action = function() act(ts("up"), "Connecting...") end
  else
    hero.mode, hero.label = "text", "Connecting..."
  end
  rows[#rows + 1] = hero

  if st and st.exitNode then rows[#rows + 1] = { kind = "info", label = "Exit node", value = st.exitNode.name, tone = "primary" } end
  for _, h in ipairs(st and st.health or {}) do rows[#rows + 1] = { kind = "info", label = "Warning", value = h, tone = "warn" } end
  rows[#rows + 1] = { kind = "info", label = "Tailscale", value = (sm.ts_version or "?") .. (sm.tun == "1" and "  -  TUN" or "  -  userspace") }
  rows[#rows + 1] = { kind = "info", label = "Rt:Tailscale-M", value = sm.version or "?" }
  if state == "Running" and not S.login then
    rows[#rows + 1] = { kind = "action", label = "Log out of this tailnet", danger = true, action = function()
      S.modal = { text = "Log this device out? You will need to log in again.", yes = function() act(ts("logout"), "Logged out") end }
    end }
  end
  return { rows = rows }
end

local function tab_peers()
  local rows = {}
  if S.status then
    for _, p in ipairs(S.status.peers) do
      rows[#rows + 1] = {
        kind = "peer", peer = p,
        action = function()
          local ip = p.ips[1]
          if not ip then return end
          S.pingResult = "Pinging " .. p.name .. "..."
          job(ts("ping -c 3 --timeout 3s " .. sq(ip)), function(out, rc)
            local last = ""
            for l in out:gmatch("[^\r\n]+") do last = l end
            S.pingResult = p.name .. ": " .. (rc == 0 and last or "no reply")
          end)
        end,
        alt = p.exitOption and p.online and function()
          act(ts("set --exit-node=" .. (p.exit and "" or sq(p.ips[1]))), p.exit and "Exit node off" or ("Exit node: " .. p.name))
        end or nil,
      }
    end
  end
  return { rows = rows, empty = (not S.status) and "Connect first to see your devices." or (#rows == 0 and "No other devices in this tailnet." or nil) }
end

local function tab_options()
  local pr, sm = S.prefs, S.summary
  local rows = {}
  local function conf_toggle(key, svc)
    return function()
      local on = sm[svc] == "1"
      local cmd = rt("conf set " .. key .. " " .. (on and "0" or "1")) .. "; " .. rt(svc .. " " .. (on and "stop" or "start"))
      if svc == "taildrop" then cmd = rt("conf set TAILDROP " .. (on and "0" or "1")) .. "; " .. rt("drop " .. (on and "stop" or "start")) end
      act(cmd, "Saved")
    end
  end
  local function row(label, desc, on, fn) rows[#rows + 1] = { kind = "toggle", label = label, desc = desc, on = on, action = fn } end
  rows[#rows + 1] = { kind = "header", label = "Service" }
  row("Start at boot", "Run Tailscale when the device powers on", sm.autostart == "on", function()
    job(rt("autostart " .. (sm.autostart == "on" and "off" or "on")), function(out, rc)
      -- rt tells us when muOS needed a setting switched on for the boot script
      local line = out:match("[^\r\n]+") or "Boot setting updated"
      toast(line:sub(1, 72), (rc ~= 0 or out:find("System Settings", 1, true)) and "warn" or "ok")
      refresh()
    end)
  end)
  row("Watchdog", "Restart Tailscale if it stops", sm.watchdog == "1", conf_toggle("WATCHDOG", "watchdog"))
  row("Web panel", "Control it from your phone or PC", sm.panel == "1", conf_toggle("PANEL", "panel"))
  row("Taildrop receiver", "Accept files sent to this device", sm.taildrop == "1", conf_toggle("TAILDROP", "taildrop"))
  if pr then
    local function flag(f, cur) return function() act(ts("set --" .. f .. "=" .. (cur and "false" or "true")), "Saved") end end
    rows[#rows + 1] = { kind = "header", label = "This device" }
    row("Use Tailscale DNS", "MagicDNS names for your devices", pr.acceptDns, flag("accept-dns", pr.acceptDns))
    row("Use subnet routes", "Reach networks shared by other devices", pr.acceptRoutes, flag("accept-routes", pr.acceptRoutes))
    row("Run Tailscale SSH", "Let tailnet users SSH into this device", pr.ssh, flag("ssh", pr.ssh))
    row("Official web client", "Tailscale's own page on port 5252", pr.webclient, flag("webclient", pr.webclient))
    row("Shields up", "Block all incoming connections", pr.shieldsUp, flag("shields-up", pr.shieldsUp))
    row("Offer as exit node", "Let other devices route traffic through here", pr.advertiseExit, flag("advertise-exit-node", pr.advertiseExit))
  end
  rows[#rows + 1] = { kind = "header", label = "This app" }
  row("Dark theme", "Easier on the eyes in the dark", S.theme == "dark", function()
    S.theme = S.theme == "dark" and "light" or "dark"; save_settings()
  end)
  row("Nintendo button layout", "A/B and X/Y swapped (Anbernic style)", S.nintendo, function()
    S.nintendo = not S.nintendo; save_settings()
  end)
  return { rows = rows }
end

local function tab_panel()
  local sm = S.summary
  local rows = {}
  rows[#rows + 1] = { kind = "info", label = "Web panel", value = sm.panel == "1" and "Running" or "Stopped", tone = sm.panel == "1" and "ok" or "bad" }
  rows[#rows + 1] = { kind = "pin", pin = (sm.pin and sm.pin ~= "") and sm.pin or nil }
  if #S.urls == 0 then rows[#rows + 1] = { kind = "info", label = "Address", value = "No network yet", tone = "warn" } end
  for i, u in ipairs(S.urls) do
    rows[#rows + 1] = { kind = "action", label = (u.kind == "TS" and "Tailnet  " or "Wi-Fi / LAN  ") .. u.url:gsub("^https?://", ""),
      action = function() S.urlIdx = i end, current = (i == S.urlIdx) }
  end
  rows[#rows + 1] = { kind = "action", label = "Generate a new PIN", action = function()
    S.modal = { text = "Generate a new PIN? Open panel sessions will be closed.", yes = function() act(rt("pin new"), "New PIN created") end }
  end }
  return { rows = rows, qr = S.urls[S.urlIdx] and S.urls[S.urlIdx].url, narrow = true }
end

local function tab_system()
  local function sub(title, cmd) return function() show_output(title, cmd) end end
  local rows = {
    { kind = "action", label = "Start everything", action = function() act(rt("start"), "Started") end },
    { kind = "action", label = "Stop everything", action = function()
      S.modal = { text = "Stop Tailscale, the panel and the watchdog?", yes = function() act(rt("stop"), "Stopped") end }
    end },
    { kind = "action", label = "Restart the daemon", action = function() act(rt("daemon restart"), "Daemon restarted") end },
    { kind = "action", label = "Update Tailscale", action = function()
      S.modal = { text = "Download the latest stable Tailscale (arm64) and replace the binaries?", yes = sub("Update", rt("update")) }
    end },
    { kind = "action", label = "Run diagnostics", action = sub("Diagnostics", rt("doctor")) },
    { kind = "action", label = "Service log", action = sub("Service log", rt("log 80")) },
    { kind = "action", label = "tailscaled log", action = sub("tailscaled log", "tail -n 80 /tmp/tailscaled.log") },
    { kind = "action", label = "Take over another Tailscale install", action = function()
      S.modal = { text = "Disable other Tailscale services and import their node identity?", yes = sub("Take over", rt("adopt")) }
    end },
    { kind = "action", label = "Quit", glyph = "power", action = function() love.event.quit() end },
  }
  return { rows = rows }
end

local BUILDERS = { tab_status, tab_peers, tab_options, tab_panel, tab_system }
local function content() return BUILDERS[S.tab]() end

local function selectable(c)
  local list = {}
  for i, r in ipairs(c.rows) do if r.action then list[#list + 1] = i end end
  return list
end

-- ------------------------------------------------------------------ input
local function swap(btn) return input.swap(btn, S.nintendo) end

local function move(dir)
  local list = selectable(content())
  if #list == 0 then return end
  local sel = S.sel[S.tab] + dir
  if sel < 1 then sel = #list elseif sel > #list then sel = 1 end
  S.sel[S.tab] = sel
end

local function button(btn)
  btn = swap(btn)
  if S.modal then
    if btn == "a" then local m = S.modal; S.modal = nil; m.yes() elseif btn == "b" then S.modal = nil end
    return
  end
  if S.view then
    local maxs = math.max(0, #S.view.lines - 12)
    if btn == "b" or btn == "a" then S.view = nil
    elseif btn == "up" then S.view.scroll = math.max(0, S.view.scroll - 1)
    elseif btn == "down" then S.view.scroll = math.min(maxs, S.view.scroll + 1)
    elseif btn == "left" then S.view.scroll = math.max(0, S.view.scroll - 12)
    elseif btn == "right" then S.view.scroll = math.min(maxs, S.view.scroll + 12) end
    return
  end
  if S.login then
    if btn == "b" or btn == "a" then login_cancel() end
    return
  end
  if btn == "l" or btn == "left" then S.tab = (S.tab - 2) % #TABS + 1
  elseif btn == "r" or btn == "right" then S.tab = S.tab % #TABS + 1
  elseif btn == "up" then move(-1)
  elseif btn == "down" then move(1)
  elseif btn == "a" or btn == "x" then
    local c = content()
    local list = selectable(c)
    local row = c.rows[list[math.min(S.sel[S.tab], #list)] or 0]
    if row then
      if btn == "a" and row.action then row.action()
      elseif btn == "x" and row.alt then row.alt() end
    end
  elseif btn == "y" then refresh(); toast("Refreshing...") end
end

local KEYMAP, PADMAP = input.KEYMAP, input.PADMAP

function love.keypressed(key)
  if key == "f10" then love.event.quit() return end
  -- keyboard stand-in for the SELECT+START exit: Ctrl+Q
  if key == "q" and (love.keyboard.isDown("lctrl") or love.keyboard.isDown("rctrl")) then love.event.quit() return end
  if KEYMAP[key] then
    -- keyboard keys already carry the label you read, so undo the Nintendo swap for them
    local b = KEYMAP[key]
    button(S.nintendo and swap(b) or b)
  end
end

function love.gamepadpressed(joy, b)
  if b == "start" or b == "back" then
    if input.quit_combo(joy:isGamepadDown("start"), joy:isGamepadDown("back")) then love.event.quit() end
    return
  end
  if PADMAP[b] then button(PADMAP[b]) end
end

local held = { dir = nil, t = 0 }
local function held_dir()
  local kb = love.keyboard.isDown
  if kb("up") then return "up" elseif kb("down") then return "down" end
  for _, j in ipairs(love.joystick.getJoysticks()) do
    if j:isGamepad() then
      if j:isGamepadDown("dpup") then return "up" elseif j:isGamepadDown("dpdown") then return "down" end
    end
  end
end

-- ------------------------------------------------------------------ drawing
local lg = love.graphics
local col = I.col

local function text(str, x, y, font, color, limit, align)
  lg.setFont(F[font or "body"])
  col(color or T().text)
  if limit then lg.printf(str, x, y, limit, align or "left") else lg.print(str, x, y) end
end

local function fit(str, font, width)
  local f = F[font]
  if f:getWidth(str) <= width then return str end
  while #str > 1 and f:getWidth(str .. "...") > width do str = str:sub(1, -2) end
  return str .. "..."
end

local function tone(name)
  local t = T()
  return ({ ok = t.ok, bad = t.bad, warn = t.warn, primary = t.primaryText })[name] or t.text
end

local function draw_header()
  local t = T()
  col(t.card); lg.rectangle("fill", 0, 0, W, 52)
  col(t.border); lg.rectangle("fill", 0, 51, W, 1)
  I.logo(16, 12, 28, t.text)
  text("Rt:Tailscale-M", 54, 14, "title", t.text)
  -- connection pill
  local st = S.status
  local label, kind = model.state_label(st and st.state or S.summary.backend, S.summary.daemon == "1" or FAKE ~= nil)
  local map = { ok = { t.okBg, t.ok }, bad = { t.badBg, t.bad }, warn = { t.warnBg, t.warn } }
  local bgc, fgc = map[kind][1], map[kind][2]
  local txt = label:sub(1, 1) .. label:sub(2):lower()
  local pw = F.small:getWidth(txt) + 34
  I.pill(W - pw - 14, 13, pw, 26, bgc, nil)
  I.dot(W - pw - 14 + 14, 26, 4, fgc)
  text(txt, W - pw - 14 + 25, 18, "small", fgc)
end

local function draw_tabs()
  local t = T()
  col(t.card); lg.rectangle("fill", 0, 52, W, 38)
  col(t.border); lg.rectangle("fill", 0, 89, W, 1)
  local x0, tw = 40, (W - 80) / #TABS
  for i, tb in ipairs(TABS) do
    local on = i == S.tab
    local cx = x0 + (i - 0.5) * tw
    local c = on and t.primaryText or t.muted
    I.tab(tb[2], cx - F.small:getWidth(tb[1]) / 2 - 12, 71, 16, c)
    text(tb[1], cx - F.small:getWidth(tb[1]) / 2 + 2, 63, "small", c)
    if on then col(t.primary); lg.rectangle("fill", cx - tw / 2 + 8, 87, tw - 16, 3, 1.5, 1.5) end
  end
  I.shoulder(8, 62, 24, 18, "L", t, F.btn)
  I.shoulder(W - 32, 62, 24, 18, "R", t, F.btn)
end

local function draw_footer()
  local t = T()
  col(t.card); lg.rectangle("fill", 0, 444, W, 36)
  col(t.border); lg.rectangle("fill", 0, 444, W, 1)
  local entries
  if S.modal then entries = { { btn = "A", glyph = "check" }, { btn = "B", glyph = "cross" } }
  elseif S.view then entries = { { btn = "dpad", glyph = nil }, { btn = "B", glyph = "back" } }
  elseif S.login then entries = { { btn = "B", glyph = "cross" } }
  else
    entries = { { btn = "dpad" }, { btn = "A", glyph = "check" }, { btn = "Y", glyph = "refresh" }, { btn = "LR", glyph = nil } }
    if S.tab == 2 then table.insert(entries, 3, { btn = "X", glyph = "exitnode" }) end
  end
  local x = 14
  for _, e in ipairs(entries) do x = I.legend_entry(x, 452, e, t, F.btn) end
  if not S.modal and not S.view and not S.login then
    I.legend_entry(W - 112, 452, { btn = "combo", glyph = "power" }, t, F.btn)
  end
  if S.toast and S.toast.untilT > S.time then
    local tc = ({ ok = t.ok, bad = t.bad, warn = t.warn })[S.toast.kind] or t.text
    local tw = F.small:getWidth(S.toast.text) + 28
    local bgc = ({ ok = t.okBg, bad = t.badBg, warn = t.warnBg })[S.toast.kind] or t.card
    I.pill(W / 2 - tw / 2, 406, tw, 28, bgc, tc)
    text(S.toast.text, W / 2 - tw / 2, 411, "small", tc, tw, "center")
  end
end

local function row_height(r)
  if r.kind == "hero" then return 104 end
  if r.kind == "header" then return 28 end
  if r.kind == "pin" then return 56 end
  if r.kind == "peer" then return 50 end
  if r.kind == "toggle" then return 46 end
  return 38
end

local function draw_row(r, x, y, w, on, t)
  local h = row_height(r)
  if r.kind == "header" then
    text(r.label:upper(), x + 4, y + 10, "tiny", t.muted)
    return
  end
  local fill, border = t.card, t.border
  if on then fill, border = t.primaryBg, t.ring end
  I.card(x, y, w, h - 4, fill, border, 8)
  if r.kind == "hero" then
    text(fit(r.name, "big", w - 190), x + 16, y + 12, "big", t.text)
    text(fit(r.sub, "body", w - 190), x + 16, y + 46, "body", t.muted)
    if r.tailnet then text(fit(r.tailnet, "small", w - 190), x + 16, y + 70, "small", t.muted) end
    if r.mode == "switch" then
      I.switch(x + w - 78, y + 22, 54, 30, r.on, t)
      text(r.label, x + w - 170, y + 58, "small", r.on and t.ok or t.muted, 146, "right")
    elseif r.mode == "button" then
      local label = r.label or "Cancel"
      I.card(x + w - 130, y + 26, 110, 38, t.primary, nil, 8)
      text(label, x + w - 130, y + 36, "strong", t.onPrimary, 110, "center")
    else
      text(r.label or "", x + w - 190, y + 36, "body", t.muted, 170, "right")
    end
  elseif r.kind == "info" then
    text(r.label, x + 14, y + 9, "small", t.muted)
    text(fit(tostring(r.value), "body", w - 150), x + 130, y + 7, "body", tone(r.tone), w - 150 - 14, "right")
  elseif r.kind == "pin" then
    text("PIN", x + 14, y + 20, "small", t.muted)
    local bx = x + 70
    local pin = r.pin or "------"
    for i = 1, #pin do
      I.card(bx + (i - 1) * 34, y + 8, 30, 38, t.bg, t.border2, 6)
      text(pin:sub(i, i), bx + (i - 1) * 34, y + 14, "title", t.text, 30, "center")
    end
  elseif r.kind == "peer" then
    local p = r.peer
    I.dot(x + 20, y + 21, 5, p.online and t.ok or t.disabled)
    text(fit(p.name, "strong", w - 230), x + 36, y + 6, "strong", p.online and t.text or t.muted)
    text((p.ips[1] or "") .. (p.os ~= "" and ("  -  " .. p.os) or ""), x + 36, y + 26, "small", t.muted)
    if p.exit then
      I.pill(x + w - 120, y + 12, 108, 22, t.primaryBg, t.ring)
      text("Exit node", x + w - 120, y + 16, "small", t.primaryText, 108, "center")
    elseif p.exitOption then
      text("Exit node ready", x + w - 150, y + 16, "small", t.muted, 138, "right")
    end
  elseif r.kind == "toggle" then
    text(r.label, x + 14, y + 6, "body", t.text)
    text(fit(r.desc or "", "small", w - 110), x + 14, y + 25, "small", t.muted)
    I.switch(x + w - 58, y + 9, 42, 24, r.on, t)
  else -- action
    local c = r.danger and t.bad or t.text
    local lx = x + 14
    if r.glyph then I.glyph(r.glyph, x + 26, y + 17, 18, c); lx = x + 44 end
    text((r.current and "- " or "") .. fit(r.label, "body", w - 60), lx, y + 9, "body", c)
    if not r.current then I.chevron(x + w - 18, y + 17, 10, t.disabled) end
  end
end

local function draw_content()
  local t = T()
  local c = content()
  local rows = c.rows
  local w = c.narrow and (W - 28 - 178) or (W - 28)
  local sellist = selectable(c)
  local sel = math.min(S.sel[S.tab], math.max(#sellist, 1))
  S.sel[S.tab] = sel
  local selrow = sellist[sel]

  -- vertical layout and scrolling
  local y, ys = 0, {}
  for i, r in ipairs(rows) do ys[i] = y; y = y + row_height(r) end
  local total = y
  local view = BOTTOM - TOP
  local sc = S.scroll[S.tab]
  if selrow then
    local top, bot = ys[selrow], ys[selrow] + row_height(rows[selrow])
    if top < sc then sc = top elseif bot > sc + view then sc = bot - view end
  end
  sc = math.max(0, math.min(sc, math.max(0, total - view)))
  S.scroll[S.tab] = sc

  lg.setScissor(0, TOP, W, BOTTOM - TOP)
  local x = 14
  for i, r in ipairs(rows) do
    local ry = TOP + ys[i] - sc
    if ry + row_height(r) > TOP and ry < BOTTOM then
      draw_row(r, x, ry, w, r.action ~= nil and i == selrow, t)
    end
  end
  if #rows == 0 or c.empty then
    text(c.empty or "Nothing here yet.", 14, TOP + 14, "body", t.muted, W - 28, "center")
  end
  lg.setScissor()

  -- scroll hint
  if total > view then
    local bh = math.max(24, view * view / total)
    col(t.border2); lg.rectangle("fill", W - 5, TOP + (view - bh) * (sc / (total - view)), 3, bh, 1.5, 1.5)
  end

  -- QR of the selected panel address, on the right
  if c.qr then
    I.card(W - 178, TOP, 164, 188, t.card, t.border, 8)
    local ok, m, size = qr.encode(c.qr)
    if ok then
      local quiet = 2
      local px = math.max(2, math.floor(140 / (size + quiet * 2)))
      local tot = (size + quiet * 2) * px
      local ox, oy = W - 178 + (164 - tot) / 2, TOP + 12
      lg.setColor(1, 1, 1); lg.rectangle("fill", ox, oy, tot, tot)
      lg.setColor(0, 0, 0)
      for r = 1, size do
        for cc = 1, size do
          if m[r][cc] then lg.rectangle("fill", ox + (cc - 1 + quiet) * px, oy + (r - 1 + quiet) * px, px, px) end
        end
      end
    end
    text("Scan to open the panel", W - 178, TOP + 160, "tiny", t.muted, 164, "center")
  end
  if S.tab == 2 and S.pingResult then text(fit(S.pingResult, "small", W - 28), 14, BOTTOM + 2, "small", t.primaryText) end
end

-- ------------------------------------------------------------------ overlays
local function dim()
  local t = T()
  lg.setColor(t.shadow[1], t.shadow[2], t.shadow[3], t.shadow[4]); lg.rectangle("fill", 0, 0, W, H)
end

local function draw_modal()
  local t = T()
  dim()
  I.card(70, 150, W - 140, 170, t.card, t.border, 12)
  local y = 172
  for _, l in ipairs(model.wrap(S.modal.text, 44)) do
    text(l, 94, y, "body", t.text, W - 188)
    y = y + 22
  end
  -- the two answers, as controller buttons
  local lbl = S.nintendo and { "A", "B" } or { "A", "B" }
  I.card(W / 2 - 120, 272, 108, 34, t.primary, nil, 8)
  I.face(W / 2 - 96, 289, 11, lbl[1], t, F.btn)
  I.glyph("check", W / 2 - 60, 289, 20, t.onPrimary)
  I.card(W / 2 + 12, 272, 108, 34, t.btnFace, t.border2, 8)
  I.face(W / 2 + 36, 289, 11, lbl[2], t, F.btn)
  I.glyph("cross", W / 2 + 72, 289, 20, t.glyph)
end

local function draw_login()
  local t = T()
  dim()
  I.card(40, 60, W - 80, 360, t.card, t.border, 12)
  I.logo(60, 76, 30, t.text)
  text("Log in to Tailscale", 100, 78, "title", t.text)
  local url = S.status and S.status.authUrl
  if not url then
    text("Waiting for the login link...", 60, 150, "body", t.text)
    text("The device needs a network connection to reach the Tailscale servers.", 60, 180, "small", t.muted, W - 140)
    return
  end
  local ok, m, size = qr.encode(url)
  local px, ox, oy = 6, 60, 128
  if ok then
    px = math.max(2, math.floor(260 / (size + 6)))
    local tot = (size + 6) * px
    lg.setColor(1, 1, 1); lg.rectangle("fill", ox, oy, tot, tot, 6, 6)
    lg.setColor(0, 0, 0)
    for r = 1, size do
      for cc = 1, size do
        if m[r][cc] then lg.rectangle("fill", ox + (cc - 1 + 3) * px, oy + (r - 1 + 3) * px, px, px) end
      end
    end
    ox = ox + tot + 20
  end
  text("Scan with your phone", ox, 132, "strong", t.text)
  text("or open this address:", ox, 154, "small", t.muted)
  local y = 180
  for _, l in ipairs(model.wrap(url, 24)) do text(l, ox, y, "small", t.primaryText); y = y + 18 end
  text("This closes by itself once you are connected.", ox, y + 14, "small", t.muted, W - ox - 56)
end

local function draw_view()
  local t = T()
  dim()
  I.card(20, 56, W - 40, 372, t.card, t.border, 12)
  text(S.view.title, 40, 66, "strong", t.text)
  text(("%d / %d"):format(math.min(#S.view.lines, S.view.scroll + 12), #S.view.lines), W - 100, 68, "small", t.muted)
  local y = 98
  for i = S.view.scroll + 1, math.min(#S.view.lines, S.view.scroll + 12) do
    local l = S.view.lines[i]
    local c = t.text
    if l:match("^%[FAIL%]") then c = t.bad elseif l:match("^%[WARN%]") then c = t.warn elseif l:match("^%[ OK %]") then c = t.ok end
    text(fit(l, "small", W - 90), 40, y, "small", c)
    y = y + 26
  end
end

-- documentation image: every controller icon with its meaning (only used by the README renderer)
local function draw_sheet()
  local t = T()
  col(t.bg); lg.rectangle("fill", 0, 0, W, H)
  I.card(20, 20, W - 40, H - 40, t.card, t.border, 12)
  text("Controls", 44, 32, "title", t.text)
  local items = {
    { { btn = "dpad" }, "Move up / down" },
    { { btn = "LR" }, "Previous / next tab (also D-pad left / right)" },
    { { btn = "A", glyph = "check" }, "Select, toggle, confirm" },
    { { btn = "B", glyph = "back" }, "Back, close, cancel" },
    { { btn = "X", glyph = "exitnode" }, "Use the highlighted device as exit node" },
    { { btn = "Y", glyph = "refresh" }, "Refresh now" },
    { { btn = "combo", glyph = "power" }, "Quit (hold both)" },
  }
  local y = 84
  for _, it in ipairs(items) do
    I.legend_entry(48, y, it[1], t, F.btn)
    text(it[2], 190, y, "body", t.text)
    y = y + 44
  end
end

function love.draw()
  lg.setCanvas(canvas)
  local t = T()
  col(t.bg); lg.rectangle("fill", 0, 0, W, H)
  if S.sheet then
    draw_sheet()
  else
    draw_content()
    draw_header()
    draw_tabs()
    draw_footer()
    if S.login then draw_login() end
    if S.view then draw_view() end
    if S.modal then draw_modal() end
  end
  lg.setCanvas()

  lg.clear(0, 0, 0, 1)
  local ww, wh = lg.getDimensions()
  local sc = math.min(ww / W, wh / H)
  lg.setColor(1, 1, 1, 1)
  lg.draw(canvas, (ww - W * sc) / 2, (wh - H * sc) / 2, 0, sc, sc)
end

-- ------------------------------------------------------------------ lifecycle
local demo
local function demo_steps(real)
  if real then -- against the real daemon: "Log in" must really start `tailscale up`
    return {
      { name = "status", fn = function() S.tab = 1 end, wait = 2 },
      { name = "login-real", fn = login_start, wait = 4 },
    }
  end
  local function tab(n, sel) return function() S.view, S.login, S.modal, S.sheet = nil, nil, nil, false; S.tab = n; S.sel[n] = sel or 1 end end
  return {
    { name = "status", fn = tab(1) },
    { name = "peers", fn = tab(2) },
    { name = "settings", fn = tab(3, 1) },
    { name = "panel", fn = tab(4) },
    { name = "system", fn = tab(5, 5) },
    { name = "dark-status", fn = function() S.modal = nil; S.theme = "dark"; S.tab = 1 end },
    { name = "dark-peers", fn = function() S.tab = 2; S.sel[2] = 2 end },
    { name = "dark-settings", fn = function() S.tab = 3; S.sel[3] = 1 end },
    { name = "diagnostics", fn = function()
      S.theme = "light"
      S.tab = 5
      S.view = { title = "Diagnostics", scroll = 0, lines = {
        "Rt:Tailscale-M 0.1.0", "muOS Andromeda", "[ OK ] tailscale binaries present", "[ OK ] python3 present (web panel)",
        "[ OK ] /dev/net/tun present (TUN mode)", "[ OK ] start at boot: init script installed", "[ OK ] tailscaled running",
        "[ OK ] web panel running", "[ OK ] watchdog running" } }
    end },
    { name = "login", fn = function()
      S.view = nil; S.tab = 1
      S.login = { started = 0 }
      S.status = model.parse_status(love.filesystem.read("needslogin.json") or "") or S.status
    end },
    { name = "confirm", fn = function()
      S.login = nil; S.tab = 1
      S.modal = { text = "Log this device out? You will need to log in again.", yes = function() end }
    end },
    { name = "controls", fn = function() S.theme = "light"; S.sheet = true end },
  }
end

local function capture(path)
  local data = canvas:newImageData()
  local fd = data:encode("png")
  local f = io.open(path, "wb")
  if f then f:write(fd:getString()); f:close() end
end

function love.load()
  lg.setDefaultFilter("linear", "linear")
  canvas = lg.newCanvas(W, H)
  F.tiny = lg.newFont("fonts/Inter-Regular.otf", 11)
  F.small = lg.newFont("fonts/Inter-Regular.otf", 12)
  F.body = lg.newFont("fonts/Inter-Regular.otf", 14)
  F.strong = lg.newFont("fonts/Inter-SemiBold.otf", 14)
  F.title = lg.newFont("fonts/Inter-SemiBold.otf", 19)
  F.big = lg.newFont("fonts/Inter-SemiBold.otf", 24)
  F.btn = lg.newFont("fonts/Inter-SemiBold.otf", 11)

  FAKE = os.getenv("RTTS_FAKE_DIR")
  if FAKE == "" then FAKE = nil end
  APP = os.getenv("RTTS_DIR")
  if not APP or APP == "" then
    local src = love.filesystem.getSource()
    APP = (src:gsub("/%.?game/?$", ""):gsub("/ui/?$", ""):gsub("/+$", ""))
  end
  RT, TS = APP .. "/rt", APP .. "/ts"
  TMP = os.getenv("RT_RUN") or "/tmp/rttailscale"
  os.execute("mkdir -p " .. sq(TMP))
  load_settings()
  if os.getenv("RTTS_THEME") and themes[os.getenv("RTTS_THEME")] then S.theme = os.getenv("RTTS_THEME") end
  refresh()

  local prefix = os.getenv("RTTS_DEMO")
  if prefix and prefix ~= "" then
    if FAKE then
      local f = io.open(FAKE .. "/status_needslogin.json")
      if f then love.filesystem.write("needslogin.json", f:read("*a")); f:close() end
    end
    local real = os.getenv("RTTS_DEMO_REAL") == "1"
    demo = { prefix = prefix, steps = demo_steps(real), i = 0, t = 2.5, real = real }
  end
end

local pollT, refreshT = 0, 0
function love.update(dt)
  S.time = S.time + dt
  pollT = pollT + dt
  if pollT > 0.1 then pollT = 0; poll_jobs() end
  refreshT = refreshT + dt
  if refreshT > (S.login and 1.5 or 4) then
    refreshT = 0
    if not demo or demo.real then refresh() end -- demo mode renders fixed fixtures
  end

  -- close the login screen once connected
  if S.login and S.status and S.status.state == "Running" then S.login = nil; toast("Connected") end

  local d = held_dir()
  if d then
    if held.dir ~= d then held.dir, held.t = d, 0 else
      held.t = held.t + dt
      if held.t > 0.45 then
        held.t = 0.37
        if not S.modal and not S.view and not S.login then move(d == "up" and -1 or 1) end
      end
    end
  else
    held.dir = nil
  end

  if demo then
    demo.t = demo.t - dt
    if demo.t <= 0 then
      if demo.i > 0 then capture(("%s-%02d-%s.png"):format(demo.prefix, demo.i, demo.steps[demo.i].name)) end
      demo.i = demo.i + 1
      if demo.i > #demo.steps then love.event.quit(); return end
      demo.steps[demo.i].fn()
      demo.t = demo.steps[demo.i].wait or 0.5
    end
  end
end
