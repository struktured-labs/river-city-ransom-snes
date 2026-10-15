-- Issue #8 repro attempt: load a late-game password, switch skill
-- Intermediate -> Gamer -> Intermediate, then walk/fight through many areas.
-- vis_check.lua compares every BG tilemap row and BG CHR slot in VRAM to the
-- expected content in settled gameplay; row_invariant.lua is also active.
dofile(os.getenv("RCR_LIB")) dofile(os.getenv("INV_LIB")) dofile(os.getenv("VC_LIB"))
dofile(os.getenv("RCR_LIB"):gsub("lib.lua", "password.lua"))
math.randomseed(tonumber(os.getenv("SEED") or "1"))
local FRAMES = tonumber(os.getenv("FRAMES") or "60000")
local SWITCH_EVERY = tonumber(os.getenv("SWITCH_EVERY") or "3")
emu.addEventCallback(function() invariantCheck() visCheck() end, emu.eventType.startFrame)
local prev, start, areas, lastArea, inMenu = 0, nil, 0, 0, false
emu.addEventCallback(function()
  local s = rd(0x1CA0)
  if prev == 0 and s ~= 0 then start = frameNo end
  if prev ~= 0 and s == 0 and start and not inMenu then
    areas = areas + 1 lastArea = frameNo patIdx, patSince = 1, frameNo
    if areas <= 60 then log("AREA", areas, "blank", frameNo - start, state(), "skill", rd(0x64C)) end
    if areas <= 40 then pendShot = {f = frameNo + 90, n = areas} end
  end
  prev = s
  if pendShot and frameNo >= pendShot.f then shot(string.format("area%03d", pendShot.n)) pendShot = nil end
end, emu.eventType.startFrame)
run(function()
  VC_ACTIVE, INV_ACTIVE = false, false
  if not bootToSettings() then return end
  for n = 1, 8 do if rd(0x64C) == 4 then break end press("right", 6, 20) end
  if not settingsToStreet() then return end
  inMenu = true
  local ok = enterPassword(os.getenv("PW")) shot("after_pw")
  log("password", ok, state(), "skill", rd(0x64C))
  log("skill->4", setSkill(4)) inMenu = false
  VC_ACTIVE, INV_ACTIVE = true, true
  local switches, f0 = 0, frameNo
  PATS = {{right=true}, {right=true, up=true}, {right=true, down=true}}
  if os.getenv("WALK") == "left" then for _, p in ipairs(PATS) do if p.right then p.right = nil p.left = true end end end
  patIdx, patSince = 1, frameNo
  local lastSwitchArea = 0
  while frameNo - f0 < FRAMES do
    emu.write(0x4BF, 0x7F, W)                -- keep the player alive
    -- exits can be up/down-right (e.g. Sticksville); cycle movement patterns
    -- while no area has loaded, biased to keep heading the same way
    local pat = PATS[patIdx]
    for _, k in ipairs({"left", "right", "up", "down"}) do held[k] = pat[k] end
    held.y = math.random() < 0.08 held.b = math.random() < 0.04
    step()
    if frameNo - patSince > 900 then
      patSince = frameNo patIdx = patIdx % #PATS + 1
      if frameNo - lastArea > 3600 then   -- dead end: reverse direction
        for _, p in ipairs(PATS) do p.left, p.right = p.right, p.left end lastArea = frameNo
      end
    end
    -- I -> G -> I mid-fight once every SWITCH_EVERY areas
    if areas - lastSwitchArea >= SWITCH_EVERY and frameNo - lastArea > 200 then
      lastSwitchArea = areas
      for k in pairs(held) do held[k] = nil end
      inMenu = true
      local a = setSkill(3) step(math.random(30, 300)) local b = setSkill(4)
      inMenu = false switches = switches + 1
      log("SWITCH", switches, "I->G", a, "G->I", b, "skill", rd(0x64C))
    end
    if frameNo % 6000 == 0 then log("progress", frameNo - f0, "areas", areas, "switches", switches, "VC checks", VC.checks, "row", VC.rowHits, "chr", VC.chrHits, "inv persist", INV.persist) end
  end
  log("SUMMARY areas", areas, "switches", switches, "VC checks", VC.checks, "row hits", VC.rowHits, "chr hits", VC.chrHits, "inv persistent", INV.persist)
end)
