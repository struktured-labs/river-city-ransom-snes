-- Issue #8 repro: many room transitions (back and forth, mid-fight, attacks held),
-- every gameplay frame compare visible BG1 tilemap (NES rows 4-23) with the game's
-- NES nametable shadow. A mismatch that persists PERSIST frames is a failure
-- (normal row deferral clears within a few frames). env RCR_TRANS, RCR_SEED, RCR_CONTROL.
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
TRANS = tonumber(os.getenv("RCR_TRANS") or "200")
PERSIST = tonumber(os.getenv("RCR_PERSIST") or "12")
CONTROL = os.getenv("RCR_CONTROL") == "1"
DEBUG = os.getenv("RCR_DEBUG") == "1"
math.randomseed(tonumber(os.getenv("RCR_SEED") or "1"))
function sh(a) return emu.read(0x12000 + a, W) end
function gameplay() return (rd(0x100) & 0xC0) == 0xC0 and rd(0x1CA0) == 0 and (rd(0x1C20) & 2) == 0 and (rd(0x3F) & 0x20) == 0 end
function mism()
  local cam = rd(0x1C94) + 256*(rd(0x1C95) & 1)
  local hi = (rd(0x1C20) & 0x10) << 4
  local c0 = cam // 8
  local miss, first = 0, nil
  for y=4,23 do for k=0,32 do
    local col = (c0 + k) % 64
    local nt, c = col // 32, col % 32
    local base = nt * 0x400
    local tile = sh(base + y*32 + c)
    local attr = sh(base + 0x3C0 + (y//4)*8 + c//4)
    local pal = (attr >> ((y & 2)*2 + (c & 2))) & 3
    local want = tile | hi | (pal << 10)
    local got = vw(0x2000 + (nt*32 + y)*32 + c) & 0x1FFF
    if got ~= want then miss = miss + 1 if not first then first = string.format("y%d col%d want %04x got %04x", y, col, want, got) end end
  end end
  return miss, first
end
S = {frames=0, run=0, worst=0, fails=0, trans=0, entries={}}
local lastRoom, sinceEntry = nil, 0
emu.addEventCallback(function()
  if not on then return end
  if not gameplay() then S.run = 0 wasPlay = false return end
  local r = rd(0x42)
  if not wasPlay or r ~= lastRoom then lastRoom = r sinceEntry = 0 S.trans = S.trans + 1 end
  wasPlay = true
  sinceEntry = sinceEntry + 1
  local m, first = mism()
  S.frames = S.frames + 1
  if m > 0 then S.run = S.run + 1 else S.run = 0 end
  if S.run > S.worst then S.worst = S.run end
  if S.run == PERSIST then
    S.fails = S.fails + 1
    log("FAILSTALE room", string.format("%02X", r), "trans", S.trans, "sinceEntry", sinceEntry, "tiles", m, first, state())
    if S.fails <= 6 then shot(string.format("fail%02d", S.fails)) end
  end
end, emu.eventType.startFrame)
on = false
run(function()
  if not bootToSettings() then return end
  if not settingsToStreet() then return end
  on = true
  local dir = "right"
  local t0 = frameNo
  local lastT = 0
  while S.trans < TRANS do
    emu.write(0x4BF, 0x7F, W)        -- keep Alex alive
    local r0 = rd(0x42)
    held.right = (dir == "right") held.left = (dir == "left")
    held.y = math.random() < 0.15 held.b = math.random() < 0.1
    held.up = math.random() < 0.05 held.down = math.random() < 0.05
    step()
    if DEBUG and frameNo % 300 == 0 then log('dbg dir', dir, 'room', rd(0x42), 'cam', rd(0x1C94)+256*(rd(0x1C95)&1), 'play', gameplay(), state()) if frameNo % 1200 == 0 then shot('dbg'..frameNo) end end
    if CONTROL and S.trans == 3 and not did then
      did = true
      if gameplay() then local cam = rd(0x1C94) + 256*(rd(0x1C95) & 1)
        local col = (cam // 8 + 10) % 64 local w = 0x2000 + ((col // 32)*32 + 12)*32 + col % 32
        emu.write(w*2, emu.read(w*2, V) ~ 0x55, V) log("control: corrupted VRAM word", string.format("%04X", w)) end
    end
    if S.trans ~= lastT then
      lastT = S.trans
      -- after entering, linger a random time (mid-fight) then reverse direction
      held.right, held.left = nil, nil
      local linger = math.random(0, 90)
      for i = 1, linger do held.y = math.random() < 0.3 held.b = math.random() < 0.2 step() end
      if math.random() < 0.3 then dir = (dir == "right") and "left" or "right" end
      if S.trans % 50 == 0 then log("progress trans", S.trans, "frames", S.frames, "worstRun", S.worst, "fails", S.fails) end
    end
    if frameNo - t0 > TRANS * 1500 then log("timeout") break end
  end
  log("SUMMARY transitions", S.trans, "audited frames", S.frames, "worst consecutive stale", S.worst, "persistent failures", S.fails)
end)
