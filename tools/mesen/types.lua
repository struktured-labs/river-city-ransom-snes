dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
function slots()
  local t={}
  for s=0,11 do
    local x = (rd(0x388+s) - rd(0xDC)) & 0xFF
    local hi = (rd(0x390+s) - rd(0xDD) - ((rd(0x388+s) < rd(0xDC)) and 1 or 0)) & 0xFF
    t[#t+1]=string.format("%d:t%02x/300=%02x/x%s%3d/y%3d", s, rd(0x4F5+s), rd(0x300+s), hi==0 and "" or "*", x, rd(0x398+s))
  end
  return table.concat(t," ")
end
run(function()
  if not bootToSettings() then return end
  while rd(0x64C) ~= 1 do press("right", 6, 20) end
  if not settingsToStreet() then return end
  for sec=1,90 do
    for f=1,60 do
      emu.write(0x4BF, 0x3F, W)
      held.right = (sec % 12) < 7 held.left = (sec % 12) >= 10
      local ph = (frameNo // 20) % 6
      held.y = ph == 1 held.b = ph == 3
      step()
    end
    log("sec", sec, "room", string.format("%02x", rd(0x42)), "cc", rd(0xCC), slots())
    if sec % 3 == 0 then shot(string.format("t%02d", sec)) end
  end
end)
