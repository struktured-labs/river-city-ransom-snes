-- Rumble check (build 4293+). Decodes the port-1 rumble packets from the bus
-- the way the MiSTer SNES core does (rtl/ioport.sv: shift WRIO bit 6 on each
-- $4016 read clock while the latch is low; level set when the top byte is
-- $72; cleared on every latch falling edge) and the way Mesen2's
-- SnesRumbleController does (continuous shift, last level kept). Hit events
-- are classified here from the game's own actor data, independently of the
-- ROM helper, and compared with the pulse the helper starts.
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
-- event table (strong, weak, frames), same order as snes/rumble.asm
EV = {"BLOCK", "LAND", "OBJECT", "TAKE", "LAND_KO", "BOSS", "KNOCKDOWN"}
PULSE = {}
local R = 0xF800    -- $7EF800 in work RAM
local function rr(o) return emu.read(R + o, W) end
-- read the table from the ROM helper ($C1:6B00 pulse_level, $6B08 pulse_frames)
local function tbl() for i=1,7 do local l = emu.read(0xC16B00 + i, emu.memType.snesMemory) PULSE[i] = {s = l >> 4, w = l & 15, f = emu.read(0xC16B08 + i, emu.memType.snesMemory), lvl = l} end end
-- bus decoder
local wrio, latch, shift, mister, mes, mesen = 0xFF, 0, 0, 0, 0, 0
local wrioBad, packets, framePackets, badPackets = 0, 0, 0, {}
local function onWrio(addr, v) wrio = v & 0xFF if (v & 0x80) == 0 then wrioBad = wrioBad + 1 end end
strobeNo = 0
local function onLatch(addr, v) local n = v & 1 if wrio ~= 0xFF then wrioOpen = (wrioOpen or 0) + 1 end if latch == 1 and n == 0 then shift = 0 mister = 0 strobeNo = strobeNo + 1 end latch = n end
local function onRead()
  local p6 = (wrio >> 6) & 1
  if latch == 0 then shift = ((shift << 1) | p6) & 0xFFFF if (shift >> 8) == 0x72 then mister = shift & 0xFF end end
  mes = ((mes << 1) | p6) & 0xFFFF
  if (mes & 0xFF00) == 0x7200 then mesen = mes & 0xFF mes = 0 packets = packets + 1 framePackets = framePackets + 1 end
end
for b=0,0xBF do if b < 0x40 or b >= 0x80 then
  emu.addMemoryCallback(onWrio, emu.callbackType.write, b*65536+0x4201, b*65536+0x4201, emu.cpuType.snes, emu.memType.snesMemory)
  emu.addMemoryCallback(onLatch, emu.callbackType.write, b*65536+0x4016, b*65536+0x4016, emu.cpuType.snes, emu.memType.snesMemory)
  emu.addMemoryCallback(onRead, emu.callbackType.read, b*65536+0x4016, b*65536+0x4016, emu.cpuType.snes, emu.memType.snesMemory)
end end
-- rumble RAM: only the helper ($6B00-$6CFF) may write it
local foreign = {}
local booted = false   -- the game clears all work RAM at boot (before the title)
emu.addMemoryCallback(function(addr, v)
  if not booted then return end
  local st = emu.getState() local pc = st["cpu.pc"] or 0
  if pc < 0x6B00 or pc >= 0x6D00 then if #foreign < 5 then foreign[#foreign+1] = string.format("f%d $%05x<-%02x pc=%02x:%04x", frameNo, addr, v, st["cpu.k"] or 0, pc) end end
end, emu.callbackType.write, R, R + 7, emu.cpuType.snes, emu.memType.snesWorkRam)
local function gameplay() return rd(0x3F) == 0 and rd(6) ~= 5 and rd(0xCC) == 0 and (rd(0x100) & 0xC0) == 0xC0 end
-- independent classifier at the hook sites (bank 5 $8DD5, $8D10)
local function isBoss(x) if x < 2 or x > 7 or rd(0xCB + x) >= 8 then return false end local c = rd(0x4F5 + x) return c >= 9 and c <= 0x18 end
local function isDown(x) local s = rd(0x4F + x) & 0x7F return s == 0x0F or s == 0x10 or ((s == 9 or s == 0x0A) and (rd(0x56 + x) & 2) ~= 0 and rd(0x497 + x) == 0) end
function classify(site)
  local v, a = rd(4), rd(5)
  if site == "down" then return a == 0 and 2 or 0 end
  if v == 0 then
    if (rd(0x4F) & 0x7F) == 0x1E then return 1 end
    if rd(0x4BF) == 0 or isDown(0) then return 7 end
    if isBoss(a) then return 6 end
    if rd(0xCB + a) >= 8 then return 3 end
    return 4
  elseif a == 0 then
    if (rd(0x4F + v) & 0x7F) == 0x1E then return 0 end
    if isBoss(v) then return 6 end
    if isDown(v) then return 5 end
    return 2
  end
  return 0
end
starts = {}
HITS = {n=0, byEv={}, mismatch=0, bad={}, started=0}
local pend = nil
local function hookEnter(site)
  local ev = classify(site)
  pend = {ev=ev, site=site, timer=rr(1), rank=rr(3), count=rr(6), v=rd(4), a=rd(5)}
end
local function hookLeave()
  if not pend then return end
  local p = pend pend = nil
  HITS.n = HITS.n + 1
  local ev = p.ev
  local running = p.timer > 0 and p.timer <= 60
  local want = ev > 0 and not (running and ev < p.rank)
  local started = rr(6) ~= p.count
  local ok = (want == started)
  if started then
    HITS.started = HITS.started + 1
    local pl = PULSE[ev]
    ok = ok and rr(5) == ev and rr(2) == pl.lvl and rr(1) == pl.f and rr(3) == ev
    lastStart = {frame=frameNo, ev=ev}
    -- durations count game ticks (pad reads; RCR runs its game loop every
    -- second NMI on the street, so a tick is 1/30 s there)
    pulseEnd = math.max(pulseEnd or 0, strobeNo + PULSE[ev].f + 1)
    -- a hit the game processes while its pause flag is still set (the tick
    -- that unpauses) is dropped on purpose at the next pad read
    local gpNow = gameplay()
    if not gpNow then HITS.dropped = (HITS.dropped or 0) + 1 end
    starts[#starts+1] = {strobe=strobeNo, lvl=PULSE[ev].lvl, seen=not gpNow}
  end
  if ev > 0 then HITS.byEv[ev] = (HITS.byEv[ev] or 0) + 1 end
  if not ok then HITS.mismatch = HITS.mismatch + 1 if #HITS.bad < 6 then HITS.bad[#HITS.bad+1] = string.format("f%d %s v%d a%d want=%s(%s) started=%s event=%d lvl=%02x t=%d", frameNo, p.site, p.v, p.a, tostring(want), EV[ev] or "none", tostring(started), rr(5), rr(2), rr(1)) end end
end
for _, b in ipairs({0xC5, 0x85}) do
  emu.addMemoryCallback(function() hookEnter("hit") end, emu.callbackType.exec, b*65536+0x8DD5, b*65536+0x8DD5, emu.cpuType.snes, emu.memType.snesMemory)
  emu.addMemoryCallback(function() hookLeave() end, emu.callbackType.exec, b*65536+0x8DDA, b*65536+0x8DDA, emu.cpuType.snes, emu.memType.snesMemory)
  emu.addMemoryCallback(function() hookEnter("down") end, emu.callbackType.exec, b*65536+0x8D10, b*65536+0x8D10, emu.cpuType.snes, emu.memType.snesMemory)
  emu.addMemoryCallback(function() hookLeave() end, emu.callbackType.exec, b*65536+0x8D15, b*65536+0x8D15, emu.cpuType.snes, emu.memType.snesMemory)
end
-- per-frame bookkeeping (called once per frame after step())
FR = {gameplayPackets=0, menuPackets=0, menuBad={}, run=0, maxRun=0, runBad=0, mesenAfter=0, wrioOpen=0, levels={}, pulseFrames=0, strongest=0, seenOnAfterStart=0, startsChecked=0}
local lastNonzeroFrame = -999
lastNonzeroStrobe = -999
lastGpStrobe = 0
function frameCheck(tag)
  local gp = gameplay()
  if framePackets > 0 then
    if gp then FR.gameplayPackets = FR.gameplayPackets + framePackets
    end
  end
  -- the level sent at the pad read where gameplay stops may stay until the
  -- next pad read (the game sets its pause flag / mode after reading the
  -- pad); after that read, nothing
  if gp then lastGpStrobe = strobeNo end
  if not gp and (mister ~= 0 or mesen ~= 0) then if strobeNo <= lastGpStrobe + 1 then FR.edge = (FR.edge or 0) + 1 else FR.menuPackets = FR.menuPackets + 1 if #FR.menuBad < 5 then FR.menuBad[#FR.menuBad+1] = string.format("%s f%d level %02x", tag, frameNo, mister) end end end
  prevGp = gp
  -- held without a pad read: the core keeps the level until the next latch
  if strobeNo ~= lastFrameStrobe then holdNoRead = 0 elseif mister ~= 0 then holdNoRead = (holdNoRead or 0) + 1 if holdNoRead > (FR.maxHold or 0) then FR.maxHold = holdNoRead end end
  lastFrameStrobe = strobeNo
  if mister ~= 0 then
    FR.run = FR.run + 1 FR.pulseFrames = FR.pulseFrames + 1 FR.levels[mister] = (FR.levels[mister] or 0) + 1
    if (mister >> 4) + (mister & 15) > FR.strongest then FR.strongest = (mister >> 4) + (mister & 15) end
    lastNonzeroFrame = frameNo lastNonzeroStrobe = strobeNo
    -- a nonzero level needs a pulse started within the last 60 frames
    if not pulseEnd or strobeNo > pulseEnd then FR.runBad = FR.runBad + 1 end
  else
    if FR.run > FR.maxRun then FR.maxRun = FR.run end
    FR.run = 0
    -- Mesen keeps the last level: it must drop to 0 within 2 frames of the core's
    if mesen ~= 0 and strobeNo - lastNonzeroStrobe > 2 then FR.mesenAfter = FR.mesenAfter + 1 end
  end
  -- a started pulse must reach the pad within 2 frames (the hit may come
  -- after this frame's pad read); outside gameplay it is dropped on purpose
  for _, st in ipairs(starts) do
    if not st.done and strobeNo > st.strobe and strobeNo <= st.strobe + 2 then
      if mister ~= 0 or not gp then st.seen = true end
    end
    if not st.done and strobeNo > st.strobe + 2 then st.done = true FR.startsChecked = FR.startsChecked + 1 if st.seen then FR.seenOnAfterStart = FR.seenOnAfterStart + 1 end end
  end
  framePackets = 0
end
function stepR(n, tag) for i=1,(n or 1) do step() frameCheck(tag) end end
function pressR(btn, on, off, tag) held[btn] = true stepR(on or 6, tag) held[btn] = nil stepR(off or 20, tag) end
local function px(s) return rd(0x83+s) + 256*rd(0x8C+s) end
-- fight: go after the nearest goon and punch/kick; pauses now and then let
-- the goons hit back
function fight(frames, tag, forceBoss, force)
  for f=1,frames do
    if force == "take" then emu.write(0x497, 0x30, W) end               -- Alex's hit gauge high: hits stagger him
    if force == "ko" then for s=2,7 do if rd(0x497+s) > 4 then emu.write(0x497+s, 4, W) end end end   -- goon gauges low: the next hit knocks down
    if forceBoss then for s=2,7 do if rd(0xCB+s) < 8 and rd(0x4F5+s) < 9 then emu.write(0x4F5+s, 9, W) end end end
    emu.write(0x4BF, 0x3F, W)   -- keep Alex alive
    local best, bd = nil, 1e9
    for s=2,7 do if rd(0xCB+s) < 8 and (rd(0xD3+s) & 0x7F) ~= 0x7F and px(s) > 0 then local d = math.abs(px(s)-px(0)) if d < bd then bd, best = d, s end end end
    held = {}
    local passive = (f % 600) >= 480 or force == "take"   -- take: walk up to the goons and let them hit
    if best and passive and force == "take" then
      local dx, dy = px(best) - px(0), rd(0x9E+best) - rd(0x9E)
      if dx > 10 then held.right = true elseif dx < -10 then held.left = true end
      if dy > 2 then held.down = true elseif dy < -2 then held.up = true end
    elseif best and not passive then
      local dx, dy = px(best) - px(0), rd(0x9E+best) - rd(0x9E)
      if dx > 6 then held.right = true elseif dx < -6 then held.left = true end
      if dy > 2 then held.down = true elseif dy < -2 then held.up = true end
      if math.abs(dx) <= 12 and math.abs(dy) <= 4 then held.y = (f % 16) < 3 end
      if (f % 40) == 20 then held.b = true end
    elseif not best then held.right = (f % 200) < 150 if (f % 40) == 20 then held.b = true end end
    -- unstick, as in accept.lua's carry phase
    local ax = px(0)
    if f % 90 == 0 then
      if lastAx and math.abs(ax - lastAx) < 4 then unstick = 60 unstickN = (unstickN or 0) + 1 end
      lastAx = ax
    end
    if (unstick or 0) > 0 then
      unstick = unstick - 1
      held = {}
      if unstickN % 2 == 1 then held.up = true held.left = true else held.down = true held.right = true end
    end
    if f % 600 == 0 then log(tag, f, state(), 'best', tostring(best), 'alexX', px(0), 'stam', hex(0x4BF, 8), 'cls', hex(0x4F5, 8), 'kind', hex(0xCB, 8), 'hooks', HITS.n, 'packets', packets) end
    stepR(1, tag)
  end
  held = {}
end
run(function()
  tbl()
  local t = {} for i=1,7 do t[#t+1] = string.format("%s=%d/%d/%d", EV[i], PULSE[i].s, PULSE[i].w, PULSE[i].f) end
  log("pulse table", table.concat(t, " "))
  -- title and settings: nothing may be sent
  if not waitUntil(isTitle, 2400) then check("R reach title", false) return end
  booted = true
  local menu0 = packets
  pressR("start", 12, 18, "title")
  stepR(60, "settings")
  while rd(0x64C) ~= 3 do pressR("right", 6, 20, "settings") end
  pressR("start", 12, 18, "settings")
  for n=1,60 do if onStreet() then break end pressR("a", 8, 12, "story") end
  local menuPackets = packets - menu0
  check("R0 reached the street", onStreet(), state())
  -- fight
  fight(1200, "take", false, "take")
  fight(3000, "fight")
  shot("R-fight")
  fight(1500, "ko", false, "ko")
  -- pause right after a pulse starts: rumble must stop and nothing is sent while paused
  local pauseOk, pausePk, waited = true, 0, 0
  for k=1,3 do
    local c = rr(6)
    for i=1,1200 do fight(1, "fight") waited = waited + 1 if rr(6) ~= c then break end end
    held = {} held.start = true stepR(3, "pause") held = {}
    local p0 = packets
    for i=1,90 do stepR(1, "pause") if rd(0x3F) ~= 0 and strobeNo > lastGpStrobe + 1 and (mister ~= 0 or mesen ~= 0) then pauseOk = false end end
    local sawPause = rd(0x3F) ~= 0
    -- packets while paused: only off packets are allowed, and only in the first frames
    pausePk = pausePk + (packets - p0)
    if mesen ~= 0 then pauseOk = false end
    if not sawPause then pauseOk = false log("pause not reached", state()) end
    shot("R-paused-" .. k)
    held = {} held.start = true stepR(3, "unpause") held = {}
    stepR(60, "unpause")
  end
  held = {}
  fight(600, "fight2")
  -- boss rule: goon classes forced to a boss class (test only)
  local b0 = HITS.byEv[6] or 0
  fight(1500, "boss", true)
  local bossHits = (HITS.byEv[6] or 0) - b0
  held = {}
  -- end: pause (the goons keep fighting otherwise) and everything must be off
  held.start = true stepR(3, "endpause") held = {}
  stepR(60, "endpause")
  shot("R-end-paused")
  local lv = {} for k,v in pairs(FR.levels) do lv[#lv+1] = string.format("%02x:%d", k, v) end table.sort(lv)
  local ev = {} for i=1,7 do ev[#ev+1] = string.format("%s:%d", EV[i], HITS.byEv[i] or 0) end
  log(string.format("hook calls=%d started=%d mismatch=%d events %s | packets=%d gameplayPackets=%d menuPackets(title/settings)=%d pauseFramesNonzero=%s pausePackets=%d | pulse frames=%d maxRun=%d runNoEvent=%d mesenStuck=%d wrioBad=%d wrioNotFF=%d levels %s | foreign=%d %s %s",
    HITS.n, HITS.started, HITS.mismatch, table.concat(ev, " "), packets, FR.gameplayPackets, menuPackets, tostring(not pauseOk), pausePk, FR.pulseFrames, FR.maxRun, FR.runBad, FR.mesenAfter, wrioBad, (wrioOpen or 0), table.concat(lv, " "), #foreign, table.concat(foreign, "; "), table.concat(HITS.bad, "; ")))
  check("R1 rumble RAM written only by the helper; WRIO bit 7 always 1 and WRIO $FF at every pad latch", #foreign == 0 and wrioBad == 0 and (wrioOpen or 0) == 0, string.format("foreign=%d wrioBad=%d wrioNotFF=%d", #foreign, wrioBad, (wrioOpen or 0)))
  check("R2 every hit classified as the check expects (event, level, frames, priority)", HITS.n > 0 and HITS.mismatch == 0, string.format("hooks=%d mismatch=%d", HITS.n, HITS.mismatch))
  check("R3 pulses on landed hits, hits taken and knockdowns, sent at the next pad read", (HITS.byEv[2] or 0) > 0 and (HITS.byEv[4] or 0) > 0 and ((HITS.byEv[5] or 0) + (HITS.byEv[7] or 0)) > 0 and FR.seenOnAfterStart == FR.startsChecked and FR.startsChecked > 0, string.format("land=%d take=%d landKO=%d knockdown=%d object=%d block=%d starts=%d seenNextFrame=%d (started while paused, dropped: %d)", HITS.byEv[2] or 0, HITS.byEv[4] or 0, HITS.byEv[5] or 0, HITS.byEv[7] or 0, HITS.byEv[3] or 0, HITS.byEv[1] or 0, FR.startsChecked, FR.seenOnAfterStart, HITS.dropped or 0))
  check("R4 rumble always returns to 0 (core: no packet = 0; Mesen: $7200 sent), never longer than the pulses started", mister == 0 and mesen == 0 and FR.runBad == 0 and FR.mesenAfter == 0 and (FR.maxHold or 0) <= 4, string.format("maxRun=%d frames, longest hold without a pad read=%d frames, runNoEvent=%d mesenStuck=%d end core=%02x mesen=%02x", FR.maxRun, FR.maxHold or 0, FR.runBad, FR.mesenAfter, mister, mesen))
  check("R5 nothing on title/settings or while paused", menuPackets == 0 and FR.menuPackets == 0 and pauseOk, string.format("titleSettingsPackets=%d nonGameplayNonzero=%d (first frame of pause/screen change, allowed: %d) pauseOk=%s %s", menuPackets, FR.menuPackets, FR.edge or 0, tostring(pauseOk), table.concat(FR.menuBad, " ")))
  check("R6 boss hits rumble (goon classes forced to a boss class)", bossHits > 0, "bossHits=" .. bossHits)
end)
