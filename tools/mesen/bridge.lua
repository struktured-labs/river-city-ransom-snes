-- Savestate bridge, no-save path (issue #30): every NMI enters bridge_nmi,
-- returns through native_interrupt's RTI, and reaches the original handler
-- at $80FB in VBlank; the skip path (post-save) never runs; the game lives.
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
SMEM = emu.memType.snesMemory
BRIDGE, RET, SKIP, GAME = 0xF820, 0xF82B, 0xF835, 0x80FB
n = {bridge=0, ret=0, skip=0, game=0}
for _,bank in ipairs({0x00, 0x80}) do
  local function count(k, a)
    emu.addMemoryCallback(function() n[k] = n[k] + 1 end, emu.callbackType.exec,
      bank*65536+a, bank*65536+a, emu.cpuType.snes, SMEM)
  end
  count("bridge", BRIDGE) count("ret", RET) count("skip", SKIP) count("game", GAME)
end
-- Liveness without trusting a changing picture: the game's main loop polls the
-- joypad (native_joypad_poll at $348C) every game tick. A static screen (Alex
-- standing against a wall) is fine; a game that stops polling, or a screen
-- that stays black, is not.
polls = 0
for b=0xC1,0xC8 do
  emu.addMemoryCallback(function() polls = polls + 1 end, emu.callbackType.exec, b*65536+0x348C, b*65536+0x348C, emu.cpuType.snes, SMEM)
end
run(function()
  if not bootToSettings() then return end
  for i=1,8 do if rd(0x64C)==4 then break end press("right", 6, 20) end
  if not settingsToStreet() then return end
  local deadSecs, blackRun, blackMax, lastPolls = 0, 0, 0, polls
  for sec=1,90 do
    for f=1,60 do
      if rd(0x4BF) < 0x20 then emu.write(0x4BF, 0x7F, W) end
      held.right = (sec % 12) < 7 held.left = (sec % 12) >= 10
      local ph = (frameNo // 20) % 6
      held.y = ph == 1 held.b = ph == 3
      step()
    end
    local _, nz = screenSig()
    if polls == lastPolls then deadSecs = deadSecs + 1 end
    lastPolls = polls
    if nz < 20 then blackRun = blackRun + 1 else blackRun = 0 end
    blackMax = math.max(blackMax, blackRun)
    if sec % 30 == 0 then shot(string.format("street-%02d", sec)) end
  end
  log("counts bridge", n.bridge, "return", n.ret, "game", n.game, "skip", n.skip, "frames", frameNo, "polls", polls, "secondsWithoutPoll", deadSecs, "longestBlackSecs", blackMax)
  check("NMIs enter the bridge", n.bridge > frameNo * 0.9, n.bridge .. "/" .. frameNo)
  check("every bridge entry returns and reaches the game NMI", n.ret == n.bridge and n.game == n.bridge,
        n.ret .. " " .. n.game .. " " .. n.bridge)
  check("skip path unused without a savestate", n.skip == 0, "skip=" .. n.skip)
  check("game stays alive (joypad polled every second, never black for 5 s)", deadSecs == 0 and blackMax < 5,
        "secondsWithoutPoll=" .. deadSecs .. " longestBlackSecs=" .. blackMax)
end)
