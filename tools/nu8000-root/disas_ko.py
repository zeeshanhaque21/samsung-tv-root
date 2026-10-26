#!/usr/bin/env python3
"""Disassemble named functions from an ARM ELF object (.ko) with capstone."""
import sys
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB

def load(path):
    f = open(path, "rb")
    e = ELFFile(f)
    symtab = e.get_section_by_name(".symtab")
    text = e.get_section_by_name(".text")
    return f, e, symtab, text

def main():
    path = sys.argv[1]
    names = sys.argv[2:]
    f, e, symtab, text = load(path)
    tdata = text.data()
    taddr = text["sh_addr"]
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    md.detail = False
    for sym in symtab.iter_symbols():
        if names and sym.name not in names:
            continue
        if sym["st_info"]["type"] != "STT_FUNC":
            continue
        off = sym["st_value"] - taddr
        size = sym["st_size"]
        if off < 0 or off >= len(tdata):
            continue
        print(f"\n===== {sym.name}  .text+0x{off:x}  size 0x{size:x} =====")
        code = tdata[off:off + size]
        for ins in md.disasm(code, sym["st_value"]):
            print(f"{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

if __name__ == "__main__":
    main()
