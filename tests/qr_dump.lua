-- usage: luajit tests/qr_dump.lua <strings.txt>   (run from the repo root)
-- For every line of the input file prints:  HEADER <version> <mask> <size>  followed by the matrix rows (0/1).
package.path = "app/RtTailscale/game/?.lua;" .. package.path
local qr = require("lib.qr")
for line in io.lines(arg[1]) do
  local ok, m, size, info = qr.encode(line)
  if not ok then io.write("ERROR ", tostring(m), "\n")
  else
    io.write(("HEADER %d %d %d\n"):format(info.version, info.mask, size))
    for y = 1, size do
      local r = {}
      for x = 1, size do r[x] = m[y][x] and "1" or "0" end
      io.write(table.concat(r), "\n")
    end
  end
end
