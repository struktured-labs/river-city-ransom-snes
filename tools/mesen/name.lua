dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
for _,a0 in ipairs({0x713A, 0x7140}) do for b=0xC1,0xC8 do local a=b*65536+a0
  emu.addMemoryCallback(function() log(string.format("exec %04x", a), state(), "name", hex(0x122AC,8)) end, emu.callbackType.exec, a, a, emu.cpuType.snes, emu.memType.snesMemory) end
end
run(function()
  if not bootToSettings() then return end
  while rd(0x64C) ~= 3 do press("right", 6, 20) end
  step(20)
  press("start", 12, 18)
  for n=1,60 do if onStreet() then break end press("a", 8, 12) local h=findNames() if #h>0 then log("names", table.concat(h," "), state()) end end
  step(30)
  local h=findNames() log("street names:", #h, table.concat(h," "))
  shot("street")
  held.right=true step(600) held.right=nil
  h=findNames() log("street later names:", #h, table.concat(h," "))
end)
