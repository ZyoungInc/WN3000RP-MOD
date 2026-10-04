/* Bounded RAM-only DHCP frame observer on br0 (MIPS o32, no libc). */
typedef unsigned char u8;
typedef unsigned short u16;
struct sockaddr_ll { u16 family, protocol; int ifindex; u16 hatype; u8 pkttype, halen, addr[8]; };
static u8 packet[2048];
static long sys3(long nr, long x, long y, long z)
{
    register long v0 __asm__("$2") = nr;
    register long a0 __asm__("$4") = x;
    register long a1 __asm__("$5") = y;
    register long a2 __asm__("$6") = z;
    register long a3 __asm__("$7");
    __asm__ volatile("syscall" : "+r"(v0), "=r"(a3) : "r"(a0), "r"(a1), "r"(a2)
                     : "memory", "$3", "$8", "$9", "$10", "$11", "$12", "$13", "$14", "$15", "$24", "$25", "hi", "lo");
    return a3 ? -v0 : v0;
}
static long sys4(long nr, long x, long y, long z, long w)
{
    register long v0 __asm__("$2") = nr;
    register long a0 __asm__("$4") = x;
    register long a1 __asm__("$5") = y;
    register long a2 __asm__("$6") = z;
    register long a3 __asm__("$7") = w;
    __asm__ volatile("syscall" : "+r"(v0), "+r"(a3) : "r"(a0), "r"(a1), "r"(a2)
                     : "memory", "$3", "$8", "$9", "$10", "$11", "$12", "$13", "$14", "$15", "$24", "$25", "hi", "lo");
    return a3 ? -v0 : v0;
}
static u16 get16(const u8 *p) { return ((u16)p[0] << 8) | p[1]; }
static void hexbyte(char *p, u8 n)
{
    static const char h[] = "0123456789ABCDEF";
    p[0] = h[n >> 4]; p[1] = h[n & 15];
}
static int mac(char *p, const u8 *m)
{
    int i;
    for (i=0;i<6;i++) { hexbyte(p+3*i,m[i]); if(i<5)p[3*i+2]=':'; }
    return 17;
}
static int note(const u8 *f, int len)
{
    char line[100];
    int ihl, u, n=0;
    if (len<42 || get16(f+12)!=0x0800 || (f[14]>>4)!=4 || f[23]!=17) return 0;
    ihl=(f[14]&15)*4; u=14+ihl;
    if (ihl<20 || len<u+8) return 0;
    if (!((get16(f+u)==67 && get16(f+u+2)==68) ||
          (get16(f+u)==68 && get16(f+u+2)==67))) return 0;
    line[n++]='D'; line[n++]='H'; line[n++]='C'; line[n++]='P'; line[n++]=' ';
    line[n++]=get16(f+u)==67?'S':'C'; line[n++]=' ';
    n+=mac(line+n,f+6); line[n++]=' ';
    n+=mac(line+n,f); line[n++]=' ';
    line[n++]='c'; line[n++]='h'; line[n++]='=';
    if (len>=u+8+34) n+=mac(line+n,f+u+8+28);
    else {line[n++]='?';}
    line[n++]='\n';
    sys3(4004,1,(long)line,n);
    return 1;
}
void _start(void)
{
    struct sockaddr_ll addr;
    u8 *p=(u8*)&addr;
    long fd, child;
    int i, len, seen=0;
    child=sys3(4002,0,0,0);
    if(child!=0)sys3(4001,child<0,0,0);
    sys3(4066,0,0,0);
    fd=sys3(4183,17,3,0x0300);
    for(i=0;i<(int)sizeof(addr);i++)p[i]=0;
    addr.family=17; addr.protocol=0x0300; addr.ifindex=6;
    if(fd<0 || sys3(4169,fd,(long)&addr,sizeof(addr))<0)sys3(4001,2,0,0);
    while(seen<200) {
        len=sys4(4175,fd,(long)packet,sizeof(packet),0);
        if(len>0) seen+=note(packet,len);
    }
    sys3(4001,0,0,0);
    __builtin_unreachable();
}
