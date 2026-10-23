-- Type a 33-char NES password on the pause PASSWORD screen (4305 layout).
-- Grid: rows 0-4 letters (A a B b ... per row 5 letters), row 0 cols 10/11 = Z z,
-- row 5 digits 0-9; col 10 rows 1-5 = AHEAD BACK ERASE SWAP END.
local function cell(ch)
  if ch == "Z" then return 0, 10 elseif ch == "z" then return 0, 11 end
  local b = ch:byte()
  if b >= 48 and b <= 57 then return 5, b - 48 end
  local up = b >= 65 and b <= 89
  local i = up and (b - 65) or (b - 97)
  return i // 5, 2 * (i % 5) + (up and 0 or 1)
end
local function tap(b) press(b, 5, 9) end
local cr, cc = 0, 0
local function go(r, c)
  local function vert() while cr < r do tap("down") cr = cr + 1 end while cr > r do tap("up") cr = cr - 1 end end
  local function horiz() while cc < c do tap("right") cc = cc + 1 end while cc > c do tap("left") cc = cc - 1 end end
  if cc >= 10 then horiz() vert() else vert() horiz() end
end
function typePassword(pw)
  pw = pw:gsub("%s", "")
  -- open: pause -> right (PASSWORD) -> A, wait for the current password to finish drawing
  openPause() menuTo(1) shot("pw_menu") press("a", 6, 20) step(200) shot("pw_open")
  cr, cc = 0, 0
  for i = 1, #pw do local r, c = cell(pw:sub(i, i)) go(r, c) tap("a") end
  step(10) shot("pw_typed")
  go(5, 10) tap("a") step(120)
end
function unpause() for i = 1, 6 do if rd(0x3F) == 0 then return true end press("start", 6, 60) end return rd(0x3F) == 0 end
function enterPassword(pw)
  typePassword(pw) press("b", 6, 90) press("start", 6, 90) press("b", 6, 90) press("start", 6, 90)
  return unpause() and waitUntil(onStreet, 300)
end
-- pause menu cursor is $06D0 (0 BELONGINGS, 1 PASSWORD, 2 LEVEL, 3 STATUS, 4 HELP)
function menuTo(item)
  for i = 1, 8 do local c = rd(0x6D0) if c == item then return true end press(c < item and "right" or "left", 6, 30) end
  return rd(0x6D0) == item
end
-- pause -> LEVEL -> Right until $064C == skill -> Start (menu) -> unpause
function openPause()
  for k in pairs(held) do held[k] = nil end
  for i = 1, 8 do if rd(0x3F) ~= 0 then step(20) return true end press("start", 6, 40) end
  return rd(0x3F) ~= 0
end
function setSkill(skill)
  openPause()
  if rd(0x3F) == 0 or not menuTo(2) then unpause() return false end
  press("a", 6, 90)
  for i = 1, 8 do if rd(0x64C) == skill then break end press("right", 6, 30) end
  local ok = rd(0x64C) == skill
  press("start", 6, 90) unpause()
  return ok and rd(0x3F) == 0
end
