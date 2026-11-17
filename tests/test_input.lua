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

-- Andromeda's primary quit shortcut is MENU (SDL guide) + START.
eq(input.quit_combo(true, false, true), true, "menu + start")
-- Keep SELECT + START as a compatibility fallback.
eq(input.quit_combo(true, true, false), true, "select + start")
eq(input.quit_combo(true, false, false), false, "start alone")
eq(input.quit_combo(false, true, true), false, "menu/select alone")
eq(input.quit_combo(false, false, false), false, "none")

-- L2/R2 trigger axes behave like L1/R1, once per press.
local mapped, down = input.trigger_button("triggerleft", 0.8, false)
eq(mapped, "l", "L2 press"); eq(down, true, "L2 held")
mapped, down = input.trigger_button("triggerleft", 0.9, true)
eq(mapped, nil, "L2 hold does not repeat"); eq(down, true, "L2 remains held")
mapped, down = input.trigger_button("triggerleft", 0.1, true)
eq(mapped, nil, "L2 release"); eq(down, false, "L2 released")
mapped, down = input.trigger_button("triggerright", 0.8, false)
eq(mapped, "r", "R2 press"); eq(down, true, "R2 held")
mapped, down = input.trigger_button("unknown", 1.0, false)
eq(mapped, nil, "unknown axis"); eq(down, nil, "unknown axis state")
eq(input.PADMAP.start, nil, "start has no other meaning"); eq(input.PADMAP.back, nil, "select has no other meaning")
print("input tests passed")
