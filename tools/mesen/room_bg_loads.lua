-- Issue #8 verification: thousands of scene loads (render off -> on, $1CA0
-- 0 -> 1 -> 2 -> 0) via pause submenus (BELONGINGS, LEVEL with skill changes
-- Intermediate/Gamer/..., STATUS) and returns to the street, interleaved with
-- walking/fighting. Row invariant checked every frame; 30 frames after each
-- load every clean visible row must equal the shadow conversion.
dofile(os.getenv("RCR_LIB")) dofile(os.getenv("INV_LIB"))
LOADS = tonumber(os.getenv("LOADS") or "1000")
math.randomseed(tonumber(os.getenv("SEED") or "3"))
local prev, loadStart = 0, nil
L = {n=0, blank=0, maxBlank=0, staleAfter=0, checks=0}
local pend = {}
emu.addEventCallback(function()
  local s = rd(0x1CA0)
  if prev == 0 and s ~= 0 then loadStart = frameNo
  elseif prev ~= 0 and s == 0 and loadStart then
    local len = frameNo - loadStart
    L.n = L.n + 1 L.blank = L.blank + len if len > L.maxBlank then L.maxBlank = len end
    pend[#pend+1] = frameNo + 30 loadStart = nil
  end
  prev = s
  if pend[1] and frameNo >= pend[1] then
    table.remove(pend, 1)
    if rd(0x1CA0) == 0 then
      L.checks = L.checks + 1
      local bad = 0
      for x = 0, 127 do if (x & 31) < 30 and rd(0x1D00 + x) == 0 then local n = rowDiff(x) if n > 0 then bad = bad + 1 end end end
      if bad > 0 then L.staleAfter = L.staleAfter + 1 if L.staleAfter <= 10 then log("STALE-AFTER-LOAD", L.n, "rows", bad, state()) shot("stale"..L.staleAfter) end end
    end
  end
end, emu.eventType.startFrame)
emu.addEventCallback(function() invariantCheck() end, emu.eventType.startFrame)
function tap(b, on) held[b]=true step(on or 8) held[b]=nil step(20) end
function walk(n) for f=1,n do emu.write(0x4BF,0x7F,W) held.right=(f%90)>3 held.y=math.random()<0.1 held.b=math.random()<0.05 step() end held.right=nil held.y=nil held.b=nil end
run(function()
  INV_ACTIVE = false
  if not bootToSettings() then return end
  for n=1,8 do if rd(0x64C)==4 then break end press("right",6,20) end
  if not settingsToStreet() then return end
  INV_ACTIVE = true
  local guard = 0
  while L.n < LOADS and guard < LOADS * 3 do
    guard = guard + 1
    walk(math.random(20, 200))
    if not onStreet() then step(30) end
    tap("start", 4) step(math.random(5, 30))
    local r = math.random()
    if r < 0.45 then
      tap("right") tap("right") tap("a") step(math.random(20, 60))
      for i = 1, math.random(1, 3) do tap("right") end
      tap("start") step(math.random(5, 40))
    elseif r < 0.75 then
      tap("a") step(math.random(20, 60)) tap("start") step(math.random(5, 40))
    elseif r < 0.9 then
      tap("right") tap("right") tap("right") tap("a") step(math.random(20, 60)) tap("start") step(math.random(5, 40))
      tap("left") tap("left") tap("left")
    end
    tap("start", 4)
    if guard % 100 == 0 then log("progress loads", L.n, "checks", L.checks, "stale-after", L.staleAfter, "persist", INV.persist, "skill", rd(0x64C)) end
  end
  log("SUMMARY loads", L.n, "post-load checks", L.checks, "stale after load", L.staleAfter, "persistent invariant violations", INV.persist,
      "avg blank frames", string.format("%.2f", L.blank / math.max(1, L.n)), "max blank", L.maxBlank)
end)
