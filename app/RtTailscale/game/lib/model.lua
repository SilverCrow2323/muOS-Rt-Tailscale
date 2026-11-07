-- Parsing of what the Tailscale CLI / rt print, kept free of any LÖVE API so it can be
-- unit-tested with plain LuaJIT (tests/test_model.lua).
local json = require("lib.json")

local M = {}

--- Parse `rt summary` (key=value lines) into a table of strings.
function M.parse_summary(text)
  local t = {}
  for line in (text or ""):gmatch("[^\r\n]+") do
    local k, v = line:match("^([%w_]+)=(.*)$")
    if k then t[k] = v end
  end
  return t
end

local function is_true(v) return v == true end

--- Parse `tailscale status --json`.
-- Returns { state, authUrl, version, tailnet, magic, health={}, self={}, peers={}, exitNode }
function M.parse_status(text)
  local d = json.decode(text)
  if type(d) ~= "table" then return nil end
  local s = {
    state = d.BackendState or "Unknown",
    authUrl = (type(d.AuthURL) == "string" and d.AuthURL ~= "") and d.AuthURL or nil,
    version = d.Version,
    tailnet = d.CurrentTailnet and d.CurrentTailnet.Name or nil,
    magic = d.MagicDNSSuffix,
    health = d.Health or {},
    peers = {},
  }
  local me = d.Self
  if type(me) == "table" then
    s.self = {
      name = me.HostName, dns = me.DNSName, ips = me.TailscaleIPs or {}, os = me.OS,
      online = is_true(me.Online), exitOption = is_true(me.ExitNodeOption),
    }
  end
  for _, p in pairs(d.Peer or {}) do
    local peer = {
      name = p.HostName or "?", dns = p.DNSName, ips = p.TailscaleIPs or {}, os = p.OS or "",
      online = is_true(p.Online), exit = is_true(p.ExitNode), exitOption = is_true(p.ExitNodeOption),
      lastSeen = p.LastSeen, relay = p.Relay, cur = p.CurAddr,
    }
    s.peers[#s.peers + 1] = peer
    if peer.exit then s.exitNode = peer end
  end
  table.sort(s.peers, function(a, b)
    if a.online ~= b.online then return a.online end
    return (a.name or ""):lower() < (b.name or ""):lower()
  end)
  return s
end

--- Parse `tailscale debug prefs`.
function M.parse_prefs(text)
  local d = json.decode(text)
  if type(d) ~= "table" then return nil end
  local adv_exit = false
  for _, r in ipairs(d.AdvertiseRoutes or {}) do
    if r == "0.0.0.0/0" or r == "::/0" then adv_exit = true end
  end
  return {
    acceptRoutes = is_true(d.RouteAll), acceptDns = is_true(d.CorpDNS), shieldsUp = is_true(d.ShieldsUp),
    ssh = is_true(d.RunSSH), webclient = is_true(d.RunWebClient), advertiseExit = adv_exit,
    hostname = d.Hostname or "", wantRunning = is_true(d.WantRunning), controlUrl = d.ControlURL or "",
  }
end

--- Pick the URLs printed by `rt urls` ("LAN http://..." / "TS  http://...").
function M.parse_urls(text)
  local list = {}
  for line in (text or ""):gmatch("[^\r\n]+") do
    local kind, url = line:match("^(%u+)%s+(https?://%S+)")
    if kind then list[#list + 1] = { kind = kind, url = url } end
  end
  return list
end

--- Word-wrap `s` to lines of at most `n` characters (also breaks long tokens such as URLs).
function M.wrap(s, n)
  local out = {}
  for para in (s .. "\n"):gmatch("(.-)\n") do
    local line = ""
    for word in para:gmatch("%S+") do
      while #word > n do
        if line ~= "" then out[#out + 1] = line; line = "" end
        out[#out + 1] = word:sub(1, n)
        word = word:sub(n + 1)
      end
      if line == "" then line = word
      elseif #line + 1 + #word <= n then line = line .. " " .. word
      else out[#out + 1] = line; line = word end
    end
    out[#out + 1] = line
  end
  return out
end

function M.state_label(state, daemon)
  if daemon == false then return "DAEMON OFF", "bad" end
  local map = {
    Running = { "CONNECTED", "ok" }, Stopped = { "DISCONNECTED", "bad" }, NeedsLogin = { "LOGIN REQUIRED", "warn" },
    Starting = { "CONNECTING...", "warn" }, NoState = { "CONNECTING...", "warn" },
    NeedsMachineAuth = { "WAITING FOR ADMIN", "warn" },
  }
  local m = map[state]
  if m then return m[1], m[2] end
  return tostring(state or "?"):upper(), "warn"
end

return M
