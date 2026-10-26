#!/usr/bin/env python3
"""Recover exported symbols from a raw ARM vmlinux by parsing __ksymtab.

Linux 4.1 (no CONFIG_HAVE_ARCH_PREL32_RELOCATIONS): each entry is
    struct kernel_symbol { unsigned long value; const char *name; }
i.e. two absolute 32-bit words. We search for the (value,name) table by
trying candidate virtual bases and scoring entries whose name pointer lands
on a printable NUL-terminated string inside the image.
"""
import struct
import sys

img_path = sys.argv[1]
data = open(img_path, "rb").read()
n = len(data)


def cstr(off, limit=128):
    if off < 0 or off >= n:
        return None
    end = data.find(b"\x00", off, min(off + limit, n))
    if end <= off:
        return None
    s = data[off:end]
    if not all(32 <= c < 127 for c in s):
        return None
    return s.decode("ascii")


def score(base):
    hits = 0
    for o in range(0, n - 8, 4):
        val, namep = struct.unpack_from("<II", data, o)
        if namep < base:
            continue
        so = namep - base
        if so >= n:
            continue
        s = cstr(so)
        if s and len(s) >= 4 and (s[0].isalpha() or s[0] == "_"):
            if base <= val < base + n:
                hits += 1
    return hits


cands = [0xC0008000, 0xC0000000, 0x80008000, 0xC0004000]
best = max(cands, key=score)
print("base scores:", {hex(c): score(c) for c in cands})
print("chosen base:", hex(best))

syms = {}
for o in range(0, n - 8, 4):
    val, namep = struct.unpack_from("<II", data, o)
    if not (best <= val < best + n):
        continue
    if namep < best:
        continue
    s = cstr(namep - best)
    if not s or len(s) < 3 or not (s[0].isalpha() or s[0] == "_"):
        continue
    if not all(ch.isalnum() or ch in "_." for ch in s):
        continue
    syms.setdefault(s, []).append(val)

print("unique exported names:", len(syms))
for want in ("call_usermodehelper", "memcpy", "memset", "schedule_timeout_uninterruptible",
             "commit_creds", "prepare_kernel_cred", "v7_coherent_kern_range",
             "v7_flush_kern_cache_all", "printk", "kernel_read", "do_execve",
             "call_usermodehelper_setup", "kallsyms_lookup_name"):
    print("%-38s %s" % (want, [hex(v) for v in syms.get(want, [])]))

with open(sys.argv[2], "w") as f:
    for s in sorted(syms, key=lambda k: syms[k][0]):
        for v in syms[s]:
            f.write("%08x %s\n" % (v, s))
print("wrote", sys.argv[2])
