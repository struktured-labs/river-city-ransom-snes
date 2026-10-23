-- Issue #8 coverage tour: visit Sherman Park (restroom backdrop) and the
-- mid/late areas. Each leg walks off the current area; while the game's own
-- area load runs (forced blank, $1CA0 != 0) the NES area tracker $0042 is held
-- at the target, so the game's normal load routine builds the target area
-- (only the source area/entry point differ from a real transition). Then:
-- fight goons, optionally I->G->I mid-fight, then leave by a NATURAL exit and
-- fight in the neighbour too. vis_check (tilemap + CHR vs expected) and the
-- row invariant run throughout. Env: PW, SEED, LEGS, TARGETS (hex list).
dofile(os.getenv("RCR_LIB")) dofile(os.getenv("INV_LIB")) dofile(os.getenv("VC_LIB"))
dofile(os.getenv("RCR_LIB"):gsub("lib.lua", "password.lua"))
math.randomseed(tonumber(os.getenv("SEED") or "1"))
local LEGS = tonumber(os.getenv("LEGS") or "20")
local TARGETS = {}
for h in (os.getenv("TARGETS") or "04 04 06 07 09 0a 0d 0f 10 11 13 14 18 1a 1b 04"):gmatch("%x+") do TARGETS[#TARGETS+1] = tonumber(h, 16) end
emu.addEventCallback(function() invariantCheck() visCheck() end, emu.eventType.startFrame)
local prev, loads, force, inMenu, lastLoad = 0, 0, nil, false, 0
local visited = {}
emu.addEventCallback(function()
  local s = rd(0x1CA0)
  if force and s ~= 0 then emu.write(0x42, force, W) end
  if prev ~= 0 and s == 0 then
    loads = loads + 1 lastLoad = frameNo
    if force then force = nil end
    if not inMenu then
      local a = rd(0x42) visited[a] = (visited[a] or 0) + 1
      log("LOAD", loads, string.format("area %02x", a), state(), "skill", rd(0x64C))
      pendShot = {f = frameNo + 60, n = loads, a = a}
    end
  end
  prev = s
  if pendShot and frameNo >= pendShot.f then if pendShot.n <= 80 then shot(string.format("load%03d_%02x", pendShot.n, pendShot.a)) end pendShot = nil end
end, emu.eventType.startFrame)
local PATS = {{right=true}, {right=true, up=true}, {right=true, down=true}, {left=true}, {left=true, up=true}, {left=true, down=true}, {up=true}}
local function walkUntilLoad(maxf, attack)
  local l0, i, since = loads, 1, frameNo
  for f = 1, maxf do
    emu.write(0x4BF, 0x7F, W)
    local p = PATS[i]
    for _, k in ipairs({"left", "right", "up", "down"}) do held[k] = p[k] end
    held.y = attack and math.random() < 0.08 held.b = attack and math.random() < 0.04
    step()
    if loads > l0 then for k in pairs(held) do held[k] = nil end return true end
    if frameNo - since > 900 then i = i % #PATS + 1 since = frameNo end
  end
  for k in pairs(held) do held[k] = nil end
  return false
end
local function fight(n)
  for f = 1, n do
    emu.write(0x4BF, 0x7F, W)
    local ph = (f // 45) % 4
    held.left = ph == 0 held.right = ph == 2 held.up = ph == 1 and f % 90 < 20 held.down = ph == 3 and f % 90 < 20
    held.y = math.random() < 0.15 held.b = math.random() < 0.10
    step()
  end
  for k in pairs(held) do held[k] = nil end
end
local function switchIGI(tag)
  inMenu = true
  local a = setSkill(3) step(math.random(20, 200)) local b = setSkill(4)
  inMenu = false
  log("SWITCH", tag, "I->G", a, "G->I", b, "skill", rd(0x64C))
end
run(function()
  VC_ACTIVE, INV_ACTIVE = false, false
  if not bootToSettings() then return end
  for n = 1, 8 do if rd(0x64C) == 4 then break end press("right", 6, 20) end
  if not settingsToStreet() then return end
  inMenu = true
  log("password", enterPassword(os.getenv("PW")), state())
  log("skill->4", setSkill(4)) inMenu = false
  VC_ACTIVE, INV_ACTIVE = true, true
  local switches = 0
  for leg = 1, LEGS do
    local t = TARGETS[(leg - 1) % #TARGETS + 1]
    force = t
    local ok = walkUntilLoad(6300, true)
    force = nil
    log("LEG", leg, string.format("target %02x", t), "reached", ok, string.format("area %02x", rd(0x42)))
    fight(math.random(300, 900))                         -- goons right after the load
    if math.random() < 0.6 then switchIGI("leg" .. leg) switches = switches + 1 end   -- mid-fight I->G->I
    fight(math.random(200, 600))
    if walkUntilLoad(6300, true) then fight(math.random(200, 600)) end   -- natural exit, fight in neighbour
    if leg % 4 == 0 then
      local v = {} for a, n in pairs(visited) do v[#v+1] = string.format("%02x:%d", a, n) end table.sort(v)
      log("progress leg", leg, "loads", loads, "switches", switches, "VC checks", VC.checks, "row", VC.rowHits, "chr", VC.chrHits, "inv persist", INV.persist, "visited", table.concat(v, " "))
    end
  end
  local v = {} for a, n in pairs(visited) do v[#v+1] = string.format("%02x:%d", a, n) end table.sort(v)
  log("SUMMARY loads", loads, "switches", switches, "VC checks", VC.checks, "row hits", VC.rowHits, "chr hits", VC.chrHits, "inv persistent", INV.persist, "visited", table.concat(v, " "))
end)
