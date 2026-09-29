-- What does RCR write to the nametable while scrolling (issue #26)? Logs,
-- per frame, every mark_ppu_dirty call (runtime $28A4 in banks C1-C8): the
-- NES PPU address and whether PPUCTRL increment-32 ($1C20 bit 2) was set,
-- plus dirty_mirrored_row calls that came from other paths.
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
SECS = tonumber(os.getenv("RCR_SECS") or "40")
SMEM = emu.memType.snesMemory
on, marks, rows, inMark = false, {}, 0, false
for b=0xC1,0xC8 do
  local base = b*65536
  if emu.read(base+0x28A4, SMEM) == 0xAD and emu.read(base+0x28A5, SMEM) == 0x27 then
    emu.addMemoryCallback(function()
      if not on then return end
      marks[#marks+1] = string.format("%04X%s", rd(0x1C27)*256 + rd(0x1C26), (rd(0x1C20) & 4) ~= 0 and "v" or "h")
    end, emu.callbackType.exec, base+0x28A4, base+0x28A4, emu.cpuType.snes, SMEM)
    emu.addMemoryCallback(function() if on then rows = rows + 1 end end,
      emu.callbackType.exec, base+0x28FC, base+0x28FC, emu.cpuType.snes, SMEM)
  end
end
run(function()
  if not bootToSettings() then return end
  for n=1,8 do if rd(0x64C)==4 then break end press("right", 6, 20) end
  if not settingsToStreet() then return end
  on = true
  local shown = 0
  for f=1,SECS*60 do
    if rd(0x4BF) < 0x20 then emu.write(0x4BF, 0x7F, W) end
    held.right = true held.b = (f % 30) < 15 and f > 600   -- walk, then run (double-tap is not needed: B held while walking)
    local cam0 = rd(0x1C94) + 256*rd(0x1C95)
    marks, rows = {}, 0
    step()
    if #marks > 0 or rows > 0 then
      shown = shown + 1
      if shown <= 60 then
        log("cam", cam0, "fine", string.format("%02X", rd(0x1C28)), "marks", #marks, "rowcalls", rows, table.concat(marks, " "))
      end
    end
  end
  log("frames with writes", shown)
end)
