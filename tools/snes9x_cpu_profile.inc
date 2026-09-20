// Include inside S9xMainLoop immediately before opcode dispatch.
// Host-only counts, not cycle measurements. Run beyond LAST to flush its frame.
static FILE *rcr_profile = getenv("RCR_CPU_PROFILE") ? fopen(getenv("RCR_CPU_PROFILE"), "w") : NULL;
static const unsigned rcr_first = getenv("RCR_PROFILE_FIRST") ? strtoul(getenv("RCR_PROFILE_FIRST"), NULL, 0) : 0;
static const unsigned rcr_last = getenv("RCR_PROFILE_LAST") ? strtoul(getenv("RCR_PROFILE_LAST"), NULL, 0) : 0;
static unsigned rcr_profile_frame = ~0u;
static unsigned rcr_counts[9][65536] = {};
// Optional original-game PPU command trace.  The three fixed PCs are RCR's
// high-address, low-address and ring-data stores; logging happens before the
// translated opcode, so both A and the adapter's current address are visible
// without adding an emulated read or cycle.
static FILE *rcr_ppu = getenv("RCR_PROFILE_PPU_TRACE") ? fopen(getenv("RCR_PROFILE_PPU_TRACE"), "w") : NULL;
if (rcr_ppu && Registers.PB >= 0xc1 && Registers.PB <= 0xc8 &&
    IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last &&
    (Registers.PCw == 0xc52a || Registers.PCw == 0xc535 || Registers.PCw == 0xc578)) {
    fprintf(rcr_ppu, "%u,%d,%d,%06x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
        IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, Registers.PBPC,
        Registers.A.B.l, Registers.X.W, Registers.Y.W, Memory.RAM[0x1c26],
        Memory.RAM[0x1c27], Memory.RAM[0x100], Memory.RAM[0x10b],
        Memory.RAM[0x1ca0], Memory.RAM[0x1c79], Memory.RAM[0x1c85],
        Memory.RAM[0x1c0a], Memory.FillRAM[0x4200], Memory.RAM[0x6b6],
        Memory.RAM[0x6b7], Memory.RAM[0x585], Memory.RAM[0x03e],
        Memory.RAM[0x004], Memory.RAM[0x006]);
    fflush(rcr_ppu);
}
// Optional exact producer-state trace for the original C487 graphics-command
// enqueue routine.  This mirrors the NES observer's columns and adds native
// transition state at the end.  It reads host memory only.
static FILE *rcr_queue = getenv("RCR_PROFILE_QUEUE_TRACE") ? fopen(getenv("RCR_PROFILE_QUEUE_TRACE"), "w") : NULL;
if (rcr_queue && Registers.PB >= 0xc1 && Registers.PB <= 0xc8 &&
    IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last &&
    (Registers.PCw == 0xc487 || Registers.PCw == 0xc497 ||
     Registers.PCw == 0xc4c0 || Registers.PCw == 0xc4ca ||
     Registers.PCw == 0xc4d3 || Registers.PCw == 0xc4e5 ||
     Registers.PCw == 0xc515)) {
    fprintf(rcr_queue,
        "%u,%d,%d,%06x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
        IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, Registers.PBPC,
        Registers.A.B.l, Registers.X.W, Registers.Y.W, Registers.S.W,
        Registers.P.W, Memory.RAM[0x6b6], Memory.RAM[0x6b7],
        Memory.RAM[0x585], Memory.RAM[0x03e], Memory.RAM[0x100],
        Memory.RAM[0x10b], Memory.RAM[0x004], Memory.RAM[0x006],
        Memory.RAM[0x01a], Memory.RAM[0x01b], Memory.RAM[0x01c],
        Memory.RAM[0x02a], Memory.RAM[0x02b], Memory.RAM[0x0dc],
        Memory.RAM[0x0dd], Memory.RAM[0x0f6], Memory.RAM[0x03d],
        Memory.RAM[0x1ca0]);
    fflush(rcr_queue);
}
// Original-game stores to the command-ring write pointer. Decode the pending
// absolute store before execution, so the writer PC and source register remain
// exact without adding an emulated memory access.
static FILE *rcr_queue_writes = getenv("RCR_PROFILE_QUEUE_WRITE_TRACE") ? fopen(getenv("RCR_PROFILE_QUEUE_WRITE_TRACE"), "w") : NULL;
if (rcr_queue_writes && CPU.PCBase && Registers.PB >= 0xc1 && Registers.PB <= 0xc8 &&
    IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last) {
    const unsigned pc = Registers.PCw;
    const uint8 opcode = CPU.PCBase[pc];
    if ((opcode == 0x8d || opcode == 0x8e || opcode == 0x8c) &&
        CPU.PCBase[pc + 1] == 0xb7 && CPU.PCBase[pc + 2] == 0x06) {
        const unsigned value = opcode == 0x8d ? Registers.A.B.l :
                               opcode == 0x8e ? Registers.X.B.l : Registers.Y.B.l;
        fprintf(rcr_queue_writes,
            "%u,%d,%d,%06x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles,
            Registers.PBPC, value, Registers.A.B.l, Registers.X.B.l,
            Registers.Y.B.l, Registers.S.W, Registers.P.W,
            Memory.RAM[0x6b6], Memory.RAM[0x6b7], Memory.RAM[0x585],
            Memory.RAM[0x03e], Memory.RAM[0x100], Memory.RAM[0x10b],
            Memory.RAM[0x1ca0]);
        fflush(rcr_queue_writes);
    }
}
// Exact writes selecting the two background-command streams.  Decode only
// direct absolute/indexed stores from the already mapped opcode bytes; this
// is host observation and executes before the emulated instruction.
static FILE *rcr_stream_writes = getenv("RCR_PROFILE_STREAM_WRITE_TRACE") ? fopen(getenv("RCR_PROFILE_STREAM_WRITE_TRACE"), "w") : NULL;
if (rcr_stream_writes && CPU.PCBase && Registers.PB >= 0xc1 && Registers.PB <= 0xc8 &&
    IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last) {
    const unsigned rcr_pc = Registers.PCw;
    const uint8 rcr_op = CPU.PCBase[rcr_pc];
    unsigned rcr_addr = 0x10000;
    unsigned rcr_value = 0;
    if (rcr_op == 0x8d || rcr_op == 0x8e || rcr_op == 0x8c ||
        rcr_op == 0x9d || rcr_op == 0x99) {
        rcr_addr = CPU.PCBase[rcr_pc + 1] | CPU.PCBase[rcr_pc + 2] << 8;
        if (rcr_op == 0x9d) rcr_addr = (rcr_addr + Registers.X.W) & 0xffff;
        if (rcr_op == 0x99) rcr_addr = (rcr_addr + Registers.Y.W) & 0xffff;
        rcr_value = rcr_op == 0x8e ? Registers.X.B.l :
                    rcr_op == 0x8c ? Registers.Y.B.l : Registers.A.B.l;
    }
    if (rcr_addr == 0x06ba || rcr_addr == 0x06bb) {
        fprintf(rcr_stream_writes,
            "%u,%d,%d,%06x,%04x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles,
            Registers.PBPC, rcr_addr, rcr_value, Registers.A.B.l,
            Registers.X.B.l, Registers.Y.B.l, Registers.S.W,
            Registers.P.W, Memory.RAM[0x100], Memory.RAM[0x10b],
            Memory.RAM[0x6ba], Memory.RAM[0x6bb], Memory.RAM[0xdc],
            Memory.RAM[0xdd], Memory.RAM[0xf6]);
        fflush(rcr_stream_writes);
    }
}
// Optional generic entry timing for exact linked PCs.  Each variable is a
// four-digit hexadecimal PC; the trace retains PB so replicated runtime and
// boot-bank entries remain distinguishable without touching emulated state.
static FILE *rcr_events = getenv("RCR_PROFILE_EVENT_TRACE") ? fopen(getenv("RCR_PROFILE_EVENT_TRACE"), "w") : NULL;
static unsigned rcr_event_pc[8] = {
    getenv("RCR_PROFILE_EVENT_PC0") ? strtoul(getenv("RCR_PROFILE_EVENT_PC0"), NULL, 16) : 0x10000,
    getenv("RCR_PROFILE_EVENT_PC1") ? strtoul(getenv("RCR_PROFILE_EVENT_PC1"), NULL, 16) : 0x10000,
    getenv("RCR_PROFILE_EVENT_PC2") ? strtoul(getenv("RCR_PROFILE_EVENT_PC2"), NULL, 16) : 0x10000,
    getenv("RCR_PROFILE_EVENT_PC3") ? strtoul(getenv("RCR_PROFILE_EVENT_PC3"), NULL, 16) : 0x10000,
    getenv("RCR_PROFILE_EVENT_PC4") ? strtoul(getenv("RCR_PROFILE_EVENT_PC4"), NULL, 16) : 0x10000,
    getenv("RCR_PROFILE_EVENT_PC5") ? strtoul(getenv("RCR_PROFILE_EVENT_PC5"), NULL, 16) : 0x10000,
    getenv("RCR_PROFILE_EVENT_PC6") ? strtoul(getenv("RCR_PROFILE_EVENT_PC6"), NULL, 16) : 0x10000,
    getenv("RCR_PROFILE_EVENT_PC7") ? strtoul(getenv("RCR_PROFILE_EVENT_PC7"), NULL, 16) : 0x10000,
};
if (rcr_events && IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last) {
    for (unsigned event = 0; event < 8; ++event) {
        if (Registers.PCw == rcr_event_pc[event]) {
            const unsigned rcr_row_slot = Memory.RAM[0x1a] & 1;
            fprintf(rcr_events, "%u,%d,%d,%u,%06x,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u",
                IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, event,
                Registers.PBPC, Memory.RAM[0x100], Memory.RAM[0x10b],
                Memory.RAM[0x1ca0], Memory.RAM[0x1c84], Memory.RAM[0xdc],
                Memory.RAM[0xdd], Memory.RAM[0x3b], Memory.RAM[0xf6],
                Registers.S.W, Registers.P.W, Registers.D.W, Registers.DB,
                Memory.RAM[0x1ced], Memory.RAM[0x1cee], Registers.A.B.l,
                Registers.X.B.l, Registers.Y.B.l, Memory.RAM[0x1a],
                Memory.RAM[0x1b], Memory.RAM[0x1c], Memory.RAM[0x2a],
                Memory.RAM[0x2b], Memory.RAM[0x6be + rcr_row_slot],
                Memory.RAM[0x6c0 + rcr_row_slot],
                Memory.RAM[0x6c2 + rcr_row_slot],
                Memory.RAM[0x6cc + rcr_row_slot], Memory.RAM[0x6b6],
                Memory.RAM[0x6b7]);
            fprintf(rcr_events,
                ",%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u",
                Memory.RAM[0x1c19], Memory.RAM[0x1c16],
                Memory.RAM[0x1c17], Memory.RAM[0x2c], Memory.RAM[0x2d],
                Memory.RAM[0x2e], Memory.RAM[0x2f],
                Memory.RAM[0x6c6 + rcr_row_slot],
                Memory.RAM[0x6c8 + rcr_row_slot],
                Memory.RAM[0x6ca + rcr_row_slot],
                Memory.RAM[0x6ce + rcr_row_slot], Memory.RAM[0xfb],
                Memory.RAM[0xfc], Memory.RAM[0xfd]);
            fprintf(rcr_events,
                ",%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
                Memory.RAM[0x18], Memory.RAM[0x19], Memory.RAM[0x4e1],
                Memory.RAM[0x4f5], Memory.RAM[0x4f6],
                Memory.RAM[0x4f7], Memory.RAM[0x4f8],
                Memory.RAM[0x4f9], Memory.RAM[0x4fa]);
            fflush(rcr_events);
        }
    }
}
static FILE *rcr_camera_ram = getenv("RCR_PROFILE_CAMERA_RAM_TRACE") ? fopen(getenv("RCR_PROFILE_CAMERA_RAM_TRACE"), "w") : NULL;
if (rcr_camera_ram && CPU.PCBase && IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last) {
    const unsigned rcr_pc = Registers.PCw;
    const uint8 rcr_op = CPU.PCBase[rcr_pc];
    unsigned rcr_addr = 0x10000;
    if (Registers.D.W == 0 && (rcr_op == 0x85 || rcr_op == 0x86 || rcr_op == 0x84))
        rcr_addr = CPU.PCBase[rcr_pc + 1];
    if (rcr_op == 0x8d || rcr_op == 0x8e || rcr_op == 0x8c)
        rcr_addr = CPU.PCBase[rcr_pc + 1] | CPU.PCBase[rcr_pc + 2] << 8;
    if (rcr_addr == 0xdc || rcr_addr == 0xdd || rcr_addr == 0xf6 || rcr_addr == 0x3d) {
        fprintf(rcr_camera_ram, "%u,%d,%d,%06x,%02x,%04x,%u,%u,%u,%u\n",
            IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, Registers.PBPC,
            rcr_op, rcr_addr, Memory.RAM[rcr_addr], Registers.A.B.l,
            Registers.X.W, Registers.Y.W);
        fflush(rcr_camera_ram);
    }
}
// Optional coroutine scheduler trace.  Exact native runtime return PC is
// supplied by the candidate label file; FC60/FC70/FC73 and the fixed NMI
// entry are original-game addresses.  Host observation only.
static FILE *rcr_fc60 = getenv("RCR_FC60_TRACE") ? fopen(getenv("RCR_FC60_TRACE"), "w") : NULL;
if (rcr_fc60 && IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last) {
    const unsigned task_return = getenv("RCR_FC60_TASK_RETURN_PC") ? strtoul(getenv("RCR_FC60_TASK_RETURN_PC"), NULL, 16) : 0;
    const bool boot_event = (Registers.PB == 0 || Registers.PB == 0xc0) &&
        (Registers.PCw == 0x80fb || Registers.PCw == 0x8114 || Registers.PCw == 0x81a2);
    const bool game_event = Registers.PB >= 0xc1 && Registers.PB <= 0xc8 &&
        (Registers.PCw == 0xfc60 || Registers.PCw == 0xfc70 || Registers.PCw == 0xfc73 ||
         Registers.PCw == 0xff4f || (task_return && Registers.PCw == task_return));
    if (boot_event || game_event) {
        fprintf(rcr_fc60, "%u,%d,%d,%06x,%u,%u,%u,%u,%u\n",
            IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, Registers.PBPC,
            Memory.RAM[0x100], Memory.RAM[0x1ca0],
            Memory.RAM[0x1c04] | Memory.RAM[0x1c05] << 8,
            Memory.RAM[0x1c0a], Memory.FillRAM[0x4200]);
        fflush(rcr_fc60);
    }
}
// Optional window: translated NMI restore to first camera store, closed at
// the next original NMI if no camera store occurs. Default restore address
// is raster-rearm-02 ONLY. Set RCR_PROFILE_RESTORE_PC from each ROM's labels.
static bool rcr_before_camera = false;
static const bool rcr_camera_window = getenv("RCR_PROFILE_CAMERA_WINDOW") != NULL;
static bool rcr_before_dma = false;
static const bool rcr_dma_window = getenv("RCR_PROFILE_DMA_WINDOW") != NULL;
if (rcr_profile) {
    if (Registers.PB == 0 || Registers.PB == 0xc0) {
        if (Registers.PCw == 0x80fb) rcr_before_dma = true;
        if (CPU.PCBase && CPU.PCBase[Registers.PCw] == 0x8d &&
            CPU.PCBase[Registers.PCw+1] == 0x0b && CPU.PCBase[Registers.PCw+2] == 0x42)
            rcr_before_dma = false;
    }
    if (Registers.PB >= 0xc1 && Registers.PB <= 0xc8) {
        if (Registers.PCw == 0xff4f) rcr_before_camera = false;
        const unsigned restore_pc = getenv("RCR_PROFILE_RESTORE_PC") ? strtoul(getenv("RCR_PROFILE_RESTORE_PC"), NULL, 16) : 0x2925;
        if (Registers.PCw == restore_pc) rcr_before_camera = true;
        static FILE *boundary = getenv("RCR_PROFILE_BOUNDARY_TRACE") ? fopen(getenv("RCR_PROFILE_BOUNDARY_TRACE"), "w") : NULL;
        if (boundary && IPPU.TotalEmulatedFrames >= rcr_first && IPPU.TotalEmulatedFrames <= rcr_last &&
            (Registers.PCw == restore_pc || Registers.PCw == 0xe2b1 || Registers.PCw == 0xff4f)) {
            fprintf(boundary, "%u,%d,%d,%06x\n", IPPU.TotalEmulatedFrames, CPU.V_Counter, CPU.Cycles, Registers.PBPC);
            fflush(boundary);
        }
        if (Registers.PCw == 0xe2b1) rcr_before_camera = false;
    }
    if (rcr_profile_frame != IPPU.TotalEmulatedFrames) {
        if (rcr_profile_frame >= rcr_first && rcr_profile_frame <= rcr_last) {
            for (unsigned bank = 0; bank < 9; ++bank)
                for (unsigned pc = 0; pc < 65536; ++pc)
                    if (rcr_counts[bank][pc])
                        fprintf(rcr_profile, "%u,%02x,%04x,%u\n", rcr_profile_frame, 0xc0 + bank, pc, rcr_counts[bank][pc]);
            fflush(rcr_profile);
            memset(rcr_counts, 0, sizeof(rcr_counts));
        }
        rcr_profile_frame = IPPU.TotalEmulatedFrames;
    }
    if (rcr_profile_frame >= rcr_first && rcr_profile_frame <= rcr_last) {
        int bank = Registers.PB == 0 ? 0 : (int)Registers.PB - 0xc0;
        if (bank >= 0 && bank < 9 && (!rcr_camera_window || rcr_before_camera) &&
            (!rcr_dma_window || rcr_before_dma)) ++rcr_counts[bank][Registers.PCw];
    }
}
