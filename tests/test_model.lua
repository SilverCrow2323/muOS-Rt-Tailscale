-- Run from the repo root: luajit tests/test_model.lua
package.path = "app/RtTailscale/game/?.lua;" .. package.path
local model = require("lib.model")
local function eq(a, b, msg) if a ~= b then error(("%s: expected %s, got %s"):format(msg, tostring(b), tostring(a))) end end

local sm = model.parse_summary("backend=Running\ndaemon=1\npin=123456\nautostart=off\n")
eq(sm.backend, "Running", "summary backend"); eq(sm.pin, "123456", "summary pin")
eq(next(model.parse_summary(nil)), nil, "nil summary")
eq(next(model.parse_summary(42)), nil, "numeric summary")

local f = io.open("tests/fixtures/status_running.json"); local txt = f:read("*a"); f:close()
local st = model.parse_status(txt)
eq(st.state, "Running", "state"); eq(st.tailnet, "pips@example.com", "tailnet")
eq(#st.peers, 4, "peer count"); eq(st.peers[1].name, "desktop-pc", "online peer sorted first")
eq(st.self.ips[1], "100.101.102.103", "self ip"); eq(st.exitNode and st.exitNode.name, "vps-frankfurt", "exit node")
eq(st.peers[4].online, false, "offline last"); eq(st.authUrl, nil, "no auth url when running")

f = io.open("tests/fixtures/status_needslogin.json"); txt = f:read("*a"); f:close()
st = model.parse_status(txt)
eq(st.state, "NeedsLogin", "needs login"); eq(st.authUrl, "https://login.tailscale.com/a/0123456789abcdef", "auth url")
eq(model.parse_status("{broken"), nil, "malformed status JSON")
eq(model.parse_status(nil), nil, "nil status JSON")
local partial = model.parse_status('{"BackendState":"Running","CurrentTailnet":"invalid","Self":"invalid","Peer":"invalid"}')
eq(partial.state, "Running", "partial status")
eq(partial.tailnet, nil, "invalid tailnet ignored")
eq(#partial.peers, 0, "invalid peer collection ignored")

f = io.open("tests/fixtures/prefs.json"); txt = f:read("*a"); f:close()
local pr = model.parse_prefs(txt)
eq(pr.acceptRoutes, true, "routes"); eq(pr.advertiseExit, true, "advertise exit")
eq(pr.ssh, false, "ssh"); eq(pr.hostname, "muos-rg35xx", "hostname")
eq(model.parse_prefs("{broken"), nil, "malformed preferences JSON")
local partial_prefs = model.parse_prefs('{"AdvertiseRoutes":"invalid","Hostname":false}')
eq(partial_prefs.advertiseExit, false, "invalid route list ignored")
eq(partial_prefs.hostname, "", "invalid hostname ignored")

local urls = model.parse_urls("LAN http://192.168.1.50:8077\nTS  http://100.101.102.103:8077\n")
eq(#urls, 2, "urls"); eq(urls[2].kind, "TS", "url kind")
eq(#model.parse_urls(nil), 0, "nil urls")
local w = model.wrap("https://login.tailscale.com/a/0123456789abcdef and some words", 20)
for _, l in ipairs(w) do assert(#l <= 20, "wrap too long: " .. l) end
eq(#model.wrap("safe", 0), 4, "zero width is clamped")
eq(model.state_label("Running"), "CONNECTED", "label")
eq(select(2, model.state_label(nil, false)), "bad", "daemon off class")
print("model tests passed")
