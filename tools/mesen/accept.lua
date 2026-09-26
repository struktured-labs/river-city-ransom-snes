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
heldActor = nil heldBy = nil
heldA = {} heldH = {}
for b=0xC1,0xC8 do
  -- the held actor is the holder's $03B7 (read when the $FC branch is taken)
  emu.addMemoryCallback(function() heldPart = true heldBy = rd(0x47) heldActor = rd(0x3B7 + rd(0x47)) end, emu.callbackType.exec, b*65536+0xEE4B, b*65536+0xEE4B, emu.cpuType.snes, emu.memType.snesMemory)
  emu.addMemoryCallback(function() heldPart = false end, emu.callbackType.exec, b*65536+0xEF7D, b*65536+0xEF7D, emu.cpuType.snes, emu.memType.snesMemory)
  emu.addMemoryCallback(function() heldPart = false end, emu.callbackType.exec, b*65536+0xED0E, b*65536+0xED0E, emu.cpuType.snes, emu.memType.snesMemory)
end
emu.addMemoryCallback(function(addr, value)
  if (addr & 3) ~= 2 then return end
  writer[(addr & 0xFF) // 4] = rd(0x47)
  heldW[(addr & 0xFF) // 4] = heldPart
  heldA[(addr & 0xFF) // 4] = heldPart and heldActor or nil
  heldH[(addr & 0xFF) // 4] = heldPart and heldBy or nil
  slotHist[rd(0x47)] = (slotHist[rd(0x47)] or 0) + 1
end, emu.callbackType.write, 0x200, 0x2FF, emu.cpuType.snes, emu.memType.snesWorkRam)
function cg(i) return emu.read(i*2, CG) + 256*emu.read(i*2+1, CG) end
-- Red outline audit (Gamer). Judged at tile level, from PPU OAM + VRAM:
-- every visible sprite on a red palette (4, 5, 7) may use only indices 0-3
-- and 5; each color-5 (red) pixel must touch a transparent pixel in its tile
-- (the outer silhouette; nothing red inside the body), and each color-1 pixel
-- that touches a transparent pixel must be color 5 (the silhouette is whole,
-- within a tile; a tile edge counts as not outer). Plane 2 only where the
-- original index was 1, so skin, shirt and jeans colors are never changed.
-- Palette 6 is never used. The screen count is reported only: overlapping
-- sprites and the background change what touches a red pixel on screen.
function rgb(c) local r, g, b = c & 31, (c >> 5) & 31, (c >> 10) & 31 return (((r << 3) | (r >> 2)) << 16) | (((g << 3) | (g >> 2)) << 8) | ((b << 3) | (b >> 2)) end
local function edgeBad(msg) EDGE.bad = EDGE.bad + 1 if #EDGE.badList < 5 then EDGE.badList[#EDGE.badList+1] = msg end end
function edgeAudit()
  local buf = emu.getScreenBuffer()
  local W_ = 256 local H_ = #buf // 256
  local redc = rgb(RED)
  local body = {}
  for _,p in ipairs({4, 5, 7}) do for c=1,3 do body[rgb(cg(p*16+0x80+c))] = true end end
  local function px(x, y) if x < 0 or y < 0 or x >= W_ or y >= H_ then return -1 end return buf[y*W_ + x + 1] & 0xFFFFFF end
  EDGE.frames = EDGE.frames + 1
  local st = emu.getState()
  local base, off = st["ppu.oamBaseAddress"], st["ppu.oamAddressOffset"]
  for i=0,127 do
    local sy = emu.read(i*4+1, OAMT)
    local attr = emu.read(i*4+3, OAMT)
    local pal = (attr >> 1) & 7
    local tile = emu.read(i*4+2, OAMT)
    local w = (base + ((attr & 1) ~= 0 and off or 0) + tile * 16) & 0x7FFF
    local function vb(k) return emu.read(((w + (k >> 1)) & 0x7FFF) * 2 + (k & 1), V) end
    if sy < 0xE0 and pal == 6 then edgeBad(string.format("f%d spr%d on palette 6", frameNo, i)) end
    if sy < 0xE0 and pal <= 3 then
      -- players, townsfolk, weapons: index 5 pixels are drawn with color 5 =
      -- color 1 of the same palette (palBad), so they look exactly as the
      -- parent's color-1 pixels; no other index may appear
      EDGE.plain = EDGE.plain + 1
      for r=0,7 do
        local p0, p1, p2, p3 = vb(2*r), vb(2*r+1), vb(16+2*r), vb(17+2*r)
        local wrong = p3 | (p2 & ~(p0 & ~p1) & 0xFF)
        if wrong ~= 0 then EDGE.plainBad = EDGE.plainBad + 1 edgeBad(string.format("f%d spr%d plain tile%02x row%d", frameNo, i, tile, r)) end
        for c=0,7 do if (p2 >> c) & 1 == 1 then EDGE.plain5 = EDGE.plain5 + 1 end end
      end
    end
    if sy < 0xE0 and (pal == 4 or pal == 5 or pal == 7) then
      local pxl = {}
      for r=0,7 do pxl[r] = {} local p0, p1, p2, p3 = vb(2*r), vb(2*r+1), vb(16+2*r), vb(17+2*r)
        for c=0,7 do local sh = 7 - c
          pxl[r][c] = ((p0 >> sh) & 1) | (((p1 >> sh) & 1) << 1) | (((p2 >> sh) & 1) << 2) | (((p3 >> sh) & 1) << 3)
        end end
      EDGE.tiles = EDGE.tiles + 1
      for r=0,7 do for c=0,7 do
        local v = pxl[r][c]
        local function nb(want) for _,d in ipairs({{-1,0},{1,0},{0,-1},{0,1}}) do local rr, cc = r+d[1], c+d[2] if rr >= 0 and rr < 8 and cc >= 0 and cc < 8 and pxl[rr][cc] == want then return true end end return false end
        -- in-tile view, reported only: a red pixel on a tile border may be
        -- outer only across the border, and a dark one next to a transparent
        -- pixel may be covered by another sprite of the same metasprite (the
        -- composed audit below decides)
        if v == 5 then
          EDGE.tileRed = EDGE.tileRed + 1
          if not nb(0) then EDGE.redInside = EDGE.redInside + 1 end
        elseif v == 1 then
          if nb(0) then EDGE.darkEdge = EDGE.darkEdge + 1 else EDGE.darkInside = EDGE.darkInside + 1 end
        elseif v ~= 0 and v ~= 2 and v ~= 3 then
          edgeBad(string.format("f%d spr%d tile%02x idx%d", frameNo, i, tile, v))
        end
      end end
    end
  end
  for y=0,H_-1 do for x=0,W_-1 do
    if px(x, y) == redc then
      EDGE.red = EDGE.red + 1
      local all = true
      for _,q in ipairs({px(x-1,y), px(x+1,y), px(x,y-1), px(x,y+1)}) do if q ~= redc and not body[q] then all = false end end
      if all then EDGE.screenInside = EDGE.screenInside + 1 end
    end
  end end
end
-- Composed silhouette audit (Gamer), per actor: the game's own sprites for
-- this frame (NES OAM $0200, drawing slot from the write callback; a held
-- part belongs to the held actor) are drawn into one canvas per actor, pixel
-- indices from VRAM (lower OAM index on top). For an enemy actor (goon bit on
-- a non-item palette), a silhouette-edge pixel is a visible outline pixel
-- (index 1 or 5) with a 4-neighbour no sprite of the actor covers.
--   comp red inside: a visible red pixel all of whose 4 neighbours the actor
--     covers (fails check 4)
--   coverage: red share of the silhouette-edge outline pixels
function compositeAudit()
  local st = emu.getState()
  local base = (st["ppu.oamBaseAddress"] + st["ppu.oamAddressOffset"]) & 0x7FFF
  local groups = {}
  for i=0,63 do
    local y = rd(0x200+i*4)
    local s = writer[i]
    if y < 0xEF and s ~= nil then
      local o = (heldW[i] == true) and heldA[i] or s
      if o ~= nil then
        local a = rd(0x202+i*4)
        groups[o] = groups[o] or {}
        table.insert(groups[o], {x=rd(0x203+i*4), y=y, t=rd(0x201+i*4), a=a, enemy=((a & 4) ~= 0 and (a & 3) ~= 2)})
      end
    end
  end
  for o, spr in pairs(groups) do
    local anyEnemy = false
    for _, sp in ipairs(spr) do if sp.enemy then anyEnemy = true end end
    if anyEnemy then
      local canvas = {}
      for _, sp in ipairs(spr) do
        local w = (base + sp.t * 16) & 0x7FFF
        for r=0,7 do
          local rr = (sp.a & 0x80) ~= 0 and 7 - r or r
          local p0, p1 = emu.read(((w + rr) & 0x7FFF) * 2, V), emu.read(((w + rr) & 0x7FFF) * 2 + 1, V)
          local p2, p3 = emu.read(((w + 8 + rr) & 0x7FFF) * 2, V), emu.read(((w + 8 + rr) & 0x7FFF) * 2 + 1, V)
          for c=0,7 do
            local cc = (sp.a & 0x40) ~= 0 and c or 7 - c
            local v = ((p0 >> cc) & 1) | (((p1 >> cc) & 1) << 1) | (((p2 >> cc) & 1) << 2) | (((p3 >> cc) & 1) << 3)
            local k = (sp.y + r) * 512 + sp.x + c
            if v ~= 0 and canvas[k] == nil then canvas[k] = sp.enemy and v or -v end
          end
        end
      end
      for k, v in pairs(canvas) do
        if v == 1 or v == 5 then
          local edge = canvas[k-1] == nil or canvas[k+1] == nil or canvas[k-512] == nil or canvas[k+512] == nil
          if edge then EDGE.cEdge = EDGE.cEdge + 1 if v == 5 then EDGE.cRed = EDGE.cRed + 1 end
          elseif v == 5 then EDGE.cInside = EDGE.cInside + 1 edgeBad(string.format("f%d actor%d red inside the composed body at x%d y%d", frameNo, o, k % 512, k // 512)) end
        end
      end
    end
  end
end
-- red share of the composed silhouette-edge outline pixels the build must reach
-- (4291, in-tile rule only: 58%; composed silhouette from the metasprites: 88%)
COVERAGE_MIN = 0.80
function coverage() return EDGE.cEdge > 0 and EDGE.cRed / EDGE.cEdge or 0 end
-- one frame's outline audit. Returns counts; records failures in stats.
stats = {}
-- weapons/items: objects of sprite kind $08-$11 (bank 6 $8000 kind table,
-- room object list bank 13 $B6D9) or a held-object sub-part. Never outlined.
ITEM = {spr=0, red=0, held=0, heldGoon=0, ground=0, flying=0, bad={}}
CARRY = {spr=0, unred=0, linkBad=0, after=0, afterUnred=0, slots={}, bad={}, shots=0}
EDGE = {plain=0, plain5=0, plainBad=0, frames=0, red=0, bad=0, badList={}, tiles=0, tileRed=0, redInside=0, darkEdge=0, darkInside=0, screenInside=0, cEdge=0, cRed=0, cInside=0}
itemShots = {held=0, ground=0}
TILES = {item={}, body={}, carried={}, other={}}
function resetStats() stats = {frames=0, goonSpr=0, goonRed=0, otherSpr=0, otherRed=0, snesMismatch=0, palBad=0, goonPal2=0, bad={}} end
function audit(tag)
  stats.frames = stats.frames + 1
  frameHeldGoon = false frameGround = false frameCarry = false
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
      -- owner: the drawing slot, or for a held-object part the held actor
      local o = held and heldA[i] or s
      local okind = rd(0xCB + o)
      local ocls = rd(0x4F5 + o)
      local item = (held and okind >= 8) or (not held and kind >= 8 and kind <= 0x11)
      local enemy = o >= 2 and o <= 7 and ocls < 0x19 and okind < 8 and rd(0xCC) == 0
      if sk ~= 3 then enemy = false end
      if held and heldH[i] ~= nil and heldH[i] <= 1 and o >= 2 and o <= 7 and okind < 8 then
        -- a player carrying a fighter: cross-check the link from the carried
        -- side (its $03B7 points back, $4F state $15 = being carried)
        CARRY.spr = CARRY.spr + 1 frameCarry = true CARRY.slots[o] = frameNo
        TILES.carried[rd(0x201+i*4)] = true
        -- ($16 = being thrown: on the release frame the sprites were written
        -- while carried, before the game advanced the goon's state)
        local cst = rd(0x4F + o) & 0x7F
        if rd(0x3B7 + o) ~= heldH[i] or (cst ~= 0x15 and cst ~= 0x16) then CARRY.linkBad = CARRY.linkBad + 1 end
        if not marked then CARRY.unred = CARRY.unred + 1 if #CARRY.bad < 6 then CARRY.bad[#CARRY.bad+1] = string.format("CARRIED %s spr%d holder%d held%d tile%02x attr%02x", tag, i, heldH[i], o, rd(0x201+i*4), a) end end
      end
      if not held and s >= 2 and s <= 7 and CARRY.slots[s] and frameNo - CARRY.slots[s] > 0 and frameNo - CARRY.slots[s] <= 90 and kind < 8 then
        -- the same goon drawn by its own slot within 1.5 s after being carried (thrown / dropped)
        CARRY.after = CARRY.after + 1
        if not marked then CARRY.afterUnred = CARRY.afterUnred + 1 end
      end
      local tile = rd(0x201+i*4)
      if not (held and heldH[i] ~= nil and heldH[i] <= 1 and o >= 2 and o <= 7 and okind < 8) then TILES.other[tile] = true end
      if item then TILES.item[tile] = true elseif s >= 2 and s <= 7 and kind < 8 then TILES.body[tile] = true end
      if item then
        ITEM.spr = ITEM.spr + 1
        if held then ITEM.held = ITEM.held + 1 if s >= 2 and s <= 7 and kind < 8 and o ~= s then ITEM.heldGoon = ITEM.heldGoon + 1 frameHeldGoon = true end
        else ITEM.ground = ITEM.ground + 1 frameGround = true if (rd(0x56 + s) & 0x80) ~= 0 then ITEM.flying = ITEM.flying + 1 end end
        if marked then ITEM.red = ITEM.red + 1 if #ITEM.bad < 8 then ITEM.bad[#ITEM.bad+1] = string.format("ITEM %s spr%d slot%d kind%02x held=%s tile%02x attr%02x", tag, i, s, kind, tostring(held), rd(0x201+i*4), a) end end
      end
      if enemy then
        stats.goonSpr = stats.goonSpr + 1
        if marked and (a & 3) == 2 then stats.goonPal2 = stats.goonPal2 + 1 end
        if marked then stats.goonRed = stats.goonRed + 1 elseif #stats.bad < 6 then stats.bad[#stats.bad+1] = string.format("UNMARKED %s spr%d slot%d type%02x attr%02x", tag, i, s, t, a) end
      else
        stats.otherSpr = stats.otherSpr + 1
        if marked then stats.otherRed = stats.otherRed + 1 if #stats.bad < 6 then stats.bad[#stats.bad+1] = string.format("%s spr%d slot%d type%02x attr%02x", tag, i, s, t, a) end end
      end
    end
  end
  if frameHeldGoon and itemShots.held < 3 and frameNo % 90 == 0 then itemShots.held = itemShots.held + 1 shot(string.format("8-goon-holding-weapon-%d", itemShots.held)) end
  if frameGround and not frameHeldGoon and itemShots.ground < 3 and frameNo % 90 == 0 then itemShots.ground = itemShots.ground + 1 shot(string.format("8-weapon-on-ground-%d", itemShots.ground)) end
  if frameCarry and CARRY.shots < 3 and frameNo - (CARRY.lastShot or -999) >= 45 then CARRY.shots = CARRY.shots + 1 CARRY.lastShot = frameNo shot(string.format("9-alex-carrying-goon-%d", CARRY.shots)) end
  -- every sprite palette: color 5 (recolored outline) = color 1. Gamer:
  -- palettes 4, 5 and 7 = palettes 0, 1 and 3 with color 5 red and color 1
  -- still dark (NES palette 2, items, never moves to a red copy).
  for p=0,3 do
    if cg(0x80+p*16+5) ~= cg(0x80+p*16+1) then stats.palBad = stats.palBad + 1 break end
  end
  if sk == 3 then
    for _,p in ipairs({0, 1, 3}) do
      local base, red = 0x80+p*16, 0xC0+p*16
      if cg(red) ~= cg(base) or cg(red+1) ~= cg(base+1) or cg(red+2) ~= cg(base+2) or cg(red+3) ~= cg(base+3) or cg(red+5) ~= RED then stats.palBad = stats.palBad + 1 break end
    end
  end
  if sk == 3 and frameNo % 15 == 0 then edgeAudit() compositeAudit() end
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
        local want = (nattr & 0xC0) | ((nattr & 3) << 1) | (((nattr & 0x20) ~= 0) and 0 or 0x30) | ((((nattr & 4) ~= 0) and (nattr & 3) ~= 2) and 8 or 0)
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
  log(string.format("%s frames=%d goonSpr=%d goonRed=%d otherSpr=%d otherRed=%d snesMismatch=%d palBad=%d goonNesPal2=%d %s", tag, stats.frames, stats.goonSpr, stats.goonRed, stats.otherSpr, stats.otherRed, stats.snesMismatch, stats.palBad, stats.goonPal2, table.concat(stats.bad, "; ")))
  log(string.format("%s plain-sprite tiles=%d color5px=%d badTiles=%d (color 5 = color 1 in palettes 0-3: palBad above)", tag, EDGE.plain, EDGE.plain5, EDGE.plainBad))
  log(string.format("%s composed silhouette: edgeOutlinePx=%d red=%d coverage=%.1f%% redInsideComposedBody=%d | in-tile (reported): redTiles=%d tileRedPx=%d redNoInTileTransparent=%d darkNextToInTileTransparent=%d interiorDark=%d | screen redPx=%d screenRedSurrounded(reported)=%d %s", tag, EDGE.cEdge, EDGE.cRed, 100 * coverage(), EDGE.cInside, EDGE.tiles, EDGE.tileRed, EDGE.redInside, EDGE.darkEdge, EDGE.darkInside, EDGE.red, EDGE.screenInside, table.concat(EDGE.badList, " ")))
  local ok = stats.otherRed == 0 and stats.goonRed == stats.goonSpr and stats.palBad == 0 and stats.snesMismatch == 0 and EDGE.bad == 0
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
function stepA(n, tag) for i=1,n do writer = {} heldW = {} heldA = {} heldH = {} step() audit(tag) end end

-- Soft reset with work RAM cleared as at power-on (Mesen starts from zeroed
-- RAM), so check 9 plays the same fight as the RCR_ONLY_CARRY run.
function powerCycle()
  for a=0,0x1FFFF do emu.write(a, 0, W) end
  emu.reset()
end
function carryPhase()
  -- 9. carry a knocked-down goon: walk to the nearest goon and punch; the
  -- punch button over a downed goon picks it up, pressing again throws it.
  resetStats()
  local function px(s) return rd(0x83+s) + 256*rd(0x8C+s) end
  for f=1,6000 do
    emu.write(0x4BF, 0x7F, W)
    local best, bd = nil, 1e9
    for s=2,7 do if rd(0xCB+s) < 8 and (rd(0xD3+s) & 0x7F) ~= 0x7F and px(s) > 0 then local d = math.abs(px(s)-px(0)) if d < bd then bd, best = d, s end end end
    held = {}
    local carrying = (rd(0x56) & 0x40) ~= 0 and rd(0x3B7) >= 2 and rd(0x3B7) <= 7 and rd(0xCB + rd(0x3B7)) < 8
    local st4f = best and (rd(0x4F + best) & 0x7F) or 0
    if carrying then
      -- carry it a little, then punch again to throw it
      carryT = (carryT or 0) + 1
      held.right = (carryT % 120) < 60 held.left = not held.right
      if carryT % 150 == 90 then held.y = true end
    elseif best and (st4f == 0x11 or st4f == 0x12) then
      -- goon lying on the ground ($4F state $11/$12): line up on it, then punch = pick up
      carryT = 0
      local dx = px(best) - px(0)
      local dy = rd(0x9E+best) - rd(0x9E)
      if dx > 3 then held.right = true elseif dx < -3 then held.left = true end
      if dy > 1 then held.down = true elseif dy < -1 then held.up = true end
      if math.abs(dx) <= 6 and math.abs(dy) <= 1 then held.y = (f % 10) < 2 end
    elseif best then
      carryT = 0
      local dx = px(best) - px(0)
      local dy = rd(0x9E+best) - rd(0x9E)
      if dx > 6 then held.right = true elseif dx < -6 then held.left = true end
      if dy > 2 then held.down = true elseif dy < -2 then held.up = true end
      if math.abs(dx) <= 12 and math.abs(dy) <= 4 then held.y = (f % 16) < 3 end
      if (f % 40) == 20 then held.b = true end
    else
      held.right = (f % 200) < 150
      if (f % 40) == 20 then held.b = true end
    end
    -- unstick: if Alex moved less than 4 px in 90 frames while not carrying
    -- (pinned against scenery or a goon out of reach), walk away diagonally
    -- for 60 frames, alternating up-left and down-right
    local ax = px(0)
    if f % 90 == 0 then
      if not carrying and lastAx and math.abs(ax - lastAx) < 4 then unstick = 60 unstickN = (unstickN or 0) + 1 end
      lastAx = ax
    end
    if (unstick or 0) > 0 then
      unstick = unstick - 1
      held = {}
      if unstickN % 2 == 1 then held.up = true held.left = true else held.down = true held.right = true end
    end
    if f % 300 == 0 then log(string.format("carry phase f=%d best=%s dx=%d dy=%d goon4F=%02x alexX=%d alex4F=%02x room=%02x carried=%d", f, tostring(best), best and (px(best)-px(0)) or 0, best and (rd(0x9E+best)-rd(0x9E)) or 0, best and rd(0x4F+best) or 0, px(0), rd(0x4F), rd(0x42), CARRY.spr), state()) end
    writer = {} heldW = {} heldA = {} heldH = {} step() audit("carry") auditEnd()
    if CARRY.spr > 400 and CARRY.after > 200 and f > 1200 then break end
  end
  held = {}
  -- for the snes9x harness, which has no write callbacks: tiles drawn only
  -- as carried-goon parts
  local ct = {} for t,_ in pairs(TILES.carried) do if not TILES.other[t] then ct[#ct+1] = string.format("%02x", t) end end table.sort(ct)
  log("carried-only tiles", table.concat(ct, " "))
  return report("carry", true) and CARRY.spr > 0 and CARRY.unred == 0 and CARRY.linkBad == 0 and CARRY.after > 0 and CARRY.afterUnred == 0,
    string.format("carriedSpr=%d unred=%d linkBad=%d afterSpr=%d afterUnred=%d shots=%d %s", CARRY.spr, CARRY.unred, CARRY.linkBad, CARRY.after, CARRY.afterUnred, CARRY.shots, table.concat(CARRY.bad, "; "))
end

-- Check 9 over several fights, as in gamer_accept_snes9x.py: each attempt
-- starts from power-on RAM and waits a different number of frames on the
-- skill screen (the game's random numbers run every frame, so this picks the
-- fight). The first attempt in which Alex carries a goon decides the check;
-- the criteria are the same in every attempt. Mesen does not replay a fight
-- exactly from run to run, so the list is long: most fights end without a
-- goon lying still long enough to be picked up.
CARRY_WAITS = {2, 11, 23, 0, 4, 28, 37, 43, 6, 1, 3, 5, 7, 8, 9, 10, 12, 13, 14, 15}
function carryCheck()
  local waits = CARRY_WAITS
  if os.getenv("RCR_CARRY_WAIT") then waits = {tonumber(os.getenv("RCR_CARRY_WAIT"))} end
  local ok, detail = false, "no attempt"
  for _, w in ipairs(waits) do
    powerCycle()
    if not bootToSettings() then check("9 reach settings after reset", false) return end
    emu.write(0x64C, 1, W)   -- the skill survives a reset; start from power-on's
    while rd(0x64C) ~= 3 do press("right", 6, 20) end
    step(w)
    if not settingsToStreet() then check("9 reached the street after reset", false) return end
    ok, detail = carryPhase()
    log("carry attempt", w, tostring(ok), detail)
    if CARRY.spr > 0 then break end
  end
  check("9 a goon carried by Alex keeps its red outline (and after it is thrown/dropped)", ok, detail)
end

run(function()
  if os.getenv("RCR_ONLY_CARRY") then
    -- Focused check 9 run: the shortest boot to the street (as in the other
    -- audits), so every build reaches the same fight regardless of how its
    -- earlier checks played out.
    if not bootToSettings() then check("1 reach settings", false) return end
    carryCheck()
    return
  end
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
      writer = {} heldW = {} heldA = {} heldH = {} step() audit("street") auditEnd()
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
  check("4 red only on goons (by actor), only on their outer silhouette, no other color changed; palettes correct", report("street", true) and EDGE.tileRed > 0 and coverage() >= COVERAGE_MIN, string.format("coverage=%.1f%% (min %.0f%%)", 100 * coverage(), 100 * COVERAGE_MIN))
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
  for i=1,120 do writer = {} heldW = {} heldA = {} heldH = {} step() audit("pause") auditEnd() if rd(0x3F) ~= 0 then sawPause = true local n = redCount() minRed = math.min(minRed, n) maxRed = math.max(maxRed, n) end end
  shot("5-paused")
  local snapPaused = nesSnap()
  local changed = 0 for i=0,255 do if snapPaused[i] ~= snapBefore[i] then changed = changed + 1 end end
  log(string.format("pause: red sprites before=%d (visible %d) during=%d..%d, NES OAM bytes changed=%d", redBefore, visBefore, minRed, maxRed, changed))
  local pauseOk = report("paused", false) and redBefore > 0 and minRed > 0
  press("start", 6, 2)
  for i=1,120 do writer = {} heldW = {} heldA = {} heldH = {} step() audit("unpause") auditEnd() end
  shot("5-after-unpause")
  local palSame = true for i=0x80,0xBF do if cg(i) ~= before[i] then palSame = false end end
  resetStats()
  for i=1,240 do held.right = (i % 60) < 30 writer = {} heldW = {} heldA = {} heldH = {} step() audit("after-pause") auditEnd() end
  held = {}
  local afterOk = report("after-pause", true)
  check("5 pause/unpause: marks + palettes intact", sawPause and pauseOk and afterOk and palSame, string.format("sawPause=%s palSame=%s", tostring(sawPause), tostring(palSame)))
  -- 6. low stamina (forced), outline must persist
  resetStats()
  for i=1,240 do emu.write(0x4BF, 2, W) held.right = (i % 40) < 20 held.y = (i % 20) == 5 writer = {} heldW = {} heldA = {} heldH = {} step() audit("lowstam") auditEnd() end
  held = {}
  shot("6-low-stamina")
  check("6 outline persists at low stamina (stam forced to 2)", report("lowstam", true), state())
  -- 9 from a fresh boot, as in the RCR_ONLY_CARRY run: the fights after the
  -- earlier checks differ between builds, and a goon may never go down. A
  -- reset keeps state outside work RAM (the sound CPU's among it), so first
  -- come back to the skill screen the way the RCR_ONLY_CARRY run does; each
  -- attempt then resets from the same screen.
  powerCycle()
  if not bootToSettings() then check("9 reach settings after reset", false) return end
  carryCheck()
  check("8 no weapon/item sprite outlined (on ground, thrown, held by a goon)", ITEM.red == 0 and ITEM.heldGoon > 0 and ITEM.ground > 0,
    string.format("itemSpr=%d red=%d heldSpr=%d heldByGoonSpr=%d groundSpr=%d flyingSpr=%d shots held=%d ground=%d %s", ITEM.spr, ITEM.red, ITEM.held, ITEM.heldGoon, ITEM.ground, ITEM.flying, itemShots.held, itemShots.ground, table.concat(ITEM.bad, "; ")))
  local it, both = {}, {}
  for t,_ in pairs(TILES.item) do it[#it+1] = string.format("%02x", t) if TILES.body[t] then both[#both+1] = string.format("%02x", t) end end
  table.sort(it) table.sort(both)
  log("item tiles", table.concat(it, " "), "shared with enemy bodies:", table.concat(both, " "))
  log("final", state())
end)
