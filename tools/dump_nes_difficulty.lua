-- Input-only NES skill-level dump. No writes to enemy fight stats.
local out = assert(os.getenv("RCR_CAPTURE_DIR"), "RCR_CAPTURE_DIR missing")
local log = assert(io.open(out .. "/dump.jsonl", "w"))

local function file(name, bytes)
    local f = assert(io.open(out .. "/" .. name, "wb"))
    f:write(bytes)
    f:close()
end

local function hold(frames, buttons)
    for _ = 1, frames do
        joypad.set(1, buttons)
        joypad.set(2, {up=false, down=false, left=false, right=false, A=false, B=false, start=false, select=false})
        emu.frameadvance()
    end
end

local function idle(frames)
    hold(frames, {up=false, down=false, left=false, right=false, A=false, B=false, start=false, select=false})
end

local function tap(button, on, off)
    local buttons = {up=false, down=false, left=false, right=false, A=false, B=false, start=false, select=false}
    buttons[button] = true
    hold(on, buttons)
    idle(off)
end

local function slot(i)
    return {
        type = memory.readbyte(0x04F5 + i),
        class = memory.readbyte(0x04F9 + i),
        punch = memory.readbyte(0x049F + i),
        kick = memory.readbyte(0x04A3 + i),
        weapon = memory.readbyte(0x04A7 + i),
        throw = memory.readbyte(0x04AB + i),
        agility = memory.readbyte(0x04AF + i),
        defense = memory.readbyte(0x04B3 + i),
        strength = memory.readbyte(0x04B7 + i),
        will = memory.readbyte(0x04BB + i),
        stamina = memory.readbyte(0x04BF + i),
        max_power = memory.readbyte(0x04C3 + i)
    }
end

local function snapshot(name)
    local ram = memory.readbyterange(0, 0x800)
    file(name .. ".ram", ram)
    file(name .. ".gd", gui.gdscreenshot(true))
    local s0, s1, s2, s3 = slot(0), slot(1), slot(2), slot(3)
    log:write(string.format(
        '{"name":"%s","frame":%d,"room":%d,"skill":%d,"speed":%d,"pause":%d,"alive":%d,"slots":['
        .. '{"i":0,"type":%d,"class":%d,"punch":%d,"will":%d,"stamina":%d},'
        .. '{"i":1,"type":%d,"class":%d,"punch":%d,"will":%d,"stamina":%d},'
        .. '{"i":2,"type":%d,"class":%d,"punch":%d,"will":%d,"stamina":%d},'
        .. '{"i":3,"type":%d,"class":%d,"punch":%d,"will":%d,"stamina":%d}]}\n',
        name, emu.framecount(), memory.readbyte(0x42), memory.readbyte(0x64C),
        memory.readbyte(0x670), memory.readbyte(0x3F), memory.readbyte(0x475),
        s0.type, s0.class, s0.punch, s0.will, s0.stamina,
        s1.type, s1.class, s1.punch, s1.will, s1.stamina,
        s2.type, s2.class, s2.punch, s2.will, s2.stamina,
        s3.type, s3.class, s3.punch, s3.will, s3.stamina))
    log:flush()
end

local function blank()
    return {up=false, down=false, left=false, right=false, A=false, B=false, start=false, select=false}
end

local function wait_until(frames, pred)
    for _ = 1, frames do
        if pred() then
            return true
        end
        idle(1)
    end
    return false
end

local function boot_to_street(walk_until)
    emu.poweron()
    for n = 1, walk_until do
        local buttons = blank()
        if n == 360 or n == 720 then
            buttons.start = true
        end
        if n >= 1000 then
            buttons.right = true
        end
        joypad.set(1, buttons)
        joypad.set(2, blank())
        emu.frameadvance()
    end
end

local function set_advanced()
    idle(60)
    tap("start", 12, 120)
    snapshot("paused")
    tap("right", 12, 90)
    tap("right", 12, 90)
    snapshot("cursor-level")
    tap("A", 12, 180)
    snapshot("level-open")
    tap("right", 12, 90)
    snapshot("level-advanced")
    tap("B", 12, 90)
    tap("start", 12, 120)
    snapshot("unpaused")
end

emu.speedmode("maximum")
boot_to_street(1600)
snapshot("novice-street")
memory.writebyte(0x42, 0x22)
idle(240)
snapshot("simon-novice-warp")

emu.poweron()
boot_to_street(1600)
snapshot("advanced-pre-menu")
set_advanced()
memory.writebyte(0x42, 0x22)
idle(240)
snapshot("simon-advanced-warp")

file("complete.json", string.format(
    '{"frames":%d,"skill":%d,"room":%d}\n',
    emu.framecount(), memory.readbyte(0x64C), memory.readbyte(0x42)))
log:close()
emu.exit()
