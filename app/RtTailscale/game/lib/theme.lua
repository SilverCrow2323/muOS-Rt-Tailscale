-- Colours taken from the Tailscale web client (client/web/src/index.css in github.com/tailscale/tailscale,
-- BSD-3-Clause): warm greys, blue-500 = rgb(75,112,204), green-300 = rgb(30,166,114)...
-- "light" is what the web client looks like; "dark" is the same ramps turned around.
local function c(r, g, b) return { r / 255, g / 255, b / 255 } end

local themes = {
  light = {
    name = "light",
    bg = c(247, 245, 244), card = c(255, 255, 255), border = c(238, 235, 234), border2 = c(218, 214, 213),
    text = c(35, 34, 34), muted = c(112, 110, 109), disabled = c(175, 172, 171),
    primary = c(75, 112, 204), primaryText = c(63, 93, 179), primaryBg = c(240, 245, 255), ring = c(108, 148, 236),
    ok = c(30, 166, 114), okBg = c(239, 255, 237), warn = c(217, 121, 23), warnBg = c(252, 249, 233),
    bad = c(208, 72, 65), badBg = c(255, 246, 244), badText = c(148, 8, 33),
    switchOff = c(218, 214, 213), knob = c(255, 255, 255), onPrimary = c(255, 255, 255),
    glyph = c(68, 67, 66), btnFace = c(238, 235, 234), btnText = c(46, 45, 45), shadow = { 0, 0, 0, 0.35 },
  },
  dark = {
    name = "dark",
    bg = c(31, 30, 30), card = c(46, 45, 45), border = c(68, 67, 66), border2 = c(112, 110, 109),
    text = c(247, 245, 244), muted = c(175, 172, 171), disabled = c(112, 110, 109),
    primary = c(108, 148, 236), primaryText = c(173, 199, 252), primaryBg = c(37, 53, 112), ring = c(133, 170, 245),
    ok = c(51, 194, 127), okBg = c(8, 36, 41), warn = c(239, 192, 120), warnBg = c(58, 22, 7),
    bad = c(246, 143, 135), badBg = c(66, 0, 0), badText = c(255, 177, 171),
    switchOff = c(68, 67, 66), knob = c(247, 245, 244), onPrimary = c(25, 34, 74),
    glyph = c(218, 214, 213), btnFace = c(68, 67, 66), btnText = c(247, 245, 244), shadow = { 0, 0, 0, 0.55 },
  },
}

return themes
