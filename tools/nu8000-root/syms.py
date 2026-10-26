from elftools.elf.elffile import ELFFile
import sys
p=sys.argv[1]
e=ELFFile(open(p,"rb")); st=e.get_section_by_name(".symtab"); tx=e.get_section_by_name(".text")["sh_addr"]
want=sys.argv[2:]
for s in st.iter_symbols():
    if s.name in want:
        off=s["st_value"]-tx
        print("%-42s .text+0x%x size=0x%x type=%s" % (s.name, off, s["st_size"], s["st_info"]["type"]))
