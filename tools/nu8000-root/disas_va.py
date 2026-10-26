#!/usr/bin/env python3
"""Disassemble raw ARM vmlinux at a virtual address (base 0xc0008000)."""
import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

path = sys.argv[1]
base = 0xC0008000
data = open(path, "rb").read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)

for arg in sys.argv[2:]:
    va = int(arg, 16)
    off = va - base
    print("\n===== %08x (file+0x%x) =====" % (va, off))
    print("bytes:", data[off:off + 32].hex())
    for ins in md.disasm(data[off:off + 96], va):
        print("%08x: %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
