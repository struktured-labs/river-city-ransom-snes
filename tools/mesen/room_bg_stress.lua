-- Issue #8 stress: power-on, then CYCLES x (title -> settings, pick a skill
-- (Intermediate/Gamer/Intermediate/Novice...), street play with walking,
-- running, attacks, occasional pause open/close, then soft reset).
-- Row invariant (tools/mesen/row_invariant.lua) is checked every frame;
-- a clean row whose VRAM differs from the shadow for INV_PERSIST frames fails.
dofile(os.getenv("RCR_LIB")) dofile(os.getenv("INV_LIB")) dofile(os.getenv("VT_LIB"))
emu.addEventCallback(function() invariantCheck() end, emu.eventType.startFrame)
CYCLES = tonumber(os.getenv("CYCLES") or "4")
PLAY = tonumber(os.getenv("PLAY") or "6000")
PAUSE = os.getenv("PAUSE") ~= "0"
math.randomseed(tonumber(os.getenv("SEED") or "7"))
function tap(b) held[b]=true step(8) held[b]=nil step(20) end
function play(n)
  local dir = "right"
  for f = 1, n do
    emu.write(0x4BF, 0x7F, W)
    if f % 900 == 0 and math.random() < 0.3 then dir = (dir == "right") and "left" or "right" end
    local ph = f % 90
    held.right = dir == "right" and not (ph == 2 or ph == 3) held.left = dir == "left" and not (ph == 2 or ph == 3)
    held.up = math.random() < 0.04 held.down = math.random() < 0.04
    held.y = math.random() < 0.08 held.b = math.random() < 0.05
    if PAUSE and f % 1500 == 750 and onStreet() then
      for k in pairs(held) do held[k] = nil end
      local r = math.random()
      press("start", 4, 40)
      if r < 0.6 then
        -- pause -> LEVEL -> change skill 1-3 steps (cycles I/A/G/N) -> back
        tap("right") tap("right") tap("a") step(40)
        for i = 1, math.random(1, 3) do tap("right") end
        log("mode switch via LEVEL -> skill", rd(0x64C))
        tap("start") step(40)
      elseif r < 0.8 then
        tap("a") step(40) tap("start") step(40)   -- belongings
      end
      press("start", 4, 40)
    end
    step()
  end
  for k in pairs(held) do held[k] = nil end
end
run(function()
  local skills = {4, 3, 4, 1, 2, 3}
  for cycle = 1, CYCLES do
    INV_ACTIVE = false
    if not bootToSettings() then log("noboot") return end
    local want = skills[(cycle - 1) % #skills + 1]
    for n = 1, 8 do if rd(0x64C) == want then break end press("right", 6, 20) end
    if not settingsToStreet() then log("nostreet") return end
    invReset() INV_ACTIVE = true
    log("cycle", cycle, "skill", rd(0x64C))
    play(PLAY)
    log("cycle", cycle, "done; persistent so far", INV.persist, "transient", INV.viol)
    INV_ACTIVE = false
    emu.reset()
  end
  log("SUMMARY frames", INV.frames, "persistent", INV.persist, "transient", INV.viol, "active-display vram writes", VT.bad)
end)
