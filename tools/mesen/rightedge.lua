-- Issue #26 hunt: one-frame artifacts at the right edge while scrolling through
-- rooms 0-3 (school, alley street, mall, park). Two audits per frame:
--  A) VRAM vs NES shadow (as stale_columns.lua) for NES rows 4-27, every visible column.
--  B) screen transient: a background pixel (no sprite near it in any of the frames)
--     at x >= X0 that differs from the next two frames while those two agree, after
--     aligning each horizontal band by its best scroll shift. Exact pixels, no video noise.
-- env RCR_SKILL (4 Intermediate), RCR_SECS per room sweep, RCR_X0 (200), RCR_RUN (1)
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
SKILL = tonumber(os.getenv("RCR_SKILL") or "4")
SECS = tonumber(os.getenv("RCR_SECS") or "60")
X0 = tonumber(os.getenv("RCR_X0") or "200")
RUN = (os.getenv("RCR_RUN") or "1") == "1"
VR = emu.memType.snesVideoRam
function sh(a) return emu.read(0x12000 + a, W) end
A = {frames=0, bad=0, tile=0, pal=0, edge={}, rooms={}}
function vramAudit()
  if (rd(0x100) & 0xC0) ~= 0xC0 or rd(0x1CA0) ~= 0 or (rd(0x1C20) & 2) ~= 0 then return end
  local cam = rd(0x1C94) + 256*(rd(0x1C95) & 1)
  local hi = (rd(0x1C20) & 0x10) << 4
  local c0 = cam // 8
  local miss, tiles, pals, xs, ys = 0, 0, 0, {}, {}
  for y=4,27 do for k=0,32 do
    local col = (c0 + k) % 64
    local nt, c = col // 32, col % 32
    local base = nt * 0x400
    local tile = sh(base + y*32 + c)
    local attr = sh(base + 0x3C0 + (y//4)*8 + c//4)
    local pal = (attr >> ((y & 2)*2 + (c & 2))) & 3
    local want = tile | hi | (pal << 10)
    local got = vw(0x2000 + (nt*32 + y)*32 + c) & 0x1FFF
    if got ~= want then
      miss = miss + 1
      if (got & 0x1FF) ~= (want & 0x1FF) then tiles = tiles + 1 else pals = pals + 1 end
      xs[#xs+1] = (col*8 - cam) % 512 ys[#ys+1] = y
    end
  end end
  A.frames = A.frames + 1
  if miss > 0 then
    A.bad = A.bad + 1 A.tile = A.tile + tiles A.pal = A.pal + pals
    table.sort(xs)
    local e = xs[#xs] >= 232 and "right" or (xs[1] < 24 and "left" or "mid")
    A.edge[e] = (A.edge[e] or 0) + 1
    if A.bad <= 30 then log("VRAMSTALE room", string.format("%02X", rd(0x42)), "cam", cam, "tiles", tiles, "pal", pals, "x", xs[1] .. ".." .. xs[#xs], "rows", table.concat(ys, ",", 1, math.min(#ys, 8)), e) if A.bad <= 8 then shot(string.format("vram-%06d", frameNo)) end end
  end
end
-- B) screen transients
hist = {}   -- {buf=, mask=, ok=}
B = {frames=0, hits=0, pix=0, skipped=0}
function spriteMask()
  local m = {}
  local hiBase = 512
  for i=0,127 do
    local x = emu.read(i*4, OAMT) local y = emu.read(i*4+1, OAMT)
    local hb = emu.read(hiBase + (i >> 2), OAMT) >> ((i & 3)*2)
    if (hb & 1) ~= 0 then x = x - 256 end
    local size = ((hb & 2) ~= 0) and 16 or 8
    if y < 0xE0 and x + size + 2 >= X0 - 8 then
      for yy = y - 1, y + size + 2 do for xx = math.max(x - 2, X0 - 8), math.min(x + size + 2, 255) do m[yy*256 + xx] = true end end
    end
  end
  return m
end
function gate() return (rd(0x100) & 0xC0) == 0xC0 and rd(0x1CA0) == 0 and (rd(0x1C20) & 2) == 0 and rd(0x3F) == 0 end
BANDS = {{32, 193}, {194, 223}}
function bestShift(a, b, ma, mb, y0, y1)
  local best, bc, bn = 0, 1e9, 0
  for s=-8,8 do
    local cnt, n = 0, 0
    for y=y0,y1,2 do for x=X0,255 do
      local xb = x - s
      if xb >= X0 - 8 and xb <= 255 and not ma[y*256+x] and not mb[y*256+xb] then
        n = n + 1
        if a[y*256+x+1] ~= b[y*256+xb+1] then cnt = cnt + 1 end
      end
    end end
    if n > 200 and cnt / n < bc then bc, best, bn = cnt / n, s, n end
  end
  return best, bc
end
function screenAudit()
  local ok = gate()
  local buf = emu.getScreenBuffer()
  local m = spriteMask()
  hist[#hist+1] = {buf=buf, mask=m, ok=ok, f=frameNo, room=rd(0x42), cam=rd(0x1C94) + 256*(rd(0x1C95) & 1)}
  if #hist > 3 then table.remove(hist, 1) end
  if #hist < 3 then return end
  local f0, f1, f2 = hist[1], hist[2], hist[3]
  if not (f0.ok and f1.ok and f2.ok) or f0.room ~= f2.room then B.skipped = B.skipped + 1 return end
  B.frames = B.frames + 1
  local hits = {}
  for _, band in ipairs(BANDS) do
    local y0, y1 = band[1], band[2]
    local s1, c1 = bestShift(f0.buf, f1.buf, f0.mask, f1.mask, y0, y1)   -- f0 x  ~ f1 x - s1
    local s2, c2 = bestShift(f1.buf, f2.buf, f1.mask, f2.mask, y0, y1)
    if c1 < 0.25 and c2 < 0.25 then
      for y=y0,y1 do for x=X0,255 do
        local k = y*256 + x
        if not f0.mask[k] then
          local x1 = x - s1 local x2 = x1 - s2
          if x1 >= X0 - 8 and x1 <= 255 and x2 >= X0 - 8 and x2 <= 255 and not f1.mask[y*256+x1] and not f2.mask[y*256+x2] then
            local a, b, c = f0.buf[k+1], f1.buf[y*256+x1+1], f2.buf[y*256+x2+1]
            if a ~= b and b == c then hits[#hits+1] = {x=x, y=y} end
          end
        end
      end end
    end
  end
  if #hits >= 4 then
    B.hits = B.hits + 1 B.pix = B.pix + #hits
    local xmin, xmax, ymin, ymax = 999, -1, 999, -1
    for _,h in ipairs(hits) do xmin = math.min(xmin, h.x) xmax = math.max(xmax, h.x) ymin = math.min(ymin, h.y) ymax = math.max(ymax, h.y) end
    if B.hits <= 40 then
      log("TRANSIENT frame", f0.f, "room", string.format("%02X", f0.room), "cam", f0.cam, f1.cam, f2.cam, "pixels", #hits, "box", xmin .. "-" .. xmax, ymin .. "-" .. ymax)
      if B.hits <= 12 then dumpTriplet(string.format("tr-%06d", f0.f)) end
    end
  end
end
C = {frames=0, hits=0, maxred=0}
redHist = {}
function isRed(c) local r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255 return r >= 0xA0 and g < 0x70 and b < 0x70 end
function redAudit()
  local buf = emu.getScreenBuffer()
  local H_ = #buf // 256
  local cnt, xs = 0, {}
  for y=0,H_-1 do for x=236,255 do if isRed(buf[y*256+x+1]) then cnt = cnt + 1 xs[#xs+1] = x end end end
  redHist[#redHist+1] = {n=cnt, f=frameNo, ok=gate(), room=rd(0x42)}
  if #redHist > 3 then table.remove(redHist, 1) end
  C.frames = C.frames + 1
  if cnt > C.maxred then C.maxred = cnt end
  if #redHist < 3 then return end
  local a, b, c = redHist[1], redHist[2], redHist[3]
  if b.n >= 6 and a.n * 4 <= b.n and c.n * 4 <= b.n then
    C.hits = C.hits + 1
    if C.hits <= 40 then
      local oam = {}
      for i=0,127 do local x = emu.read(i*4, OAMT) local y = emu.read(i*4+1, OAMT) local hb = emu.read(512 + (i >> 2), OAMT) >> ((i & 3)*2)
        if (hb & 1) ~= 0 then x = x - 256 end
        if y < 0xE0 and x >= 200 then oam[#oam+1] = string.format("%d:%d,%d t%02x a%02x", i, x, y, emu.read(i*4+2, OAMT), emu.read(i*4+3, OAMT)) end end
      log("REDTRANSIENT frame", b.f, "room", string.format("%02X", b.room), "gate", tostring(b.ok), "red", a.n, b.n, c.n, "oam(now)", table.concat(oam, " "))
      if C.hits <= 12 and #hist == 3 then dumpTriplet(string.format("red-%06d", b.f)) end
    end
  end
end
function dumpTriplet(name)
  -- raw PPM of the three frames side by side
  local h = io.open(OUT .. "/" .. name .. ".ppm", "wb")
  local H_ = #hist[1].buf // 256
  h:write(string.format("P6\n%d %d\n255\n", 768, H_))
  local t = {}
  for y=0,H_-1 do for i=1,3 do local b = hist[i].buf for x=0,255 do local c = b[y*256+x+1]
    t[#t+1] = string.char((c >> 16) & 255, (c >> 8) & 255, c & 255) end end
    if #t > 4096 then h:write(table.concat(t)) t = {} end
  end
  h:write(table.concat(t)) h:close()
end
emu.addEventCallback(function() if on then vramAudit() end end, emu.eventType.startFrame)
on = false
function nav(room, target, tf)
  -- returns held table for this frame
  local x = rd(0x388) + 256*rd(0x390)
  local r = {}
  if room == 1 and target == "mall" then
    if x < 461 then r.right = true elseif x > 467 then r.left = true else r.up = true end
  else
    if target == "east" then r.right = true else r.left = true end
  end
  if RUN and (r.right or r.left) then local ph = tf % 90 if ph == 2 or ph == 3 then r.right = nil r.left = nil end end
  if tf % 30 == 3 then r.b = true end
  if room >= 2 and tf % 30 >= 3 and tf % 30 < 7 then r.a = true end
  return r
end
run(function()
  if not bootToSettings() then return end
  for n=1,8 do if rd(0x64C)==SKILL then break end press("right", 6, 20) end
  check("skill selected", rd(0x64C)==SKILL, "sk=" .. rd(0x64C))
  if not settingsToStreet() then return end
  on = true
  -- legs: {expected room, direction, seconds, stop}
  -- stop: "next" = room changed, "x<" / "x>" = position threshold in this room
  local plan = {{0,"east",60,"next"},{1,"mall",60,"next"},{2,"east",14,"time"},{2,"west",40,"x<"},
                {2,"east",14,"time"},{2,"west",40,"x<"},{2,"east",60,"next"},{3,"east",30,"x>"},{3,"west",40,"x<"},{3,"east",30,"x>"}}
  local tf = 0
  for _, p in ipairs(plan) do
    local room, target, secs, stop = p[1], p[2], p[3], p[4]
    local start = frameNo
    if rd(0x42) ~= room then log("leg skipped: not in room", room, "now", rd(0x42)) else
    for f=1,secs*60 do
      tf = tf + 1
      emu.write(0x4BF, 0x7F, W)
      A.rooms[rd(0x42)] = true
      local x = rd(0x388) + 256*rd(0x390)
      if stop == "next" and rd(0x42) ~= room then break end
      if stop == "x<" and x < 160 then break end
      if stop == "x>" and x > 650 then break end
      if rd(0x42) ~= room and stop ~= "next" then break end
      held = nav(rd(0x42), target, tf)
      step()
      screenAudit()
      redAudit()
    end
    end
    held = {}
    step(30)
    log("leg", room, target, "room now", string.format("%02X", rd(0x42)), "x", rd(0x388) + 256*rd(0x390), "frames", frameNo - start, state())
  end
  local rl = {} for k in pairs(A.rooms) do rl[#rl+1] = string.format("%02X", k) end table.sort(rl)
  local e = {} for k,v in pairs(A.edge) do e[#e+1] = k .. "=" .. v end
  log("rooms", table.concat(rl, " "))
  log("VRAM audit frames", A.frames, "stale frames", A.bad, "tile", A.tile, "pal", A.pal, "by edge", table.concat(e, " "))
  log("SCREEN audit frames", B.frames, "skipped", B.skipped, "transient frames", B.hits, "pixels", B.pix)
  log("RED audit frames", C.frames, "transient red frames", C.hits, "max red px in x>=236", C.maxred)
  check("no transient red at the right edge", C.hits == 0, "hits=" .. C.hits)
  check("visited rooms 0-3", A.rooms[0] and A.rooms[1] and A.rooms[2] and A.rooms[3], table.concat(rl, " "))
  check("no stale visible BG tiles", A.bad == 0, "stale=" .. A.bad)
  check("no right-edge screen transients", B.hits == 0, "hits=" .. B.hits)
end)
