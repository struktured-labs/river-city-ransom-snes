-- Stale visible tiles in the scrolling street band (issue #26). At the start
-- of each rendered frame, every visible BG1 tile of NES rows 4-23 is rebuilt
-- from the game's NES shadow ($7F2000/$7F2400 + attributes, vertical
-- mirroring) and compared with SNES VRAM (64x32 map at $2000, row r at
-- $2000 + r*32). Mismatches are logged with their screen x, split into tile
-- vs palette-only. env RCR_SECS, RCR_RUN (1 = hold B to run).
dofile(os.getenv("RCR_LIB") or "tools/mesen/lib.lua")
SECS = tonumber(os.getenv("RCR_SECS") or "90")
RUN = os.getenv("RCR_RUN") == "1"
CONTROL = os.getenv("RCR_CONTROL") == "1"
VRAM = emu.memType.snesVideoRam
function sh(a) return emu.read(0x12000 + a, W) end          -- $7F2000 + a
function vw(word) return emu.read(word*2, V) + 256*emu.read(word*2+1, V) end
stats = {nonzero=0, frames=0, bad=0, tileBad=0, palBad=0, byEdge={}}
function audit()
  if (rd(0x100) & 0xC0) ~= 0xC0 or rd(0x1CA0) ~= 0 or (rd(0x1C20) & 2) ~= 0 then return end
  local cam = rd(0x1C94) + 256*(rd(0x1C95) & 1)
  local hi = (rd(0x1C20) & 0x10) << 4
  local c0 = cam // 8
  local miss, tiles, pals, xs = 0, 0, 0, {}
  for y=4,23 do
    for k=0,32 do
      local col = (c0 + k) % 64
      local nt, c = col // 32, col % 32
      local base = nt * 0x400
      local tile = sh(base + y*32 + c)
      local attr = sh(base + 0x3C0 + (y//4)*8 + c//4)
      local pal = (attr >> ((y & 2)*2 + (c & 2))) & 3
      local want = tile | hi | (pal << 10)
      local got = vw(0x2000 + (nt*32 + y)*32 + c) & 0x1FFF
      if want ~= 0 then stats.nonzero = stats.nonzero + 1 end
      if got ~= want then
        miss = miss + 1
        if (got & 0x1FF) ~= (want & 0x1FF) then tiles = tiles + 1 else pals = pals + 1 end
        local x = (col*8 - cam) % 512
        xs[#xs+1] = x
      end
    end
  end
  stats.frames = stats.frames + 1
  if miss > 0 then
    stats.bad = stats.bad + 1 stats.tileBad = stats.tileBad + tiles stats.palBad = stats.palBad + pals
    table.sort(xs)
    local e = xs[#xs] >= 232 and "right" or (xs[1] < 24 and "left" or "mid")
    stats.byEdge[e] = (stats.byEdge[e] or 0) + 1
    if stats.bad <= 25 then
      log("stale", "room", string.format("%02X", rd(0x42)), "cam", cam, "tiles", tiles, "pal", pals, "x", xs[1] .. ".." .. xs[#xs], e)
    end
  end
end
emu.addEventCallback(function() if on then audit() end end, emu.eventType.startFrame)
on = false
rooms = {}
run(function()
  if not bootToSettings() then return end
  for n=1,8 do if rd(0x64C)==4 then break end press("right", 6, 20) end
  if not settingsToStreet() then return end
  on = true
  for sec=1,SECS do
    for f=1,60 do
      emu.write(0x4BF, 0x7F, W)
      rooms[rd(0x42)] = true
      local tf = sec*60 + f
      held.right = (tf % 400) < 330 held.up = (tf % 900) > 860 held.y = (tf % 30) == 3
      if RUN then
        -- RCR runs on a double tap of the direction
        local ph = f % 60
        held.right = held.right and not (ph == 2 or ph == 3)
      end
      step()
      if CONTROL and sec >= 20 and not controlled and (rd(0x100) & 0xC0) == 0xC0 and rd(0x1CA0) == 0 and (rd(0x1C20) & 2) == 0 then
        controlled = true
        -- negative control: corrupt one visible street tile in VRAM
        local cam = rd(0x1C94) + 256*(rd(0x1C95) & 1)
        local col = (cam // 8 + 10) % 64
        local w = 0x2000 + ((col // 32)*32 + 12)*32 + col % 32
        local before = emu.read(w*2, V)
        emu.write(w*2, before ~ 0x55, V)
        local b0 = stats.bad
        log("gate 100", string.format("%02X", rd(0x100)), "1CA0", rd(0x1CA0), "1C20", string.format("%02X", rd(0x1C20)), "cam", cam)
        audit()
        log("control: corrupted VRAM word", string.format("%04X", w), "byte", before, "->", emu.read(w*2, V),
            "detected immediately", stats.bad > b0)
      end
    end
  end
  local rl = {} for k in pairs(rooms) do rl[#rl+1] = string.format("%02X", k) end table.sort(rl)
  log("rooms visited", table.concat(rl, " "))
  local e = {} for k,v in pairs(stats.byEdge) do e[#e+1] = k .. "=" .. v end
  log("compared nonzero tiles", stats.nonzero, "frames audited", stats.frames, "frames with stale visible tiles", stats.bad,
      "tile mismatches", stats.tileBad, "palette-only", stats.palBad, "by edge", table.concat(e, " "))
end)
