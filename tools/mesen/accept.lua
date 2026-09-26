-- Gamer Mode acceptance checklist, run on the final ROM in Mesen2.
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
NEXT = {[1]=4,[4]=2,[2]=3,[3]=1}
PREV = {[1]=3,[3]=2,[2]=4,[4]=1}
NAMES = {[1]="00cdced5c8c2c400", [2]="c0c3d5c0cdc2c4c3", [3]="00c6c0ccc4d10000", [4]="c8cdd3c4d1ccc4c3"}
RED = 0x00BB
function vname() local t={} for i=0,7 do t[#t+1]=string.format("%02x", emu.read((0x22AC+i)*2, V)) end return table.concat(t) end
-- ground truth: which actor slot wrote each NES OAM attribute this frame
writer = {}
heldW = {}
slotHist = {}
-- Held objects (a weapon, box or can in someone's hands) are drawn as a
-- sub-part of the holder's own metasprite: the $FC opcode branch at $EE4B
-- (taken only when the holder's $56 bit 6 is set) draws the held object's
-- frame and returns at $EF7D. Track that control flow independently of the
-- ROM's own test so held-object sprites can be told apart from body sprites.
heldPart = false
for b=0xC1,0xC8 do
  emu.addMemoryCallback(function() heldPart = true end, emu.callbackType.exec, b*65536+0xEE4B, b*65536+0xEE4B, emu.cpuType.snes, emu.memType.snesMemory)
  emu.addMemoryCallback(function() heldPart = false end, emu.callbackType.exec, b*65536+0xEF7D, b*65536+0xEF7D, emu.cpuType.snes, emu.memType.snesMemory)
  emu.addMemoryCallback(function() heldPart = false end, emu.callbackType.exec, b*65536+0xED0E, b*65536+0xED0E, emu.cpuType.snes, emu.memType.snesMemory)
end
emu.addMemoryCallback(function(addr, value)
  if (addr & 3) ~= 2 then return end
  writer[(addr & 0xFF) // 4] = rd(0x47)
  heldW[(addr & 0xFF) // 4] = heldPart
  slotHist[rd(0x47)] = (slotHist[rd(0x47)] or 0) + 1
end, emu.callbackType.write, 0x200, 0x2FF, emu.cpuType.snes, emu.memType.snesWorkRam)
function cg(i) return emu.read(i*2, CG) + 256*emu.read(i*2+1, CG) end
-- one frame's outline audit. Returns counts; records failures in stats.
stats = {}
-- weapons/items: objects of sprite kind $08-$11 (bank 6 $8000 kind table,
-- room object list bank 13 $B6D9) or a held-object sub-part. Never outlined.
ITEM = {spr=0, red=0, held=0, heldGoon=0, ground=0, flying=0, bad={}}
itemShots = {held=0, ground=0}
TILES = {item={}, body={}}
function resetStats() stats = {frames=0, goonSpr=0, goonRed=0, otherSpr=0, otherRed=0, snesMismatch=0, palBad=0, bad={}} end
function audit(tag)
  stats.frames = stats.frames + 1
  frameHeldGoon = false frameGround = false
  local sk = rd(0x64C)
  for i=0,63 do
    local y = rd(0x200+i*4)
    local s = writer[i]
    if y < 0xEF and s ~= nil then
      local t = rd(0x4F5 + s)
      local a = rd(0x202+i*4)
      local marked = (a & 4) ~= 0
      -- game semantics: slots 0-1 players, classes 0-8 gangs (room table $B5E8), 9-$18 bosses, $19+ townsfolk
      local kind = rd(0xCB + s)
      local held = heldW[i] == true
      local item = held or (kind >= 8 and kind <= 0x11)
      local enemy = s >= 2 and s <= 7 and t < 0x19 and kind < 8 and not held and rd(0xCC) == 0
      if sk ~= 3 then enemy = false end
      local tile = rd(0x201+i*4)
      if item then TILES.item[tile] = true elseif s >= 2 and s <= 7 and kind < 8 then TILES.body[tile] = true end
      if item then
        ITEM.spr = ITEM.spr + 1
        if held then ITEM.held = ITEM.held + 1 if s >= 2 and s <= 7 and kind < 8 then ITEM.heldGoon = ITEM.heldGoon + 1 frameHeldGoon = true end
        else ITEM.ground = ITEM.ground + 1 frameGround = true if (rd(0x56 + s) & 0x80) ~= 0 then ITEM.flying = ITEM.flying + 1 end end
        if marked then ITEM.red = ITEM.red + 1 if #ITEM.bad < 8 then ITEM.bad[#ITEM.bad+1] = string.format("ITEM %s spr%d slot%d kind%02x held=%s tile%02x attr%02x", tag, i, s, kind, tostring(held), rd(0x201+i*4), a) end end
      end
      if enemy then
        stats.goonSpr = stats.goonSpr + 1
        if marked then stats.goonRed = stats.goonRed + 1 elseif #stats.bad < 6 then stats.bad[#stats.bad+1] = string.format("UNMARKED %s spr%d slot%d type%02x attr%02x", tag, i, s, t, a) end
      else
        stats.otherSpr = stats.otherSpr + 1
        if marked then stats.otherRed = stats.otherRed + 1 if #stats.bad < 6 then stats.bad[#stats.bad+1] = string.format("%s spr%d slot%d type%02x attr%02x", tag, i, s, t, a) end end
      end
    end
  end
  if frameHeldGoon and itemShots.held < 3 and frameNo % 90 == 0 then itemShots.held = itemShots.held + 1 shot(string.format("8-goon-holding-weapon-%d", itemShots.held)) end
  if frameGround and not frameHeldGoon and itemShots.ground < 3 and frameNo % 90 == 0 then itemShots.ground = itemShots.ground + 1 shot(string.format("8-weapon-on-ground-%d", itemShots.ground)) end
  -- palettes 4-7 = palettes 0-3 with color 1 red (only meaningful in Gamer)
  if sk == 3 then
    for p=0,3 do
      local base, red = 0x80+p*16, 0xC0+p*16
      if cg(red) ~= cg(base) or cg(red+1) ~= RED or cg(red+2) ~= cg(base+2) or cg(red+3) ~= cg(base+3) then stats.palBad = stats.palBad + 1 break end
    end
  end
  -- SNES OAM (PPU) palette bit 3 must follow the NES goon bit for visible sprites
  -- (PPU OAM is uploaded in the vblank after the game writes $0200, so compare
  -- against both this and the previous frame's NES attributes)
  local cur = {} for i=0,63 do cur[i] = rd(0x202+i*4) end
  for i=0,63 do
    local sy = emu.read(i*4+1, OAMT)
    if sy < 0xE0 then
      local sattr = emu.read(i*4+3, OAMT)
      local ok = false
      local cands = {cur[i]}
      for k=1,#nesHist do cands[#cands+1] = nesHist[k][i] end
      for _,nattr in ipairs(cands) do
        local want = (nattr & 0xC0) | ((nattr & 3) << 1) | (((nattr & 0x20) ~= 0) and 0 or 0x30) | (((nattr & 4) ~= 0) and 8 or 0)
        if (sattr & 0xFE) == want then ok = true end
      end
      if not ok then
        stats.snesMismatch = stats.snesMismatch + 1
        if stats.snesMismatch <= 5 then local h = {} for _,c in ipairs(cands) do h[#h+1] = string.format("%02x", c) end log(string.format("snes mismatch %s spr%d sattr=%02x nes(cur,prev..)=%s sy=%d", tag, i, sattr, table.concat(h, ","), sy)) end
      end
    end
  end
end
nesHist = {}
-- PPU OAM may trail the game's OAM by up to 3 frames when a vblank has no room for the OAM DMA
function auditEnd() local t = {} for i=0,63 do t[i] = rd(0x202+i*4) end table.insert(nesHist, 1, t) if #nesHist > 3 then table.remove(nesHist) end end
function report(tag, needGoons)
  log(string.format("%s frames=%d goonSpr=%d goonRed=%d otherSpr=%d otherRed=%d snesMismatch=%d palBad=%d %s", tag, stats.frames, stats.goonSpr, stats.goonRed, stats.otherSpr, stats.otherRed, stats.snesMismatch, stats.palBad, table.concat(stats.bad, "; ")))
  local ok = stats.otherRed == 0 and stats.goonRed == stats.goonSpr and stats.palBad == 0 and stats.snesMismatch == 0
  if needGoons then ok = ok and stats.goonSpr > 0 end
  return ok
end
-- liveness
lastSig = nil sameCount = 0 blackCount = 0
-- alive: the game keeps polling the joypad (native_joypad_poll executions) and the screen is not black for long.
-- Call about every 15 frames.
polls = 0
for b=0xC1,0xC8 do
  emu.addMemoryCallback(function() polls = polls + 1 end, emu.callbackType.exec, b*65536+0x348C, b*65536+0x348C, emu.cpuType.snes, emu.memType.snesMemory)
end
function alive()
  local s, nz = screenSig()
  local t = polls
  if t == lastSig then sameCount = sameCount + 1 else sameCount = 0 end
  if nz < 20 then blackCount = blackCount + 1 else blackCount = 0 end
  lastSig = t
  if sameCount >= 4 or blackCount >= 8 then log("NOT ALIVE", "timerStuck="..sameCount, "black="..blackCount, state()) end
  return sameCount < 4 and blackCount < 8
end
function frameHook() writer = {} end
function stepA(n, tag) for i=1,n do writer = {} heldW = {} step() audit(tag) end end

run(function()
  -- 1. skill select
  if not bootToSettings() then check("1 reach settings", false) return end
  local stepFails, nameFails = 0, 0
  local function tap(btn, on, off)
    local before = rd(0x64C) press(btn, on, off)
    local want = (btn=="right") and NEXT[before] or PREV[before]
    if rd(0x64C) ~= want then stepFails = stepFails + 1 log("step fail", btn, on, off, before, rd(0x64C), want) end
  end
  local function settle(tag)
    step(10)
    local sk = rd(0x64C)
    if vname() ~= NAMES[sk] or hex(0x122AC,8) ~= NAMES[sk] then nameFails = nameFails + 1 log("name fail", tag, sk, vname(), hex(0x122AC,8)) end
  end
  settle("initial") shot("1-skill-initial")
  for i=1,4 do tap("right", 6, 20) settle("spaced R"..i) end
  for i=1,4 do tap("left", 6, 20) settle("spaced L"..i) end
  for _,p in ipairs({{2,2},{2,1},{1,1},{1,2},{3,1},{4,2}}) do
    for i=1,4 do tap("right", p[1], p[2]) end settle("quick R"..p[1].."/"..p[2])
    for i=1,3 do tap("left", p[1], p[2]) end settle("quick L"..p[1].."/"..p[2])
    shot(string.format("1-skill-quick-%d-%d", p[1], p[2]))
  end
  local guard = 0
  while rd(0x64C) ~= 3 and guard < 8 do tap("right", 6, 20) guard = guard + 1 end
  settle("gamer") shot("1-skill-gamer")
  check("1 skill: one step per press (spaced + 1-2 frame taps)", stepFails == 0, "stepFails="..stepFails)
  check("1 skill: on-screen name matches memory", nameFails == 0, "nameFails="..nameFails)
  -- 2. Start from the skill screen, right after a quick tap pair (worst case)
  tap("right", 2, 1) tap("right", 2, 1) tap("right", 2, 1) tap("right", 2, 1)
  log("before start", state(), "vname", vname())
  press("start", 3, 1)
  local okStart = true local sawText = false
  for i=1,40 do step(15) if not alive() then okStart = false end if rd(6) ~= 5 then sawText = true end if i == 4 then shot("2-after-start") end end
  check("2 Start from skill screen proceeds (no freeze/black)", okStart and sawText and rd(0x64C) == 3, state())
  for n=1,60 do if onStreet() then break end press("a", 8, 12) end
  check("2 reached the street", onStreet(), state())
  -- 3. no skill-name tiles on the street
  step(30)
  local h = findNames()
  shot("3-street-start")
  check("3 no skill name on street at start", #h == 0, table.concat(h, " "))
  -- 4/7. walk and fight, auditing every frame
  resetStats() lastSig=nil sameCount=0 blackCount=0
  local dead = false
  local nameHits = 0
  local t0 = frameNo
  fights = 0
  local es = {rd(0x4C1), rd(0x4C2)}
  for sec=1,70 do
    for f=1,60 do
      local ph = (frameNo // 20) % 6
      held.right = (sec % 10) < 6
      held.left = (sec % 10) >= 8
      held.y = ph == 1 held.b = ph == 3 held.up = (sec % 7) == 3 held.down = (sec % 7) == 5
      writer = {} heldW = {} step() audit("street") auditEnd()
      if f % 15 == 0 and not alive() then dead = true end
      if rd(0x4C1) ~= es[1] or rd(0x4C2) ~= es[2] or rd(0x4BF) ~= (es[3] or rd(0x4BF)) then fights = fights + 1 end
      es = {rd(0x4C1), rd(0x4C2), rd(0x4BF)}
    end
    if sec % 10 == 0 then shot(string.format("7-street-%02ds", sec)) log("sec", sec, state(), "types", hex(0x4F5,8)) end
    if #findNames() > 0 then nameHits = nameHits + 1 end
    if sec == 20 then shot("4-goons-20s") end
  end
  held = {}
  local secs = (frameNo - t0) / 60
  check("3 no skill name on street during play", nameHits == 0, "hits="..nameHits)
  check("4 red outline only on goons (by actor slot type), palettes 4-7 correct", report("street", true))
  local hist = {} for k,v in pairs(slotHist) do hist[#hist+1] = string.format("%d:%d", k, v) end table.sort(hist)
  log("metasprite slots", table.concat(hist, " "))
  check("7 no freeze/black in "..secs.."s of street play incl. fighting", (not dead) and fights > 0, state().." fights="..fights)
  -- 5. pause / unpause
  local before = {} for i=0x80,0xBF do before[i] = cg(i) end
  shot("5-before-pause")
  resetStats()
  local function redCount() local n, v = 0, 0 for i=0,63 do if emu.read(i*4+1, OAMT) < 0xE0 then v = v + 1 if (emu.read(i*4+3, OAMT) & 8) ~= 0 then n = n + 1 end end end return n, v end
  local function nesSnap() local t = {} for i=0,255 do t[i] = rd(0x200+i) end return t end
  local redBefore, visBefore = redCount()
  local snapBefore = nesSnap()
  press("start", 6, 2)
  local sawPause = false
  local minRed, maxRed = 999, 0
  for i=1,120 do writer = {} heldW = {} step() audit("pause") auditEnd() if rd(0x3F) ~= 0 then sawPause = true local n = redCount() minRed = math.min(minRed, n) maxRed = math.max(maxRed, n) end end
  shot("5-paused")
  local snapPaused = nesSnap()
  local changed = 0 for i=0,255 do if snapPaused[i] ~= snapBefore[i] then changed = changed + 1 end end
  log(string.format("pause: red sprites before=%d (visible %d) during=%d..%d, NES OAM bytes changed=%d", redBefore, visBefore, minRed, maxRed, changed))
  local pauseOk = report("paused", false) and redBefore > 0 and minRed > 0
  press("start", 6, 2)
  for i=1,120 do writer = {} heldW = {} step() audit("unpause") auditEnd() end
  shot("5-after-unpause")
  local palSame = true for i=0x80,0xBF do if cg(i) ~= before[i] then palSame = false end end
  resetStats()
  for i=1,240 do held.right = (i % 60) < 30 writer = {} heldW = {} step() audit("after-pause") auditEnd() end
  held = {}
  local afterOk = report("after-pause", true)
  check("5 pause/unpause: marks + palettes intact", sawPause and pauseOk and afterOk and palSame, string.format("sawPause=%s palSame=%s", tostring(sawPause), tostring(palSame)))
  -- 6. low stamina (forced), outline must persist
  resetStats()
  for i=1,240 do emu.write(0x4BF, 2, W) held.right = (i % 40) < 20 held.y = (i % 20) == 5 writer = {} heldW = {} step() audit("lowstam") auditEnd() end
  held = {}
  shot("6-low-stamina")
  check("6 outline persists at low stamina (stam forced to 2)", report("lowstam", true), state())
  check("8 no weapon/item sprite outlined (on ground, thrown, held by a goon)", ITEM.red == 0 and ITEM.heldGoon > 0 and ITEM.ground > 0,
    string.format("itemSpr=%d red=%d heldSpr=%d heldByGoonSpr=%d groundSpr=%d flyingSpr=%d shots held=%d ground=%d %s", ITEM.spr, ITEM.red, ITEM.held, ITEM.heldGoon, ITEM.ground, ITEM.flying, itemShots.held, itemShots.ground, table.concat(ITEM.bad, "; ")))
  local it, both = {}, {}
  for t,_ in pairs(TILES.item) do it[#it+1] = string.format("%02x", t) if TILES.body[t] then both[#both+1] = string.format("%02x", t) end end
  table.sort(it) table.sort(both)
  log("item tiles", table.concat(it, " "), "shared with enemy bodies:", table.concat(both, " "))
  log("final", state())
end)
