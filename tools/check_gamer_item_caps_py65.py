from py65.devices.mpu6502 import MPU
import sys
def mk(rom, bank):
    m=MPU(); mem=bytearray(rom[bank*0x10000:(bank+1)*0x10000]); mem[0:0x800]=bytes(0x800); m.memory=mem; return m
def run(m, pc, stop, n=500):
    m.pc=pc
    for _ in range(n):
        if m.pc==stop: return True
        m.step()
    return False
res=[]
for name in sys.argv[1:]:
    rom=open(name,'rb').read()
    for skill in (1,2,3,4):
        for cur,add in ((63,1),(62,2),(100,5),(126,4),(120,1)):
            if skill!=3 and cur>63: continue
            m=mk(rom,3); m.memory[0x64C]=skill
            m.memory[0x2C]=0xAF; m.memory[0x2D]=0x04; m.y=0; m.x=4  # agility p1
            m.memory[0x4AF]=cur; m.memory[0x133]=cur
            s=cur+add; m.sp=0xFE; m.memory[0x1FF]=s  # pushed sum
            ok=run(m,0x92F9,0x9315)
            res.append((name[-30:],skill,cur,add,ok,m.memory[0x4AF],m.a))
    m=mk(rom,4); m.x=0; m.y=0; m.sp=0xFF
    for k,v in enumerate([10,63,64,100,127,0,200,5]): m.memory[0x58E+k]=v
    m.memory[0x4BF]=0x99
    ok=run(m,0xBE44,0xBE47)
    print(name[-30:],'pw',ok,list(m.memory[0x58E:0x596]),hex(m.a))
for r in res: print(r)
