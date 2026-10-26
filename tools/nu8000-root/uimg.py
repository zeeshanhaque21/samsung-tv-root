import struct, sys, zlib
p=sys.argv[1]; d=open(p,"rb").read()
h=d[:64]
magic,hcrc,t,size,load,ep,dcrc,os_,arch,typ,comp,name=struct.unpack(">IIIIIIIBBBB32s",h)
print("magic %08x hcrc %08x ok=%s" % (magic,hcrc, (zlib.crc32(h[:4]+b"\0\0\0\0"+h[8:])&0xffffffff)==hcrc))
print("time",t,"size",size,"load",hex(load),"ep",hex(ep),"dcrc",hex(dcrc),"os",os_,"arch",arch,"type",typ,"comp",comp,"name",name.rstrip(b"\0"))
pay=d[64:64+size]
print("payload len",len(pay),"first16",pay[:16].hex())
open(sys.argv[2],"wb").write(pay)
