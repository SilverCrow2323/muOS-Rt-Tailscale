-- tests/fuzz_json.lua — 10 000 random inputs, must never crash
package.path = "app/RtTailscale/game/?.lua;" .. package.path
local json = require("lib.json")
math.randomseed(42)
local alphabet = "{}[]\",:0123456789truefalsnul\\uABCDEFghij \t\r\n"
local crashes = 0
for i = 1, 10000 do
  local len = math.random(0, 200)
  local s = {}
  for j = 1, len do
    local k = math.random(#alphabet)
    s[j] = alphabet:sub(k, k)
  end
  local ok = pcall(json.decode, table.concat(s))
  if not ok then crashes = crashes + 1 end
end
if crashes > 0 then
  io.stderr:write(("FAIL: %d crashes out of 10000\n"):format(crashes))
  os.exit(1)
end
print("fuzz_json: 10000 inputs, no crashes")
