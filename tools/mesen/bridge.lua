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
run(function()
  if not bootToSettings() then return end
  for i=1,8 do if rd(0x64C)==4 then break end press("right", 6, 20) end
  if not settingsToStreet() then return end
  local stuck, last = 0, nil
  for sec=1,90 do
    for f=1,60 do
      if rd(0x4BF) < 0x20 then emu.write(0x4BF, 0x7F, W) end
      held.right = (sec % 12) < 7 held.left = (sec % 12) >= 10
      local ph = (frameNo // 20) % 6
      held.y = ph == 1 held.b = ph == 3
      step()
    end
    local s = screenSig()
    if s == last then stuck = stuck + 1 end
    last = s
    if sec % 30 == 0 then shot(string.format("street-%02d", sec)) end
  end
  log("counts bridge", n.bridge, "return", n.ret, "game", n.game, "skip", n.skip, "frames", frameNo, "stuck", stuck)
  check("NMIs enter the bridge", n.bridge > frameNo * 0.9, n.bridge .. "/" .. frameNo)
  check("every bridge entry returns and reaches the game NMI", n.ret == n.bridge and n.game == n.bridge,
        n.ret .. " " .. n.game .. " " .. n.bridge)
  check("skip path unused without a savestate", n.skip == 0, "skip=" .. n.skip)
  check("screen keeps changing", stuck < 10, "stuck=" .. stuck)
end)
