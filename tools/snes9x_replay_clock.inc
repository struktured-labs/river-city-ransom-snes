// Host-only observer, explicitly armed AFTER state restore. Never reads MMIO
// through emulated accessors and never changes guest CPU/memory/timing state.
static FILE *rcr_replay_file = NULL;
static long long rcr_replay_lines = 0;
static unsigned rcr_replay_frame = 0, rcr_replay_first = 0, rcr_replay_last = 0;
static bool rcr_replay_active = false;

static void rcrReplayRecord(char kind)
{
    if (!rcr_replay_file || rcr_replay_frame < rcr_replay_first ||
        rcr_replay_frame > rcr_replay_last) return;
    const unsigned op = CPU.PCBase ? CPU.PCBase[Registers.PCw] : 256;
    fprintf(rcr_replay_file,
        "%c,%u,%d,%d,%lld,%06x,%02x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%d\n",
        kind, rcr_replay_frame, CPU.V_Counter, CPU.Cycles,
        rcr_replay_lines + CPU.Cycles, Registers.PBPC, op,
        Registers.A.W, Registers.X.W, Registers.Y.W, Registers.S.W,
        Registers.P.W, Registers.DB, Registers.D.W,
        Memory.FillRAM[0x4200], Memory.FillRAM[0x4210], unsigned(CPU.NMIPending),
        Memory.RAM[0x1c0a], Memory.RAM[0x1c83], Memory.RAM[0x1ce0],
        Memory.RAM[0x1ce1], Memory.RAM[0x1b80], Memory.RAM[0x1ca0],
        Memory.RAM[0x107], Memory.RAM[0x100], Memory.RAM[0xf6],
        Memory.RAM[0x1c04] | Memory.RAM[0x1c05] << 8, Timings.H_Max);
}

extern "C" bool retro_rcr_replay_begin(const char *path, unsigned first, unsigned last)
{
    if (rcr_replay_active || !path || first == 0 || last < first) return false;
    rcr_replay_file = fopen(path, "wx");
    if (!rcr_replay_file) return false;
    rcr_replay_active = true;
    rcr_replay_lines = -static_cast<long long>(CPU.Cycles);
    rcr_replay_frame = 0;
    rcr_replay_first = first;
    rcr_replay_last = last;
    return true;
}

extern "C" bool retro_rcr_replay_frame_begin(unsigned frame)
{
    if (!rcr_replay_active || frame == 0 ||
        (rcr_replay_frame && frame != rcr_replay_frame+1)) return false;
    rcr_replay_frame = frame;
    rcrReplayRecord('B');
    return true;
}

extern "C" void retro_rcr_replay_frame_end(void)
{
    rcrReplayRecord('E');
}

extern "C" bool retro_rcr_replay_end(void)
{
    if (!rcr_replay_active) return false;
    const bool okay = !ferror(rcr_replay_file);
    const int closed = fclose(rcr_replay_file);
    rcr_replay_file = NULL;
    rcr_replay_active = false;
    return okay && closed == 0;
}

static void rcrReplayInstruction(void)
{
    rcrReplayRecord('I');
}

static void rcrReplayLine(void)
{
    if (!rcr_replay_active) return;
    // The old H_Max is precisely what the emulator subtracts from CPU.Cycles.
    // Keeping that same amount preserves elapsed clocks across short lines,
    // frame wrap, DMA, and any in-instruction event processing.
    rcrReplayRecord('H');
    rcr_replay_lines += Timings.H_Max;
}
