-- Minimal JSON decoder (no encoder needed). LuaJIT / Lua 5.1 compatible.
-- json.decode(str) -> value | nil, errmsg
local json = {}

local escapes = { ['"'] = '"', ['\\'] = '\\', ['/'] = '/', b = '\b', f = '\f', n = '\n', r = '\r', t = '\t' }

local function utf8char(cp)
  if cp < 0x80 then return string.char(cp)
  elseif cp < 0x800 then return string.char(0xC0 + math.floor(cp / 64), 0x80 + cp % 64)
  elseif cp < 0x10000 then
    return string.char(0xE0 + math.floor(cp / 4096), 0x80 + math.floor(cp / 64) % 64, 0x80 + cp % 64)
  end
  return string.char(0xF0 + math.floor(cp / 262144), 0x80 + math.floor(cp / 4096) % 64,
                     0x80 + math.floor(cp / 64) % 64, 0x80 + cp % 64)
end

local function skip(s, i)
  return s:find("[^ \t\r\n]", i) or #s + 1
end

local parse

local function parse_string(s, i)
  local out, j = {}, i + 1
  while true do
    local c = s:sub(j, j)
    if c == "" then error("unterminated string") end
    if c == '"' then return table.concat(out), j + 1 end
    if c == "\\" then
      local e = s:sub(j + 1, j + 1)
      if e == "u" then
        local cp = tonumber(s:sub(j + 2, j + 5), 16)
        if not cp then error("bad \\u escape") end
        j = j + 6
        if cp >= 0xD800 and cp < 0xDC00 and s:sub(j, j + 1) == "\\u" then
          local lo = tonumber(s:sub(j + 2, j + 5), 16)
          if lo and lo >= 0xDC00 and lo < 0xE000 then
            cp = 0x10000 + (cp - 0xD800) * 1024 + (lo - 0xDC00)
            j = j + 6
          end
        end
        out[#out + 1] = utf8char(cp)
      else
        if not escapes[e] then error("bad escape") end
        out[#out + 1] = escapes[e]
        j = j + 2
      end
    else
      local k = s:find('["\\]', j) or #s + 1
      out[#out + 1] = s:sub(j, k - 1)
      j = k
    end
  end
end

function parse(s, i)
  i = skip(s, i)
  local c = s:sub(i, i)
  if c == "{" then
    local t = {}
    i = skip(s, i + 1)
    if s:sub(i, i) == "}" then return t, i + 1 end
    while true do
      i = skip(s, i)
      if s:sub(i, i) ~= '"' then error("expected key at " .. i) end
      local k
      k, i = parse_string(s, i)
      i = skip(s, i)
      if s:sub(i, i) ~= ":" then error("expected ':' at " .. i) end
      t[k], i = parse(s, i + 1)
      i = skip(s, i)
      local d = s:sub(i, i)
      if d == "}" then return t, i + 1 end
      if d ~= "," then error("expected ',' or '}' at " .. i) end
      i = i + 1
    end
  elseif c == "[" then
    local t, n = {}, 0
    i = skip(s, i + 1)
    if s:sub(i, i) == "]" then return t, i + 1 end
    while true do
      n = n + 1
      t[n], i = parse(s, i)
      i = skip(s, i)
      local d = s:sub(i, i)
      if d == "]" then return t, i + 1 end
      if d ~= "," then error("expected ',' or ']' at " .. i) end
      i = i + 1
    end
  elseif c == '"' then
    return parse_string(s, i)
  elseif s:sub(i, i + 3) == "true" then return true, i + 4
  elseif s:sub(i, i + 4) == "false" then return false, i + 5
  elseif s:sub(i, i + 3) == "null" then return nil, i + 4
  else
    local num = s:match("^-?%d+%.?%d*[eE]?[+-]?%d*", i)
    if not num or num == "" then error("unexpected character at " .. i) end
    return tonumber(num), i + #num
  end
end

function json.decode(s)
  if type(s) ~= "string" or s == "" then return nil, "empty" end
  local ok, v = pcall(function()
    local val, i = parse(s, 1)
    i = skip(s, i)
    if i <= #s then error("trailing data at " .. i) end
    return val
  end)
  if not ok then return nil, tostring(v) end
  return v
end

return json
