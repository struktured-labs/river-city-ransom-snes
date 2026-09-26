dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
function live(tag) local s,nz=screenSig() log("live", tag, "sig", s, "nonblack", nz, state()) return s,nz end
run(function()
  for i=1,8 do step(60) live("boot"..i) end
  if not bootToSettings() then check("settings", false) shot("nosettings") return end
  shot("settings")
  -- Gamer: three rights
  for i=1,3 do press("right", 6, 20) end
  step(20) shot("settings-gamer") log("sk", rd(0x64C))
  press("start", 12, 18)
  for i=1,10 do step(30) live("afterstart"..i) end
  shot("afterstart")
  for n=1,60 do if onStreet() then break end press("a", 8, 12) end
  log("street?", onStreet(), state())
  check("street", onStreet())
  shot("street0")
  held.right=true
  local last=nil local same=0
  for i=1,20 do step(30) local s,nz=live("walk"..i) if s==last then same=same+1 end last=s end
  held.right=nil
  shot("street600")
  check("alive", same<5, "same="..same)
end)
