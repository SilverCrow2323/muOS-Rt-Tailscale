-- Button mapping, free of any LÖVE API so it can be unit-tested (tests/test_input.lua).
--
-- SDL names buttons by POSITION: "a" = bottom, "b" = right, "x" = left, "y" = top.
-- Nintendo-style handhelds (Anbernic...) print A on the right and B at the bottom, X on top and Y on the left,
-- so both pairs are swapped: the button labelled A must give "a" in the app.
local M = {}

function M.swap(btn, nintendo)
  if nintendo then
    local m = { a = "b", b = "a", x = "y", y = "x" }
    return m[btn] or btn
  end
  return btn
end

--- The app quits only when SELECT ("back" in SDL) and START are held together.
function M.quit_combo(start_down, back_down)
  return (start_down and back_down) and true or false
end

M.KEYMAP = {
  up = "up", down = "down", left = "left", right = "right",
  ["return"] = "a", space = "a", escape = "b", backspace = "b", x = "x", y = "y", z = "y",
  q = "l", pageup = "l", e = "r", pagedown = "r", tab = "r",
}
M.PADMAP = {
  a = "a", b = "b", x = "x", y = "y", dpup = "up", dpdown = "down", dpleft = "left", dpright = "right",
  leftshoulder = "l", rightshoulder = "r",
}
return M
