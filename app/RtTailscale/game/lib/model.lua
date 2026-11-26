-- Defensive parsing of Tailscale CLI output; kept free of LÖVE APIs for LuaJIT tests.
local json = require("lib.json")
local M = {}

local function decode_table(text)
  if type(text) ~= "string" then return nil end
  local ok, value = pcall(json.decode, text)
  if not ok or type(value) ~= "table" then return nil end
  return value
end

local function table_or_empty(value)
  return type(value) == "table" and value or {}
end

function M.parse_summary(text)
  local t = {}
  if type(text) ~= "string" then return t end
  for line in text:gmatch("[^\r\n]+") do
    local k, v = line:match("^([%w_]+)=(.*)$")
    if k then t[k] = v end
  end
  return t
end

local function is_true(v) return v == true end

function M.parse_status(text)
  local d = decode_table(text)
  if not d then return nil end
  local current = table_or_empty(d.CurrentTailnet)
  local self_data = table_or_empty(d.Self)
  local s = {
    state = type(d.BackendState) == "string" and d.BackendState or "Unknown",
    authUrl = (type(d.AuthURL) == "string" and d.AuthURL ~= "") and d.AuthURL or nil,
    version = type(d.Version) == "string" and d.Version or nil,
    tailnet = type(current.Name) == "string" and current.Name or nil,
    magic = type(d.MagicDNSSuffix) == "string" and d.MagicDNSSuffix or nil,
    health = table_or_empty(d.Health),
    peers = {},
  }
  if next(self_data) ~= nil then
    s.self = {
      name = self_data.HostName, dns = self_data.DNSName,
      ips = table_or_empty(self_data.TailscaleIPs), os = self_data.OS,
      online = is_true(self_data.Online), exitOption = is_true(self_data.ExitNodeOption),
    }
  else
    s.self = {}
  end
  for _, p in pairs(table_or_empty(d.Peer)) do
    if type(p) == "table" then
      local peer = {
        name = type(p.HostName) == "string" and p.HostName or "?",
        dns = p.DNSName, ips = table_or_empty(p.TailscaleIPs), os = p.OS or "",
        online = is_true(p.Online), exit = is_true(p.ExitNode), exitOption = is_true(p.ExitNodeOption),
        lastSeen = p.LastSeen, relay = p.Relay, cur = p.CurAddr,
      }
      s.peers[#s.peers + 1] = peer
      if peer.exit then s.exitNode = peer end
    end
  end
  table.sort(s.peers, function(a, b)
    if a.online ~= b.online then return a.online end
    return (a.name or ""):lower() < (b.name or ""):lower()
  end)
  return s
end

function M.parse_prefs(text)
  local d = decode_table(text)
  if not d then return nil end
  local adv_exit = false
  for _, route in ipairs(table_or_empty(d.AdvertiseRoutes)) do
    if route == "0.0.0.0/0" or route == "::/0" then adv_exit = true end
  end
  return {
    acceptRoutes = is_true(d.RouteAll), acceptDns = is_true(d.CorpDNS), shieldsUp = is_true(d.ShieldsUp),
    ssh = is_true(d.RunSSH), webclient = is_true(d.RunWebClient), advertiseExit = adv_exit,
    hostname = type(d.Hostname) == "string" and d.Hostname or "",
    wantRunning = is_true(d.WantRunning),
    controlUrl = type(d.ControlURL) == "string" and d.ControlURL or "",
  }
end

function M.parse_urls(text)
  local list = {}
  if type(text) ~= "string" then return list end
  for line in text:gmatch("[^\r\n]+") do
    local kind, url = line:match("^(%u+)%s+(https?://%S+)")
    if kind then list[#list + 1] = { kind = kind, url = url } end
  end
  return list
end

function M.wrap(s, n)
  s = type(s) == "string" and s or tostring(s or "")
  n = tonumber(n) or 1
  n = math.floor(n)
  if n < 1 then n = 1 end
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
