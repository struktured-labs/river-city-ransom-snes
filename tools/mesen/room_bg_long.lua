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
-- SHOP=1: wallet changes + shop purchases. P1 money $04C7-$04C9 (BCD); $00CC != 0 while a shop
-- (or other interior dialogue) is drawn. Wallet is randomly set (rich / broke / random)
-- before entering, then menus are mashed (Up/Down + A to buy, B to leave).
local SHOP = os.getenv("SHOP") == "1"
local function money() return rd(0x4C7) | (rd(0x4C8) << 8) | (rd(0x4C9) << 16) end
local function wallet()
  local r = math.random()
  local v = r < 0.6 and {0x99, 0x99, 0x09} or (r < 0.8 and {0, 0, 0} or {math.random(0, 9) * 16 + math.random(0, 9), math.random(0, 9) * 16, 0})
  for i = 0, 2 do emu.write(0x4C7 + i, v[i + 1], W) end
end
local function shop()
  wallet()
  local m0, inShop = money(), false
  for f = 1, math.random(200, 500) do held.up = true held.right = (f % 160) < 25 held.left = (f % 160) > 135 tick() if rd(0xCC) ~= 0 then inShop = true break end end clear()
  local bought = 0
  for f = 1, math.random(600, 1800) do
    if rd(0xCC) ~= 0 then inShop = true end
    held.down = (f % 50) < 3 and math.random() < 0.5 held.up = (f % 50) >= 25 and (f % 50) < 28 and math.random() < 0.3
    held.a = (f % 16) < 3 held.b = (f % 400) > 394
    tick()
  end
  clear()
  for f = 1, 300 do held.b = (f % 20) < 3 held.down = f > 200 tick() end clear()
  local m1 = money() if m1 ~= m0 then bought = 1 end
  return inShop, bought, m0, m1
end
local gamer = false
local function setG(on) inMenu = true local ok = setSkill(on and 3 or 4) inMenu = false gamer = on and ok or false return ok end
local seg, stats = 0, {tele=0, nat=0, menu=0, igi=0, gstretch=0, death=0, door=0, shop=0, inshop=0, buy=0,
  grind=0, grindG=0, grindNoG=0, grind64=0, redo=0, redoOk=0, weap=0, wpick=0, wcarry=0, wkept=0, wthrow=0, wdeath=0, wpoke=0, wkinds={}, combo=0, cswitch=0, cwdeath=0}
-- Opt-in #8 segments (env, any combination; all off = previous behaviour):
--   GRIND=1  long fights in one area, stats pushed toward the caps in Gamer mode
--   REDO=1   after each death go back to the room the death happened in ($0042 forced on the next load)
--   WEAP=1   pick up / carry through room loads / throw, cycling weapon kinds $08-$0F
--            (WPOKE=1: retag the nearest lying object to the wanted kind before pickup)
--   COMBO=1  Gamer<->Intermediate switch mid-fight; death while holding a weapon
--   NEWP=0.35 share of segments drawn from the enabled new modes
-- RAM (docs/SHOP-QOL-MECHANICS.md, tools/capture_shop_qol_mechanics.py, tools/build_gamer_item_caps.py,
-- docs/RUMBLE.md): stat i of player p at $049F + 4*i + p, i = punch kick weapon throw agility
-- defense strength will stamina($04BF) maxpower($04C3); caps 63 (stats 0-7; Gamer item caps 127),
-- max power 127. Password stat slots $058E-$0595. No XP in RCR (money $04C7-$04C9 BCD).
-- Objects: slot s (0-1 players, 2-3 goons, 4-7 objects) kind $00CB+s ($08 rock, $09 knuckles,
-- $0A stick, $0B pipe, $0C chain, $0D tire, $0E box, $0F can); $0056+s bit 6 = held,
-- $03B7+s = holder; x = $008C+s (hi) $0083+s (lo).
local MODES = {}
for _, k in ipairs({"GRIND", "REDO", "WEAP", "COMBO"}) do if os.getenv(k) == "1" then MODES[#MODES+1] = k end end
local NEWP = tonumber(os.getenv("NEWP") or "0.35")
local WPOKE = os.getenv("WPOKE") == "1"
local STATN = {"punch", "kick", "weapon", "throw", "agility", "defense", "strength", "will"}
local function statStr() local t = {} for i = 0, 9 do t[#t+1] = rd(0x49F + 4*i) end return table.concat(t, ",") end
local function objX(s) return rd(0x8C + s) * 256 + rd(0x83 + s) end
local function heldBy(s) return (rd(0x56 + s) & 0x40) ~= 0 and rd(0x3B7 + s) == 0 end
local function holding() for s = 4, 7 do local k = rd(0xCB + s) if k >= 8 and k <= 0x0F and heldBy(s) then return s, k end end end
local function lying() local best, bd for s = 4, 7 do local k = rd(0xCB + s) if k >= 8 and k <= 0x0F and not heldBy(s) and (rd(0xD3 + s) & 0x7F) ~= 0x7F then local d = math.abs(objX(s) - objX(0)) if not bd or d < bd then best, bd = s, d end end end return best end
local function grind()
  local wasG = gamer
  -- Gamer must really engage ($064C == 3): retry the LEVEL menu (it fails mid-fight / under hits)
  for t = 1, 4 do if rd(0x64C) == 3 then break end setG(true) if rd(0x64C) ~= 3 then fight(60) end end
  gamer = rd(0x64C) == 3
  local cap = gamer and 127 or 63
  if gamer then stats.grindG = stats.grindG + 1 else stats.grindNoG = stats.grindNoG + 1 end
  for i = 0, 7 do local v = rd(0x49F + 4*i) if math.random() < 0.8 then v = math.random(cap - 6, cap) end emu.write(0x49F + 4*i, v, W) end
  if math.random() < 0.3 then emu.write(0x4C3, math.random(118, 127), W) end
  local n = math.random(3000, 9000)
  local t0 = frameNo
  while frameNo - t0 < n do
    fight(math.random(300, 900))
    if math.random() < 0.15 then menus() end
  end
  stats.grindStats = statStr()
  local mx = 0 for i = 0, 7 do mx = math.max(mx, rd(0x49F + 4*i)) end
  if mx > 63 then stats.grind64 = stats.grind64 + 1 end
  log("grind", "skill", rd(0x64C), "max", mx, "stats", statStr())
  if not wasG and math.random() < 0.5 then setG(false) end
end
local deathRoom
local function die(n)
  deathRoom = rd(0x42)
  alive = false emu.write(0x4BF, 1, W) fight(n or 1500) alive = true stats.death = stats.death + 1
end
local function redo()
  local tries = 0
  repeat
    die(1500)
    force = deathRoom local ok = walkUntilLoad(6300) force = nil
    if ok and rd(0x42) == deathRoom then stats.redoOk = stats.redoOk + 1 end
    stats.redo = stats.redo + 1
    if math.random() < 0.6 then for f = 1, math.random(120, 400) do held.up = true tick() end clear() end   -- same door
    fight(math.random(200, 700))
    tries = tries + 1
  until tries >= math.random(1, 4)
end
local wantKind = 8
local function pickup(maxf)
  for f = 1, maxf do
    if holding() then clear() return true end
    local s = lying()
    if not s then fight(math.min(60, maxf - f + 1)) else
      if WPOKE and rd(0xCB + s) ~= wantKind and f == 1 then emu.write(0xCB + s, wantKind, W) stats.wpoke = stats.wpoke + 1 end
      local dx = objX(s) - objX(0)
      held.right = dx > 6 held.left = dx < -6 held.up = false held.down = false
      held.b = math.abs(dx) <= 10 and (f % 8) < 3 held.y = false
      tick()
    end
  end
  clear() return holding() ~= nil
end
local function weapon(thenDie)
  local got = pickup(math.random(900, 2400))
  local s, k = holding()
  if got then stats.wpick = stats.wpick + 1 stats.wkinds[k] = (stats.wkinds[k] or 0) + 1 end
  if got and not thenDie and math.random() < 0.4 then   -- throw in place (weapons are dropped on room loads)
    for f = 1, 90 do held.y = f < 6 held.right = f > 6 and f < 40 tick() end clear() stats.wthrow = stats.wthrow + 1
  end
  if holding() and math.random() < 0.6 then
    local r = math.random()
    if r < 0.5 then force = TARGETS[math.random(#TARGETS)] end
    walkUntilLoad(6300) force = nil stats.wcarry = stats.wcarry + 1
    if holding() then stats.wkept = stats.wkept + 1 end
  end
  if thenDie then die(1500) stats.wdeath = stats.wdeath + 1 return end
  if holding() then for f = 1, 90 do held.y = f < 6 held.right = f > 6 and f < 40 tick() end clear() stats.wthrow = stats.wthrow + 1 end
  fight(math.random(200, 600))
  wantKind = wantKind == 0x0F and 8 or wantKind + 1
end
local function combo()
  if math.random() < 0.5 then
    fight(math.random(100, 500)) setG(not gamer) fight(math.random(100, 500))
    if math.random() < 0.5 then setG(not gamer) fight(math.random(60, 300)) end
    stats.cswitch = stats.cswitch + 1
  else weapon(true) stats.cwdeath = stats.cwdeath + 1 end
end
local function newSeg()
  local m = MODES[math.random(#MODES)]
  if m == "GRIND" then grind() stats.grind = stats.grind + 1
  elseif m == "REDO" then redo()
  elseif m == "WEAP" then weapon(false) stats.weap = stats.weap + 1
  else combo() stats.combo = stats.combo + 1 end
  local hs, hk = holding()
  log("seg", m, "room", string.format("%02x", rd(0x42)), "skill", rd(0x64C), "hold", hk and string.format("%02x", hk) or "-", "redo", stats.redoOk .. "/" .. stats.redo, "pick", stats.wpick, "kept", stats.wkept .. "/" .. stats.wcarry, "stats", statStr())
end
run(function()
  VC_ACTIVE, INV_ACTIVE = false, false
  if not bootToSettings() then return end
  for n = 1, 8 do if rd(0x64C) == 4 then break end press("right", 6, 20) end
  if not settingsToStreet() then return end
  inMenu = true
  if os.getenv("PW") then log("password", enterPassword(os.getenv("PW")), state()) end
  log("skill->4", setSkill(4)) inMenu = false
  log("modes", table.concat(MODES, ","), "newp", NEWP, "wpoke", tostring(WPOKE), "statsP1", statStr())
  VC_ACTIVE, INV_ACTIVE = true, true
  local f0, nextCk = frameNo, frameNo + 36000
  while frameNo - f0 < FRAMES do
    seg = seg + 1
    local r = math.random()
    if #MODES > 0 and math.random() < NEWP then newSeg()
    elseif r < 0.25 then force = TARGETS[math.random(#TARGETS)] walkUntilLoad(6300) force = nil fight(math.random(300, 900)) stats.tele = stats.tele + 1
    elseif r < 0.45 then if walkUntilLoad(6300) then fight(math.random(200, 800)) end stats.nat = stats.nat + 1
    elseif r < 0.60 then menus() stats.menu = stats.menu + 1
    elseif r < 0.70 then if gamer then setG(false) else setG(true) fight(math.random(60, 400)) setG(false) end stats.igi = stats.igi + 1
    elseif r < 0.76 then setG(true) stats.gstretch = stats.gstretch + 1          -- long Gamer stretch until a later switch
    elseif r < 0.82 then alive = false emu.write(0x4BF, 1, W) fight(1500) alive = true stats.death = stats.death + 1
    elseif SHOP and r < 0.90 and math.random() < 0.6 then local i, b = shop() stats.shop = stats.shop + 1 if i then stats.inshop = stats.inshop + 1 end stats.buy = stats.buy + b
    elseif r < 0.90 then door() stats.door = stats.door + 1
    else fight(math.random(300, 1200)) end
    if frameNo >= nextCk then
      nextCk = frameNo + 36000
      local v = {} for a, n in pairs(visited) do v[#v+1] = string.format("%02x:%d", a, n) end table.sort(v)
      local st = {0, 0, 0, 0} for x = 0, 127 do local q = rd(0x1D00 + x) if q <= 3 then st[q+1] = st[q+1] + 1 end end
      log(string.format("CK emu %.2fh", (frameNo - f0) / 216000), "loads", loads, "maxBlank", maxBlank, "segs", seg,
          "tele", stats.tele, "nat", stats.nat, "menu", stats.menu, "igi", stats.igi, "gstr", stats.gstretch, "death", stats.death, "door", stats.door, "shop", stats.shop, "inshop", stats.inshop, "buy", stats.buy, "money", string.format("%06x", money()),
          "skill", rd(0x64C), "VC", VC.checks, "row", VC.rowHits, "chr", VC.chrHits, "invP", INV.persist, "hits", hits,
          "rowstates", table.concat(st, "/"),
          "new", string.format("grindG=%d/%d noG=%d >63=%d ", stats.grindG, stats.grind, stats.grindNoG, stats.grind64) .. string.format("grind=%d redo=%d/%d weap=%d pick=%d carry=%d kept=%d throw=%d wdeath=%d poke=%d combo=%d sw=%d cwd=%d", stats.grind, stats.redoOk, stats.redo, stats.weap, stats.wpick, stats.wcarry, stats.wkept, stats.wthrow, stats.wdeath, stats.wpoke, stats.combo, stats.cswitch, stats.cwdeath),
          "wk", (function() local t = {} for k, n in pairs(stats.wkinds) do t[#t+1] = string.format("%02x:%d", k, n) end table.sort(t) return table.concat(t, " ") end)(), "statsP1", statStr(), "bk1C00", hex(0x1C00, 0xC0), "visited", table.concat(v, " "))
      inlog:flush()
    end
  end
  log("SUMMARY loads", loads, "segs", seg, "VC", VC.checks, "row", VC.rowHits, "chr", VC.chrHits, "invP", INV.persist, "hits", hits)
  inlog:close()
end)
