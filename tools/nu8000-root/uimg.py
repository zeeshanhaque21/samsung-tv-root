"""Parse a legacy u-boot uImage header and write the payload.

The input must be the uImage section itself, not an already-stripped payload:
the header lives at offset 0 and both CRCs are checked before anything is written.
"""
import struct
import sys
import zlib

MAGIC = 0x27051956

if len(sys.argv) != 3:
    sys.exit("usage: uimg.py <uImage> <payload-out>")

path, out = sys.argv[1], sys.argv[2]
d = open(path, "rb").read()
if len(d) < 64:
    sys.exit("input shorter than a u-boot header")

h = d[:64]
(magic, hcrc, t, size, load, ep, dcrc, os_, arch, typ, comp,
 name) = struct.unpack(">IIIIIIIBBBB32s", h)

if magic != MAGIC:
    sys.exit("not a uImage: magic %08x, expected %08x" % (magic, MAGIC))

hcrc_calc = zlib.crc32(h[:4] + b"\0\0\0\0" + h[8:]) & 0xFFFFFFFF
if hcrc_calc != hcrc:
    sys.exit("uImage header CRC mismatch: stored %08x, computed %08x" % (hcrc, hcrc_calc))

pay = d[64:64 + size]
if len(pay) != size:
    sys.exit("truncated payload: header says %d, file holds %d" % (size, len(pay)))

dcrc_calc = zlib.crc32(pay) & 0xFFFFFFFF
if dcrc_calc != dcrc:
    sys.exit("uImage data CRC mismatch: stored %08x, computed %08x" % (dcrc, dcrc_calc))

print("time %d size %d load 0x%x ep 0x%x dcrc %08x os %d arch %d type %d comp %d name %s"
      % (t, size, load, ep, dcrc, os_, arch, typ, comp, name.rstrip(b"\0").decode("ascii", "replace")))
print("payload len %d first16 %s" % (len(pay), pay[:16].hex()))
open(out, "wb").write(pay)
