-- Read-only reference capture in FCEUX. Run through tools/capture_nes.py.
local out = assert(os.getenv("RCR_CAPTURE_DIR"), "RCR_CAPTURE_DIR missing")
local total = tonumber(os.getenv("RCR_CAPTURE_FRAMES") or "1800")
local profile = os.getenv("RCR_CAPTURE_PROFILE") or "title"
local replay = {}
if profile == "replay" then
    for line in io.lines(assert(os.getenv("RCR_REPLAY_INPUT"))) do
        replay[#replay+1] = assert(tonumber(line))
    end
end
local writes = assert(io.open(out .. "/hardware.jsonl", "w"))
local code = assert(io.open(out .. "/executed.jsonl", "w"))
local ram_code = assert(io.open(out .. "/executed-ram.jsonl", "w"))
local decompression = assert(io.open(out .. "/decompression.jsonl", "w"))
local ram_seen = {}
local seen = {}
local bank_select = 0
local bank_regs = {[6]=0,[7]=1}
local frame = 0
local lastpc = 0
local ppu_regs = {[0]=0,[1]=0,[5]=0,[6]=0}
local oam = string.rep(string.char(255), 256)
local oam_address = 0

local function file(name, bytes)
    local f = assert(io.open(out .. "/" .. name, "wb"))
    f:write(bytes)
    f:close()
end

local function physical(pc)
    local slot = math.floor((pc - 0x8000) / 0x2000)
    local mode = math.floor(bank_select / 64) % 2
    if slot == 3 then return 15 end
    if slot == 1 then return (bank_regs[7] or 1) % 16 end
    if slot == (mode == 0 and 2 or 0) then return 14 end
    return (bank_regs[6] or 0) % 16
end

memory.registerexec(0x8000, 0x8000, function(pc)
    local previouspc = lastpc
    lastpc = pc
    local bank = physical(pc)
    local offset = bank * 8192 + pc % 8192
    if offset == 0x1C8DB or offset == 0x1C90C then
        -- Immediate predecessor is the actual JSR site, including nested
        -- decompression. Do not infer the caller from a last-command latch.
        decompression:write(string.format('{"frame":%d,"kind":"%s","caller":%d,"source_base":%d,"source_index":%d,"destination":%d,"value":%d,"ppu_ctrl":%d}\n',
            frame, offset == 0x1C8DB and "read" or "write", previouspc,
            memory.readbyte(0x2A) + 256 * memory.readbyte(0x2B),
            memory.readbyte(0x1A), memory.readbyte(0x2C) + 256 * memory.readbyte(0x2D),
            memory.readbyte(0x1B), ppu_regs[0]))
    end
    if not seen[offset] then
        local opcode = memory.readbyte(pc)
        -- A mapping bug must not silently associate code with the wrong PRG bank.
        assert(opcode == rom.readbyte(16 + offset), "PRG mapping mismatch")
        seen[offset] = true
        code:write(string.format('{"frame":%d,"bank":%d,"pc":%d,"offset":%d,"opcode":%d}\n',
            frame, bank, pc, offset, opcode))
    end
end)

memory.registerexec(0, 0x8000, function(pc)
    lastpc = pc
    local bytes = {}
    for i=0,3 do bytes[#bytes+1] = memory.readbyte((pc+i)%65536) end
    local key = tostring(pc) .. ":" .. table.concat(bytes, ",")
    if not ram_seen[key] then
        ram_seen[key] = true
        ram_code:write(string.format('{"frame":%d,"pc":%d,"bytes":[%s]}\n',
            frame, pc, table.concat(bytes, ",")))
    end
end)

local function hardware(address, size, value)
    writes:write(string.format('{"frame":%d,"cycle":%d,"pc":%d,"address":%d,"value":%d}\n',
        frame, debugger.getcyclescount(), lastpc, address, value))
    if address == 0x8000 then bank_select = value end
    if address == 0x8001 then bank_regs[bank_select % 8] = value end
    if address == 0x2000 then ppu_regs[0] = value end
    if address == 0x2001 then ppu_regs[1] = value end
    if address == 0x2003 then oam_address = value end
    if address == 0x2004 then
        oam = oam:sub(1, oam_address) .. string.char(value) .. oam:sub(oam_address + 2)
        oam_address = (oam_address + 1) % 256
    end
    if address == 0x4014 then oam = memory.readbyterange(value * 256, 256) end
end

memory.registerwrite(0x2000, 8, hardware)
memory.registerwrite(0x4000, 0x18, hardware)
for _, address in ipairs({0x8000,0x8001,0xA000,0xA001,0xC000,0xC001,0xE000,0xE001}) do
    memory.registerwrite(address, hardware)
end

emu.speedmode("maximum")
emu.poweron()
for n=1,total do
    frame = n
    local buttons = {up=false,down=false,left=false,right=false,A=false,B=false,start=false,select=false}
    if profile == "replay" then
        local mask = replay[n] or 0
        for key, bit in pairs({B=0,select=2,start=3,up=4,down=5,left=6,right=7,A=8}) do
            buttons[key] = math.floor(mask / 2^bit) % 2 == 1
        end
    end
    if profile == "walk" or profile == "inventory" then
        if n == 360 or n == 720 then buttons.start = true end
        if profile == "walk" then
            if n >= 1000 then buttons.right = true end
            if n >= 1200 and n % 20 < 5 then buttons.A = true end
        else
            if n >= 1200 and n < 1212 then buttons.A = true end
            if n >= 1800 and n < 1812 then buttons.start = true end
            if n >= 2100 and n < 2112 then buttons.A = true end
            if n >= 2700 and n < 2712 then buttons.B = true end
        end
    end
    joypad.set(1, buttons)
    joypad.set(2, {up=false,down=false,left=false,right=false,A=false,B=false,start=false,select=false})
    emu.frameadvance()
    if n == 60 or n == 120 or n % 300 == 0 then
        local prefix = string.format("frame-%05d", n)
        file(prefix .. ".gd", gui.gdscreenshot(true))
        file(prefix .. ".ppu", ppu.readbyterange(0, 0x4000))
        file(prefix .. ".ram", memory.readbyterange(0, 0x800))
        file(prefix .. ".oam", oam)
        file(prefix .. ".json", string.format('{"frame":%d,"ppu_ctrl":%d,"ppu_mask":%d,"bank_select":%d}\n',
            n, ppu_regs[0], ppu_regs[1], bank_select))
        writes:flush()
        code:flush()
    end
end
memory.registerexec(0x8000, 0x8000, nil)
memory.registerexec(0, 0x8000, nil)
memory.registerwrite(0x2000, 8, nil)
memory.registerwrite(0x4000, 0x18, nil)
for _, address in ipairs({0x8000,0x8001,0xA000,0xA001,0xC000,0xC001,0xE000,0xE001}) do
    memory.registerwrite(address, nil)
end
writes:close()
code:close()
ram_code:close()
decompression:close()
file("complete.json", string.format('{"frames":%d,"profile":"%s"}\n', total, profile))
emu.exit()
