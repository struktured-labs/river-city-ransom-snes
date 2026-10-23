-- Issue #8 negative control / fix check. Walks right through room loads.
-- INJECT=1: when a load starts ($1CA0 0->1), make every clean visible tilemap
-- row and the BG CHR VRAM wrong (what a dropped/partial upload leaves behind),
-- leaving the game's shadow untouched. A correct load must republish them.
-- Reports, per load: frames with $1CA0 != 0, clean rows still differing from
-- the shadow 30 frames after the load, and a screenshot for pixel comparison.
dofile(os.getenv("RCR_LIB")) dofile(os.getenv("INV_LIB"))
INJECT = os.getenv("INJECT") == "1"
LOADS = tonumber(os.getenv("LOADS") or "3")
local V = emu.memType.snesVideoRam
local prev, loadStart, loads, pending = 0, nil, 0, nil
R = {}
emu.addEventCallback(function()
  local s = rd(0x1CA0)
  if prev == 0 and s ~= 0 and INV_ACTIVE then
    loadStart = frameNo
    if INJECT then
      for x = 0, 127 do if (x & 31) < 30 and rd(0x1D00 + x) == 0 then
        for c = 0, 31 do local a = (0x2000 + x*32 + c) * 2 emu.write(a, emu.read(a, V) ~ 0x5A, V) end end end
      for a = 0, 0x1FFF do emu.write(a, emu.read(a, V) ~ 0xA5, V) end   -- BG CHR words $0000-$0FFF
    end
  elseif prev ~= 0 and s == 0 and loadStart then
    loads = loads + 1 pending = {n = loads, done = frameNo + 30, len = frameNo - loadStart} loadStart = nil
  end
  prev = s
  if pending and frameNo == pending.done then
    local bad = 0
    for x = 0, 127 do if (x & 31) < 30 and rd(0x1D00 + x) == 0 then local n = rowDiff(x) if n > 0 then bad = bad + 1 end end end
    log("LOAD", pending.n, "blank frames", pending.len, "clean rows differing from shadow 30f later", bad, "room", rd(0x42))
    R[#R+1] = {pending.len, bad}
    shot(string.format("load%02d", pending.n))
    pending = nil
  end
end, emu.eventType.startFrame)
run(function()
  INV_ACTIVE = false
  if not bootToSettings() then return end
  if not settingsToStreet() then return end
  INV_ACTIVE = true
  local f = 0
  while loads < LOADS and f < 20000 do
    f = f + 1 emu.write(0x4BF, 0x7F, W)
    held.right = (f % 90) > 3
    step()
  end
  held.right = nil step(60)
  local tb, tl = 0, 0 for _, r in ipairs(R) do tl = tl + r[1] tb = tb + r[2] end
  log("SUMMARY loads", #R, "total blank frames", tl, "total stale clean rows", tb)
end)
