-- Vector icons drawn with LÖVE primitives (no image files needed, crisp at any scale).
--
-- logo(): the 9-dot Tailscale mark, geometry copied UNMODIFIED from
--         client/web/src/assets/icons/tailscale-icon.svg (github.com/tailscale/tailscale, BSD-3-Clause).
--         "Tailscale" and its logo are trademarks of Tailscale Inc.; this project is not affiliated with them.
local lg = love.graphics
local I = {}

-- ---------------------------------------------------------------- the Tailscale mark
local CX = { 3.8696 / 26, 13.0879 / 26, 22.1919 / 26 }
local CY = { 3.69865 / 26, 12.8599 / 26, 22.1919 / 26 }
local R = 3.0727 / 26
-- opacity per [row][col]: the middle row and the bottom-centre dot are solid, the rest 20 %
local BRIGHT = { { false, false, false }, { true, true, true }, { false, true, false } }

function I.logo(x, y, size, color)
  for row = 1, 3 do
    for col = 1, 3 do
      lg.setColor(color[1], color[2], color[3], BRIGHT[row][col] and 1 or 0.2)
      lg.circle("fill", x + CX[col] * size, y + CY[row] * size, R * size, 24)
    end
  end
end

-- ---------------------------------------------------------------- shapes
local function col(c, a) lg.setColor(c[1], c[2], c[3], a or c[4] or 1) end
I.col = col

function I.card(x, y, w, h, fill, border, r)
  col(fill)
  lg.rectangle("fill", x, y, w, h, r or 8, r or 8)
  if border then
    col(border)
    lg.setLineWidth(1)
    lg.rectangle("line", x + 0.5, y + 0.5, w - 1, h - 1, r or 8, r or 8)
  end
end

function I.dot(x, y, r, color) col(color); lg.circle("fill", x, y, r, 20) end

function I.switch(x, y, w, h, on, T)
  col(on and T.primary or T.switchOff)
  lg.rectangle("fill", x, y, w, h, h / 2, h / 2)
  col(T.knob)
  lg.circle("fill", on and (x + w - h / 2) or (x + h / 2), y + h / 2, h / 2 - 3, 20)
end

function I.pill(x, y, w, h, fill, border)
  I.card(x, y, w, h, fill, border, h / 2)
end

-- ---------------------------------------------------------------- action glyphs (centre cx,cy; size s)
local G = {}
function G.check(cx, cy, s, c) col(c); lg.setLineWidth(s * 0.16); lg.line(cx - s * .32, cy + s * .02, cx - s * .08, cy + s * .26, cx + s * .34, cy - s * .24) end
function G.back(cx, cy, s, c)
  col(c); lg.setLineWidth(s * 0.14)
  lg.line(cx + s * .30, cy - s * .22, cx + s * .30, cy + s * .10, cx - s * .10, cy + s * .10)
  lg.polygon("fill", cx - s * .34, cy + s * .10, cx - s * .06, cy - s * .08, cx - s * .06, cy + s * .28)
end
function G.cross(cx, cy, s, c) col(c); lg.setLineWidth(s * 0.14); lg.line(cx - s * .26, cy - s * .26, cx + s * .26, cy + s * .26); lg.line(cx + s * .26, cy - s * .26, cx - s * .26, cy + s * .26) end
function G.refresh(cx, cy, s, c)
  col(c); lg.setLineWidth(s * 0.13)
  lg.arc("line", "open", cx, cy, s * .30, math.rad(-60), math.rad(220), 24)
  local ax, ay = cx + math.cos(math.rad(-60)) * s * .30, cy + math.sin(math.rad(-60)) * s * .30
  lg.polygon("fill", ax - s * .06, ay - s * .20, ax + s * .24, ay + s * .02, ax - s * .14, ay + s * .12)
end
function G.power(cx, cy, s, c)
  col(c); lg.setLineWidth(s * 0.13)
  lg.arc("line", "open", cx, cy + s * .02, s * .30, math.rad(-55), math.rad(235), 24)
  lg.line(cx, cy - s * .38, cx, cy - s * .04)
end
function G.exitnode(cx, cy, s, c) -- arrow leaving a box = "use as exit node"
  col(c); lg.setLineWidth(s * 0.12)
  lg.line(cx - s * .08, cy - s * .30, cx - s * .32, cy - s * .30, cx - s * .32, cy + s * .30, cx - s * .08, cy + s * .30)
  lg.line(cx - s * .12, cy, cx + s * .26, cy)
  lg.polygon("fill", cx + s * .34, cy, cx + s * .12, cy - s * .16, cx + s * .12, cy + s * .16)
end
function G.tabs(cx, cy, s, c)
  col(c); lg.setLineWidth(s * 0.13)
  lg.line(cx - s * .08, cy - s * .26, cx - s * .30, cy, cx - s * .08, cy + s * .26)
  lg.line(cx + s * .08, cy - s * .26, cx + s * .30, cy, cx + s * .08, cy + s * .26)
end
function G.move(cx, cy, s, c)
  col(c)
  lg.polygon("fill", cx, cy - s * .36, cx - s * .16, cy - s * .16, cx + s * .16, cy - s * .16)
  lg.polygon("fill", cx, cy + s * .36, cx - s * .16, cy + s * .16, cx + s * .16, cy + s * .16)
end
I.glyph = function(name, cx, cy, s, c) if G[name] then G[name](cx, cy, s, c) end end

-- ---------------------------------------------------------------- controller button icons
function I.face(x, y, r, letter, T, font)   -- A / B / X / Y
  col(T.btnFace); lg.circle("fill", x, y, r, 24)
  col(T.border2); lg.setLineWidth(1); lg.circle("line", x, y, r, 24)
  lg.setFont(font); col(T.btnText)
  lg.printf(letter, x - r, y - font:getHeight() / 2 + 1, r * 2, "center")
end

function I.dpad(x, y, s, T)
  col(T.btnFace)
  local t = s * 0.36
  lg.rectangle("fill", x - t / 2, y - s / 2, t, s, 3, 3)
  lg.rectangle("fill", x - s / 2, y - t / 2, s, t, 3, 3)
  col(T.border2); lg.setLineWidth(1)
  lg.rectangle("line", x - t / 2 + .5, y - s / 2 + .5, t, s, 3, 3)
  lg.rectangle("line", x - s / 2 + .5, y - t / 2 + .5, s, t, 3, 3)
  col(T.btnText)
  local a = s * 0.17
  lg.polygon("fill", x, y - s * .40, x - a, y - s * .22, x + a, y - s * .22)
  lg.polygon("fill", x, y + s * .40, x - a, y + s * .22, x + a, y + s * .22)
  lg.polygon("fill", x - s * .40, y, x - s * .22, y - a, x - s * .22, y + a)
  lg.polygon("fill", x + s * .40, y, x + s * .22, y - a, x + s * .22, y + a)
end

function I.shoulder(x, y, w, h, letter, T, font)   -- L / R
  I.card(x, y, w, h, T.btnFace, T.border2, h / 2)
  lg.setFont(font); col(T.btnText)
  lg.printf(letter, x, y + (h - font:getHeight()) / 2 + 1, w, "center")
end

function I.startpill(x, y, w, h, kind, T)      -- kind = "start" | "select"
  I.card(x, y, w, h, T.btnFace, T.border2, h / 2)
  col(T.btnText)
  if kind == "start" then
    lg.polygon("fill", x + w / 2 - h * .14, y + h * .26, x + w / 2 - h * .14, y + h * .74, x + w / 2 + h * .26, y + h / 2)
  else
    lg.setLineWidth(1.5)
    lg.line(x + w * .3, y + h * .38, x + w * .7, y + h * .38)
    lg.line(x + w * .3, y + h * .62, x + w * .7, y + h * .62)
  end
end

--- Legend entry: a controller button followed by what it does. Returns the x after the entry.
--  e = { btn = "A"|"B"|"X"|"Y"|"L"|"R"|"dpad"|"combo", glyph = "check"|... }
function I.legend_entry(x, y, e, T, font)
  local h = 20
  if e.btn == "dpad" then I.dpad(x + 11, y + h / 2, 21, T); x = x + 25
  elseif e.btn == "combo" then
    I.startpill(x, y + 2, 26, 16, "select", T)
    col(T.muted); lg.setFont(font); lg.print("+", x + 29, y + 1)
    I.startpill(x + 40, y + 2, 26, 16, "start", T)
    x = x + 72
  elseif e.btn == "LR" then
    I.shoulder(x, y + 1, 24, 18, "L", T, font)
    I.shoulder(x + 28, y + 1, 24, 18, "R", T, font)
    x = x + 56
  else I.face(x + 10, y + h / 2, 10, e.btn, T, font); x = x + 24 end
  if e.glyph then
    I.glyph(e.glyph, x + 9, y + h / 2, 18, T.glyph)
    x = x + 20
  end
  return x + 12
end

-- tab icons (small, 18 px box with centre cx,cy)
local TAB = {}
function TAB.status(cx, cy, s, c) col(c); lg.setLineWidth(1.6); lg.circle("line", cx, cy, s * .40, 24); lg.circle("fill", cx, cy, s * .14, 16) end
function TAB.peers(cx, cy, s, c)
  col(c); lg.setLineWidth(1.6)
  lg.rectangle("line", cx - s * .42, cy - s * .36, s * .84, s * .52, 2, 2)
  lg.line(cx - s * .22, cy + s * .34, cx + s * .22, cy + s * .34); lg.line(cx, cy + s * .16, cx, cy + s * .34)
end
function TAB.options(cx, cy, s, c)
  col(c); lg.setLineWidth(1.6)
  lg.line(cx - s * .42, cy - s * .20, cx + s * .42, cy - s * .20); lg.line(cx - s * .42, cy + s * .22, cx + s * .42, cy + s * .22)
  lg.circle("fill", cx - s * .16, cy - s * .20, s * .14, 14); lg.circle("fill", cx + s * .18, cy + s * .22, s * .14, 14)
end
function TAB.panel(cx, cy, s, c)
  col(c); lg.setLineWidth(1.5); lg.circle("line", cx, cy, s * .40, 24)
  lg.ellipse("line", cx, cy, s * .17, s * .40, 20); lg.line(cx - s * .40, cy, cx + s * .40, cy)
end
function TAB.system(cx, cy, s, c)
  col(c); lg.setLineWidth(1.6); lg.circle("line", cx, cy, s * .22, 16)
  for i = 0, 5 do
    local a = i * math.pi / 3
    lg.line(cx + math.cos(a) * s * .30, cy + math.sin(a) * s * .30, cx + math.cos(a) * s * .44, cy + math.sin(a) * s * .44)
  end
end
function I.tab(name, cx, cy, s, c) if TAB[name] then TAB[name](cx, cy, s, c) end end

function I.chevron(x, y, s, c) col(c); lg.setLineWidth(1.8); lg.line(x - s * .25, y - s * .4, x + s * .15, y, x - s * .25, y + s * .4) end

return I
