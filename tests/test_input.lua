-- Run from the repo root:  luajit tests/test_input.lua
package.path = "app/RtTailscale/game/?.lua;" .. package.path
local input = require("lib.input")
local function eq(a, b, m) if a ~= b then error(("%s: expected %s, got %s"):format(m, tostring(b), tostring(a))) end end

-- Nintendo layout (default on Anbernic): both pairs are swapped
eq(input.swap("a", true), "b", "a->b"); eq(input.swap("b", true), "a", "b->a")
eq(input.swap("x", true), "y", "x->y"); eq(input.swap("y", true), "x", "y->x")
for _, d in ipairs({ "up", "down", "left", "right", "l", "r" }) do eq(input.swap(d, true), d, d .. " untouched") end
-- layout switched off: nothing changes
for _, b in ipairs({ "a", "b", "x", "y" }) do eq(input.swap(b, false), b, b .. " plain") end
-- swapping twice is the identity
for _, b in ipairs({ "a", "b", "x", "y" }) do eq(input.swap(input.swap(b, true), true), b, b .. " round trip") end

-- quit needs SELECT and START together; START alone must NOT quit
eq(input.quit_combo(true, true), true, "both")
eq(input.quit_combo(true, false), false, "start alone")
eq(input.quit_combo(false, true), false, "select alone")
eq(input.quit_combo(false, false), false, "none")
eq(input.PADMAP.start, nil, "start has no other meaning"); eq(input.PADMAP.back, nil, "select has no other meaning")
print("input tests passed")
