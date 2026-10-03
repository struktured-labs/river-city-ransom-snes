-- SPC link health for the frame packet sender (4302 Memblers engine or the
-- 4303 Project Nested trial): every packet completes (no $EE timeout code in
-- $1C0B), the sender runs about once per game frame, and its cost in
-- scanlines is logged. RCR_SENDER_RTS = address of the sender's final RTS.
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
SMEM = emu.memType.snesMemory
ENTRY, RTS = 0xD2BC, tonumber(os.getenv("RCR_SENDER_RTS") or "0xD2F9")
calls, done, errs, startLine, startFrame = 0, 0, 0, 0, 0
cost, worst = {}, 0
for _,bank in ipairs({0x00, 0x80, 0xC0}) do
  emu.addMemoryCallback(function()
    calls = calls + 1
    local s = emu.getState() startLine = s["snes.ppu.scanline"] or s["ppu.scanline"] or 0 startFrame = frameNo
  end, emu.callbackType.exec, bank*65536+ENTRY, bank*65536+ENTRY, emu.cpuType.snes, SMEM)
  emu.addMemoryCallback(function()
    done = done + 1
    local s = emu.getState() local line = s["snes.ppu.scanline"] or s["ppu.scanline"] or 0
    local n = line - startLine
    if n < 0 then n = n + 262 end            -- the call spans one frame boundary at most
    cost[n] = (cost[n] or 0) + 1 if n > worst then worst = n end
  end, emu.callbackType.exec, bank*65536+RTS, bank*65536+RTS, emu.cpuType.snes, SMEM)
end
for _,a in ipairs({0x7E1C0B, 0x001C0B}) do
  emu.addMemoryCallback(function(addr, value) if value == 0xEE then errs = errs + 1 end end,
    emu.callbackType.write, a, a, emu.cpuType.snes, SMEM)
end
run(function()
  if not bootToSettings() then return end
  if not settingsToStreet() then return end
  local c0 = calls
  for sec=1,90 do
    for f=1,60 do
      if rd(0x4BF) < 0x20 then emu.write(0x4BF, 0x7F, W) end
      held.right = (sec % 12) < 7 held.left = (sec % 12) >= 10
      local ph = (frameNo // 20) % 6
      held.y = ph == 1 held.b = ph == 3
      step()
    end
  end
  local keys = {} for k in pairs(cost) do keys[#keys+1] = k end table.sort(keys)
  local hist = {} for _,k in ipairs(keys) do hist[#hist+1] = k .. ":" .. cost[k] end
  log("sender cost (scanlines:count)", table.concat(hist, " "))
  check("SPC link: no packet timeout ($EE in $1C0B)", errs == 0, "errors=" .. errs)
  check("SPC link: sender ran about once per frame on the street", calls - c0 >= 5000, "calls=" .. (calls - c0) .. " of 5400 frames")
  check("SPC link: every sender call returned", calls - done <= 1, "calls=" .. calls .. " returns=" .. done)
  log("worst sender cost", worst, "scanlines")
end)
