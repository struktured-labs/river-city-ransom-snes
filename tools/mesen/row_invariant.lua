-- Issue #8: invariant "row state $1D00+x == 0 (clean) => VRAM row x equals the
-- conversion of the game's NES nametable shadow" for all 128 rows (rows 30/31
-- of each table excluded). Checked at every frame start while the NMI video
-- pipeline runs ($1C79 != 0). A violation on a clean row can only be repaired
-- by a CHANGED shadow byte (identical $2007 writes are skipped), which is what
-- the pause-menu redraw does. Library: included by scenario scripts.
INV = {frames=0, viol=0, firstLog=0, rowsSeen={}, persist=0, plog=0}
PERSIST = tonumber(os.getenv("INV_PERSIST") or "60")
function invReset() INV.rowsSeen = {} end
function sh(a) return emu.read(0x12000 + a, W) end
function shadowBase(x)
  local horiz = (rd(0x1C18) & 1) == 1
  local a = horiz and (((x & 0x40) ~= 0) and 0x400 or 0) or (((x & 0x20) ~= 0) and 0x400 or 0)
  return a
end
function rowDiff(x)
  local y = x & 31
  local base = shadowBase(x)
  local hi = (rd(0x1C78) & 0x10) << 4
  local n, first = 0, nil
  for c = 0, 31 do
    local tile = sh(base + y*32 + c)
    local attr = sh(base + 0x3C0 + (y//4)*8 + c//4)
    local pal = (attr >> ((y & 2)*2 + (c & 2))) & 3
    local want = tile | hi | (pal << 10)
    local got = vw(0x2000 + x*32 + c) & 0x1FFF
    if got ~= want then n = n + 1 if not first then first = string.format("c%d want %04x got %04x", c, want, got) end end
  end
  return n, first
end
INV_ACTIVE = true
function invariantCheck(tag)
  if not INV_ACTIVE or rd(0x1C79) == 0 then return 0 end
  -- pattern half change pending: producer will dirty every row itself
  if (rd(0x1C20) & 0x10) ~= (rd(0x1C78) & 0x10) then return 0 end
  INV.frames = INV.frames + 1
  local bad = 0
  for x = 0, 127 do
    if (x & 31) < 30 and rd(0x1D00 + x) == 0 then
      local n, first = rowDiff(x)
      if n > 0 then
        bad = bad + 1
        if not INV.rowsSeen[x] then
          INV.rowsSeen[x] = frameNo
          INV.viol = INV.viol + 1
          INV.first = INV.first or {} INV.first[x] = string.format("row %d tiles %d %s 1CA0 %d %s %s", x, n, first, rd(0x1CA0), tag or "", state())
        elseif frameNo - INV.rowsSeen[x] == PERSIST then
          INV.persist = INV.persist + 1
          if INV.plog < 60 then INV.plog = INV.plog + 1
            log("PERSISTENT", PERSIST, "frames; began f" .. INV.rowsSeen[x], INV.first[x], "now tiles", n, state())
            if INV.plog <= 8 then shot(string.format("persist%02d", INV.plog)) end end
        end
      elseif INV.rowsSeen[x] then
        if frameNo - INV.rowsSeen[x] > PERSIST then log("repaired row", x, "after", frameNo - INV.rowsSeen[x], "frames") end
        INV.rowsSeen[x] = nil
      end
    end
  end
  return bad
end
