-- Issue #8 long session: one power-on, no resets, hours of mixed play.
-- Segments (random): teleport legs ($0042 held during the game's own load), natural
-- exits, goon fights, deaths + respawns, pause menus (BELONGINGS, PASSWORD view,
-- STATUS, HELP), quick I->G->I and long Gamer stretches, "door" attempts (Up into
-- buildings/shops) with A/B mashing in any dialogue/shop. Checks: vis_check (skip
-- rows mid-update), per-frame row invariant, periodic bookkeeping snapshots.
-- Every frame's pad state is logged (RLE) to inputs.txt; on bsnes a savestate is
-- written every SS_EVERY frames (ss_<frame>.state, last 3 kept) for replay.
-- On any hit: WRAM + shadow dump, screenshot, savestate (bsnes).
dofile(os.getenv("RCR_LIB")) dofile(os.getenv("INV_LIB")) dofile(os.getenv("VC_LIB"))
dofile(os.getenv("RCR_LIB"):gsub("lib.lua", "password.lua"))
math.randomseed(tonumber(os.getenv("SEED") or "1"))
local FRAMES = tonumber(os.getenv("FRAMES") or "864000")
local SS_EVERY = tonumber(os.getenv("SS_EVERY") or "18000")
local TARGETS = {}
for h in (os.getenv("TARGETS") or "04 04 06 07 09 0a 0b 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 08"):gmatch("%x+") do TARGETS[#TARGETS+1] = tonumber(h, 16) end
local BITS = {"a","b","x","y","l","r","up","down","left","right","start","select"}
local inlog = io.open(OUT .. "/inputs.txt", "w") local lastMask = -1
local function mask() local m = 0 for i, k in ipairs(BITS) do if held[k] then m = m | (1 << (i-1)) end end return m end
local states, hits = {}, 0
local function dump(tag)
  local h = io.open(string.format("%s/wram_%s_f%d.hex", OUT, tag, frameNo), "w")
  for base, len in pairs({[0] = 0x2000, [0x12000] = 0x1000}) do
    for a = base, base + len - 1, 32 do
      local t = {} for i = 0, 31 do t[#t+1] = string.format("%02x", emu.read(a + i, W)) end
      h:write(string.format("%05x %s\n", a, table.concat(t)))
    end
  end
  h:close()
  if emu.saveStateFile then emu.saveStateFile(string.format("%s/hit_%s_f%d.state", OUT, tag, frameNo)) end
  inlog:flush()
end
function VC_ON_HIT(kind, key) hits = hits + 1 log("HIT-DUMP", kind, key, "f", frameNo) if hits <= 5 then dump(kind .. key) end end
function INV_ON_HIT(x) hits = hits + 1 log("HIT-DUMP INV", x, "f", frameNo) if hits <= 5 then dump("INV" .. x) end end
local prev, loads, force, inMenu, lastLoad = 0, 0, nil, false, 0
local visited, maxBlank = {}, 0
local ldStart
emu.addEventCallback(function()
  invariantCheck() visCheck()
  local m = mask() if m ~= lastMask then inlog:write(frameNo, " ", m, "\n") lastMask = m end
  if emu.saveStateFile and frameNo % SS_EVERY == 0 and frameNo > 0 then
    local p = string.format("%s/ss_%d.state", OUT, frameNo)
    if emu.saveStateFile(p) then states[#states+1] = p inlog:flush() if #states > 3 then os.remove(table.remove(states, 1)) end end
  end
  local s = rd(0x1CA0)
  if force and s ~= 0 then emu.write(0x42, force, W) end
  if prev == 0 and s ~= 0 then ldStart = frameNo end
  if prev ~= 0 and s == 0 then
    loads = loads + 1 lastLoad = frameNo force = nil
    if ldStart and frameNo - ldStart > maxBlank and frameNo - ldStart < 400 then maxBlank = frameNo - ldStart end
    local a = rd(0x42) visited[a] = (visited[a] or 0) + 1
  end
  prev = s
end, emu.eventType.startFrame)
local alive = true
local function tick() if alive then emu.write(0x4BF, 0x7F, W) end step() end
local PATS = {{right=true}, {right=true, up=true}, {right=true, down=true}, {left=true}, {left=true, up=true}, {left=true, down=true}, {up=true}}
local function clear() for k in pairs(held) do held[k] = nil end end
local function walkUntilLoad(maxf)
  local l0, i, since = loads, 1, frameNo
  for f = 1, maxf do
    local p = PATS[i]
    for _, k in ipairs({"left", "right", "up", "down"}) do held[k] = p[k] end
    held.y = math.random() < 0.08 held.b = math.random() < 0.04
    tick()
    if loads > l0 then clear() return true end
    if frameNo - since > 900 then i = i % #PATS + 1 since = frameNo end
  end
  clear() return false
end
local function fight(n)
  for f = 1, n do
    local ph = (f // 45) % 4
    held.left = ph == 0 held.right = ph == 2 held.up = ph == 1 and f % 90 < 20 held.down = ph == 3 and f % 90 < 20
    held.y = math.random() < 0.15 held.b = math.random() < 0.10 held.a = math.random() < 0.02
    tick()
  end
  clear()
end
local function menus()
  inMenu = true
  local item = math.random(0, 4)
  if openPause() and menuTo(item) then
    press("a", 6, 90)
    if item == 1 then step(math.random(150, 400)) press("b", 6, 90) press("start", 6, 90) press("b", 6, 90) press("start", 6, 90)
    elseif item == 0 then press("right", 6, 20) press("a", 6, 60)
    else for i = 1, math.random(1, 4) do press(item == 2 and "b" or "start", 6, 60) end end
  end
  for i = 1, 4 do unpause() if rd(0x3F) == 0 then break end press("b", 6, 40) end
  inMenu = false
  return item
end
local function door()
  for f = 1, math.random(120, 400) do held.up = true held.right = (f % 120) < 30 tick() end clear()
  for f = 1, math.random(200, 600) do held.a = (f % 20) < 3 held.b = (f % 97) < 3 held.down = (f % 150) > 140 tick() end clear()
end
local gamer = false
local function setG(on) inMenu = true local ok = setSkill(on and 3 or 4) inMenu = false gamer = on and ok or false return ok end
local seg, stats = 0, {tele=0, nat=0, menu=0, igi=0, gstretch=0, death=0, door=0}
run(function()
  VC_ACTIVE, INV_ACTIVE = false, false
  if not bootToSettings() then return end
  for n = 1, 8 do if rd(0x64C) == 4 then break end press("right", 6, 20) end
  if not settingsToStreet() then return end
  inMenu = true
  if os.getenv("PW") then log("password", enterPassword(os.getenv("PW")), state()) end
  log("skill->4", setSkill(4)) inMenu = false
  VC_ACTIVE, INV_ACTIVE = true, true
  local f0, nextCk = frameNo, frameNo + 36000
  while frameNo - f0 < FRAMES do
    seg = seg + 1
    local r = math.random()
    if r < 0.25 then force = TARGETS[math.random(#TARGETS)] walkUntilLoad(6300) force = nil fight(math.random(300, 900)) stats.tele = stats.tele + 1
    elseif r < 0.45 then if walkUntilLoad(6300) then fight(math.random(200, 800)) end stats.nat = stats.nat + 1
    elseif r < 0.60 then menus() stats.menu = stats.menu + 1
    elseif r < 0.70 then if gamer then setG(false) else setG(true) fight(math.random(60, 400)) setG(false) end stats.igi = stats.igi + 1
    elseif r < 0.76 then setG(true) stats.gstretch = stats.gstretch + 1          -- long Gamer stretch until a later switch
    elseif r < 0.82 then alive = false emu.write(0x4BF, 1, W) fight(1500) alive = true stats.death = stats.death + 1
    elseif r < 0.90 then door() stats.door = stats.door + 1
    else fight(math.random(300, 1200)) end
    if frameNo >= nextCk then
      nextCk = frameNo + 36000
      local v = {} for a, n in pairs(visited) do v[#v+1] = string.format("%02x:%d", a, n) end table.sort(v)
      local st = {0, 0, 0, 0} for x = 0, 127 do local q = rd(0x1D00 + x) if q <= 3 then st[q+1] = st[q+1] + 1 end end
      log(string.format("CK emu %.2fh", (frameNo - f0) / 216000), "loads", loads, "maxBlank", maxBlank, "segs", seg,
          "tele", stats.tele, "nat", stats.nat, "menu", stats.menu, "igi", stats.igi, "gstr", stats.gstretch, "death", stats.death, "door", stats.door,
          "skill", rd(0x64C), "VC", VC.checks, "row", VC.rowHits, "chr", VC.chrHits, "invP", INV.persist, "hits", hits,
          "rowstates", table.concat(st, "/"), "bk1C00", hex(0x1C00, 0xC0), "visited", table.concat(v, " "))
      inlog:flush()
    end
  end
  log("SUMMARY loads", loads, "segs", seg, "VC", VC.checks, "row", VC.rowHits, "chr", VC.chrHits, "invP", INV.persist, "hits", hits)
  inlog:close()
end)
