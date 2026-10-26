# NU8000 root research

> Offline static research note for `UN65NU8000FXZA`, firmware `T-KTM2AKUC-1355.1`.
> No TV was contacted.
> Nothing was flashed, mounted on hardware, or executed on a device.
> All binaries were inspected statically on the host.

## Verdict

**Candidate:** the Samsung out-of-tree exFAT driver stack overflow in `exfat_get_uni_name_from_ext_entry`, reached from directory enumeration.

**Status: vulnerable, exact binary match, full root chain not established.**
The defect, its call path, its frame geometry, and the kernel primitives it needs are present in this exact build.
The remaining chain stages (UEP neutralization, post-copy stack saver, cache flush sequence, pivot assembly) are not derived for Kant-M2 and no public payload exists for this family.
The hardware gate is **not** met.

What that buys, and what it does not:

| Claim | Confidence | Basis |
| --- | --- | --- |
| The vulnerable function is in the shipped image and is byte-identical to the published 2018 Kant-M2 candidate module | proven | E1, E2 |
| The vulnerable function is reachable from the readdir path in this build | proven statically | E3, E4 |
| The overflow corrupts the `ffsReadDir` saved-register block at `+520..+556` | proven from this binary | E4 |
| A kernel-mode `pc`/`sp` control primitive follows | high, not demonstrated here | E2, E4, E9; the register mapping is derived from this binary, but the control-flow effect is extrapolated from the sibling 2019 emulation, not observed on this image |
| A working local privilege escalation exists for this TV | unproven | no chain, no UEP neutralizer, no emulation |
| A crafted volume causes a reliable DoS when something lists it | high, runtime unverified | E2; enumeration path not observed on this TV |

## Evidence ledger

| ID | Artifact | SHA-256 | Notes |
| --- | --- | --- | --- |
| E1 | `exfat_core.ko` from this rootfs | `22f43de04d7ee4ff4183e99474e4b3c0a02a3690f1aa0636961daceebfe602cf` | 63,398 bytes; equals the published `T-KTM2DEUC` 1400.2 module hash exactly |
| E2 | same module, `.text+0x1bc4` `exfat_get_uni_name_from_ext_entry` | function size `0x104` | instruction-for-instruction match with the published Kant listing |
| E3 | `.rel.data+0x1c` relocation | type 2, symbol `exfat_get_uni_name_from_ext_entry` | binds the `fs_func` slot used by the readdir call |
| E4 | `ffsReadDir` disassembly, `.text+0x260c`, size `0x4cc` | `44c352350c651b0abd21b4771f08f723213dcc165f7d4cda7daef23060247db1` | frame and call site |
| E5 | raw kernel image (`uImage` payload) | `6d49f38eb43bf7e193870a874a14fe2597422416ca5ef23d257150c0340cb07f` | 6,505,800 bytes; uncompressed ARM kernel, base `0xc0008000` |
| E6 | recovered export table | `7847f9fe7869c4bae9a6980f057456b84d0c0cc0489135f073190f38dfede805` | 8,465 unique exported names, 9,038 entries |
| E7 | `exfat_fs.ko` | `e86e85c54e7b8feeb1f8bc56ca3ef877bb9bac09da65d8a3b020d76f964f5a90` | 29,342 bytes; vermagic `8970658 ... ARMv7 p2v8` |
| E8 | public candidate source | `Luminger/samsung-tv-usb-root` @ `223f1cd6cca185f93fe7db53ef71eb52963a7086` | AGPL-3.0; findings cited, no code copied |
| E9 | `exfat_mount` and `exfat_fs_func`, `.text+0x3744` and `.data+0x0` | mount-time store at `0x383c`; MOVW/MOVT relocations at `0x37e0`/`0x37e4` | establishes how the `fs_func` table reaches the readdir call |

Reproduce with `tools/nu8000-root/{uimg,ksymtab,disas_ko,syms,disas_va}.py` and the patched VDFS extractor used for E1.
The scripts need `capstone` and `pyelftools`; they take the module, image, or virtual address as an argument and do not depend on the firmware living at a fixed path.

### Evidence locations

The decrypted firmware and everything derived from it are **not** in git.
They live in the primary checkout under `.work/`, which is gitignored there:

| Artifact | Path (primary checkout) | Needed by |
| --- | --- | --- |
| `uImage` section, 6,506,176 bytes, SHA-256 `379182ab77bde4322b61e378905ab05c18de9bfd7d3cf86bf0f5c9d06c174f35` | `.work/nu8000-firmware/decrypted/full-01-verifier/02_uImage` | `uimg.py`, which parses the 64-byte u-boot header |
| `platform.img`, 1,283,346,432 bytes, SHA-256 `da4221274e5a86021033748f19a7075832bcd54ac1580985cdea156c3e82645c` | `.work/nu8000-firmware/decrypted/full-01-verifier/07_platform.img` | VDFS extraction that yields E1 and E7 |
| extracted rootfs | worktree-local `.work/rootfs/` (1.8 GB) | E1, E3, E7, E9 |
| header-stripped payload, SHA-256 `6d49f38e...` | worktree-local `.work/uImage.payload` | E5, E6, gadget checks |
| export dump and frame disassembly | worktree-local `.work/ksymtab.txt`, `.work/ffsReadDir.asm` | E4, E6 |

`uimg.py` takes the **original section**, not the payload, because it reads the u-boot header at offset 0 and refuses to write anything unless the magic and both CRCs match.
Running it on `.work/uImage.payload` exits with a magic mismatch, which is the guard against feeding it the wrong file.
Re-running it on the section reproduces E5 exactly: payload length 6,505,800 and SHA-256 `6d49f38e...`.
The worktree `.work/` paths are disposable; only the two primary-checkout inputs above are authoritative.


## 1. Driver form and reachability

Observed: exFAT is **not** built into the kernel.
It ships as two loadable modules, `exfat_core.ko` and `exfat_fs.ko`, under `/usr/lib/modules/4.1.10/kernel/`.
`modules.dep` orders `exfat_fs.ko` after `exfat_core.ko`.
`/etc/modprobe.d/modprobe.conf` aliases `fs-exfat` to `exfat_fs`, so a mount attempt resolves through the normal module autoload path.
`/etc/usb/mount.conf` gives the `[exfat]` class mount options `uid=0,gid=10001,dmask=0000,fmask=0111` with `MS_DIRSYNC,MS_NOATIME`.
Unlike the `ext4` and `ntfs` entries in the same file, the exFAT entry carries **no** `MS_NOEXEC` and **no** `MS_NOSUID`.

Observed: the module identifies itself as `exFAT: Core Version 1.1.11p1(13-FEB-2013)`.
That is the pre-fix Samsung code base; upstream's bound for this loop is `d42334578eba` (CVE-2023-4273), which this driver never received.

Inference, labelled: a volume inserted on the TV is mounted through this module, and the mount options permit executing files from it.
Unknown: which process enumerates the volume, and when.
No offline artifact can establish that timing.

## 2. Exact binary match

E1 is the decisive result.
The `exfat_core.ko` in this `T-KTM2AKUC-1355.1` rootfs hashes to `22f43de0...`, the same value the public compatibility matrix records for `T-KTM2DEUC` 1400.2, a 2018 Kant-M2 set.
So the vulnerable driver is not merely "similar" here; for this file it is the same build.

E2 confirms the vulnerable routine at `.text+0x1bc4`.
The loop has no bound against the 256-entry name buffer:

```
1bfc: ldrb r5, [r0, #1]        ; num_ext, raw on-disk byte
1c20: ldr  r3, [sb, #0xc]      ; es->num_entries
1c24: cmp  r3, #2
1c28: bls  1ca8                ; the only size-related guard
1c4c: mla  r5, r3, r5, r4      ; end = uniname + 30*num_ext
1c50: sub  r5, r5, #0x1e       ;      - 30
1c54..1c78: copy 15 halfwords per name entry
1c98: cmp  r5, r4 / bne 1c54   ; loop while uniname != end
```

No stack canary is present in the function.
No comparison against 255, 256, or a name-length maximum appears anywhere in it.

E3 closes the reachability question at the binary level.
The `fs_func` slot at `.data+0x1c` is relocated against `exfat_get_uni_name_from_ext_entry`, and `ffsReadDir` loads exactly that slot:

```
2950: ldr r4, [ip, #0x1c]
2954: blx r4
```

So the readdir path calls the vulnerable routine through a function-pointer table, not by an offset that might belong to a sibling.

E9 closes the other half: how that table is installed.
`exfat_mount` materialises the table address and stores it in the per-superblock private structure:

```
3774: ldr  r3, [r0, #0x240]   ; r3 = fs_info
37e0: movw ip, #0             ; R_ARM_MOVW_ABS_NC against .LANCHOR2
37e4: movt ip, #0             ; R_ARM_MOVT_ABS    against .LANCHOR2
383c: str  ip, [r3, #0x80]    ; fs_info->fs_func = &exfat_fs_func
```

`.LANCHOR2` and `exfat_fs_func` both resolve to `.data+0x0`, so the anchor the compiler emitted for the mount path is the table itself.
The consumer walks the same path in reverse:

```
2628: ldr r7, [r0, #0x1c]     ; p_fs -> super_block
263c: ldr sl, [r7, #0x240]    ; super_block -> fs_info
2944: ldr ip, [sl, #0x80]     ; fs_info -> fs_func table
2950: ldr r4, [ip, #0x1c]     ; table + 0x1c
2954: blx r4                  ; -> exfat_get_uni_name_from_ext_entry
```

Observed: the mount-time store and the read-time load use the same `fs_info+0x80` slot, and the read uses the same `+0x1c` entry the relocation binds.
That rules out the alternative reading in which `+0x1c` belonged to an unrelated object that merely shared the offset.
The indirection is therefore mount-established, not an artifact of how the module happened to be linked.

## 3. Frame geometry in this binary

E4 shows the same 11-register APCS frame as the published Kant analysis:

```
260c: mov  ip, sp
2610: push {r4, r5, r6, r7, r8, sb, sl, fp, ip, lr, pc}
2614: sub  fp, ip, #4
2618: sub  sp, sp, #0x264
292c: sub  r3, fp, #0x230      ; arg3 = uniname = fp-560
2954: blx  r4                  ; exfat_get_uni_name_from_ext_entry
2648: sub  sp, fp, #0x28
264c: ldm  sp, {r4, r5, r6, r7, r8, sb, sl, fp, sp, pc}
```

The local buffer spans `fp-560` to `fp-40`, exactly 520 bytes, and the epilogue reloads ten words starting at `fp-40`.
Payload offsets therefore map as follows:

| offset from `uniname` | restored register |
| ---: | --- |
| +520 | `r4` |
| +524 | `r5` |
| +528 | `r6` |
| +532 | `r7` |
| +536 | `r8` |
| +540 | `sb` |
| +544 | `sl` |
| +548 | `fp` |
| +552 | `sp` |
| +556 | `pc` |

Byte accounting, corrected for the trailing NUL halfword.
Each name entry contributes a 30-byte body fragment, and the routine then stores one `0x0000` halfword at the end of that fragment (`strh r8, [r4]` at `1c90`).
So the body is `30*(num_ext-1)` bytes and the highest offset touched is `30*(num_ext-1)+2`.
A bound of `30*num_ext+2` is a safe over-estimate and is what the table below uses.

| `num_ext` | body bytes | highest offset touched | effect |
| ---: | ---: | ---: | --- |
| 3 | 60 | 62 | parses, no overflow |
| 18 | 510 | 512 | last value that fits the 520-byte buffer |
| 19 | 540 | 542 | reaches `r8`; the trailing NUL lands in `sb` |
| 20 | 570 | 572 | reaches `sp` and `pc` |
| 254 | 7,590 | 7,592 | maximum accepted value |

Overflow therefore begins at `num_ext = 19`, and `pc`/`sp` coverage begins at `num_ext = 20`.
The frame conclusions are unchanged by the NUL accounting; it only extends the written span by two bytes.
Accepted range is `3..254`.
Values `0..1` fail the `num_entries < 3` guard, `2` parses but writes a single 30-byte fragment and cannot overflow, and `255` is unusable because `get_entry_set_in_dir` computes `num_ext + 1` in a `UINT8` and wraps to zero, which also fails the guard.
At the top of the range the write runs 7,590 bytes past a 520-byte buffer, deep into the caller's frames; those values are valid inputs but carry a much higher chance of an immediate fatal fault than the minimal `19..22` window.

Note: these offsets are **not** copied from the 2019 Muse.M profile.
That profile's `ffsReadDir` sits at `.text+0x2670`; ours sits at `.text+0x260c`.
The geometry agrees because the buffer size and epilogue shape agree, which is a derived result for this binary.

## 4. Kernel primitives in this image

The kernel carries no `IKCONFIG` payload and no compressed `kallsyms` table.
Symbols were recovered instead from `__ksymtab` plus `__ksymtab_strings`, using absolute `{value, name}` pairs.
Scoring the candidate bases gives 10,918 consistent entries at `0xc0008000` and fewer at every alternative, which fixes the virtual base.

Recovered exports relevant to this chain:

| Symbol | Address |
| --- | ---: |
| `call_usermodehelper` | `0xc0039a78` |
| `call_usermodehelper_setup` | `0xc0039434` |
| `memcpy` | `0xc01fa720` |
| `memset` | `0xc01fada0` |
| `schedule_timeout_uninterruptible` | `0xc04cc05c` |
| `v7_coherent_kern_range` | `0xc001cba8` |
| `v7_flush_kern_cache_all` | `0xc001cb74` |
| `commit_creds` | `0xc00441dc` |
| `prepare_kernel_cred` | `0xc004481c` |

Every one of the four addresses the public matrix lists for the 2018 Kant-M2 row matches this image exactly:

| Primitive | Published Kant-M2 | This image |
| --- | ---: | ---: |
| `call_usermodehelper` | `0xc0039a78` | `0xc0039a78` |
| `memcpy` | `0xc01fa720` | `0xc01fa720` |
| coherent range | `0xc001cba8` | `0xc001cba8` |
| `schedule_timeout_uninterruptible` | `0xc04cc05c` | `0xc04cc05c` |

The two chain gadgets the matrix lists for that row also verify here by disassembly, not by assumption:

```
c04dde3c: ldm ip, {r2, r3, r4, r7, r8, sb, sl, sp, lr, pc}
c010598c: mov r2, r4 ; mov r1, ip ; mov r0, r6 ; blx r3
```

The second is the memcpy call window with the length in `r4`, matching the matrix's "`r4` length" annotation.
The cave at `0xc0008358..0xc0009000` is present and **entirely zero**: 3,240 bytes, zero non-zero words.
The kernel banner is `Linux version 4.1.10 ... #1 SMP PREEMPT Fri Jan 16 05:54:15 UTC 2026`, consistent with a 1355.1 build.

## 5. What remains before any hardware step

These are the open gates, in dependency order.

1. **UEP / SFD neutralization.**
   The kernel contains Samsung's SFD/UEP enforcement code, including `SfdUepVerifyExecutableBinary`, `SfdUepCheckFileSignature`, `SfdUepVerifyDynamicLibrary`, and `SfdUepHandleVerificationResult`.
   The published Kant-M2 row states plainly that neither 2017 nor 2018 kernels contain the 2019 neutralizer bytes.
   No hook address, no enforcement-mode determination, and no patch exists for this build.
   Without this, a kernel primitive cannot start an unsigned payload such as Dropbear.
2. **Post-copy stack saver and cache-flush sequence.**
   The 2019 chain needs a saver gadget and two coherent-cache flush stages between the copy and the jump.
   The 2019 addresses are Muse.M-specific and do not transfer.
   The flush target itself is exported here (`v7_coherent_kern_range`), so this stage is mechanical rather than architectural, but it is not derived.
3. **Pivot assembly.**
   `ip` survives the epilogue and points into the overflowed stream at `fp+4`, which is offset 564 from `uniname`.
   `num_ext = 21` writes 600 bytes and just reaches `ip`; the `ldm ip` gadget then reads ten words through offset 603, so a usable landing needs `num_ext >= 22`.
   Turning that into a stable landing pad, with the cave as the copy destination, is chain work that has not been done for this image.
4. **Module load base.**
   Module-internal offsets are base-relative and therefore valid, but the runtime `MODULES_VADDR` on this TV is unknown.
   This matters only for absolute references into the module, which the chain design should avoid.
5. **Runtime enumeration.**
   The mount options and module aliases show intent, not behaviour.
   Nothing here proves which process lists a freshly inserted volume, or how quickly.
6. **Emulation.**
   Not attempted.
   The 2019 lab ran a vendor-source rebuild, not the shipped image, and this kernel has no matching upstream machine.
   A faithful boot of this exact kernel would need Samsung's board support; a partial harness would prove the copy arithmetic, not the chain.
   Any future emulation claim must be labelled as such.
7. **Hardware proof.**
   Out of scope for this phase, and not implied by anything above.

## 6. Risk and recovery posture

The candidate path is USB-only and does not write flash, bootloader state, or the rootfs.
A crash corrupts RAM only, and a power cycle restores the previous state.
The realistic failure mode is a wedged enumerating task or an RCU stall, which can present as a hung picture until power is removed.
That is a denial of service, not persistent damage.
A stock USB image and a known-good FAT32 stick remain the recovery baseline.
No claim is made about watchdog or panic behaviour on this model; neither was inspected.

## 7. Decision

**No-go for hardware in this phase.**
The bug is real, exact, and reachable in this image; the chain is not.
Treating "same module bytes as a published candidate" as "root is close" would be the error this note exists to prevent.

Recommended next step, if the route is continued: one more bounded offline phase with a hard stop.
Derive, in this order, (a) the UEP hook and its enforcement mode, (b) the saver and flush sequence, (c) a complete register-level chain walk against the E4 frame.
Stop and report if (a) cannot be located by static means, because no amount of gadget work substitutes for it.

Do not do any of the following on the strength of this note:

- insert a crafted exFAT volume into the TV;
- flash, downgrade, or repack firmware;
- retry the `appinstall` injection probe;
- reuse any Muse.M address, cave offset, or payload byte.

If the UEP stage proves out of reach offline, the correct outcome is the non-root dashboard path, not a search for an unrelated vulnerability.

## 8. Provenance and licensing

Public candidate: `https://github.com/Luminger/samsung-tv-usb-root`, commit `223f1cd6cca185f93fe7db53ef71eb52963a7086`, license AGPL-3.0.
Relevant files: `docs/FIRMWARE-COMPATIBILITY.md`, `docs/PROVENANCE.md`, `research/findings/exploit-004-exfat-numext.md`.
Only factual findings and hashes are cited here; no source code, payload, image, or module is copied or redistributed.

Firmware evidence is the decrypted `T-KTM2AKUC-1355.1` artifact documented in `NU8000_FIRMWARE_ASSESSMENT.md`.
That file exists only in the primary checkout at `/Users/zeeshanhaque/Projects/hacks/samsung-tv-root/docs/research-notes/NU8000_FIRMWARE_ASSESSMENT.md`, and it is not mirrored on this branch.
Its identity and extraction results are used as given; this note does not re-derive them.
Only the three values this note actually depends on are restated here, so the chain of custody survives without that file:

| Fact taken from the assessment | Value |
| --- | --- |
| `upgrade.msd` container | `e8afd05a510adb4e9dd91dee22d9a78198fa1e9d7abd72efb44ec20922c7fb61` |
| `platform.img` section | `da4221274e5a86021033748f19a7075832bcd54ac1580985cdea156c3e82645c` |
| `uImage` section | `379182ab77bde4322b61e378905ab05c18de9bfd7d3cf86bf0f5c9d06c174f35` |

Everything else in that assessment, including the archive-root and `appinstall` findings, is out of scope here and is deliberately not duplicated.

