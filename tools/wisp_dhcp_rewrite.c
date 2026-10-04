/* RAM-only DHCP reply MAC repair for Broadcom PSR AP (MIPS o32, no libc). */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
struct sockaddr_ll { u16 family, protocol; int ifindex; u16 hatype; u8 pkttype, halen, addr[8]; };
static u8 packet[2048];
static u8 out[2048];
static struct { u32 xid; u8 mac[6]; } clients[32];
static int next_client, output_count;
static long bound_fd;
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
static u32 get32(const u8 *p) { return ((u32)get16(p)<<16) | get16(p+2); }
static void put16(u8 *p, u16 v) { p[0]=v>>8; p[1]=v; }
static void copy(u8 *to, const u8 *from, int n) { while(n--)*to++=*from++; }
static int same(const u8 *a, const u8 *b, int n) { while(n--)if(*a++!=*b++)return 0; return 1; }
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
    int ihl, u, n=0, i, client_port;
    u32 xid;
    if (len<42 || get16(f+12)!=0x0800 || (f[14]>>4)!=4 || f[23]!=17) return 0;
    ihl=(f[14]&15)*4; u=14+ihl;
    if (ihl<20 || len<u+8) return 0;
    if (!((get16(f+u)==67 && get16(f+u+2)==68) ||
          (get16(f+u)==68 && get16(f+u+2)==67))) return 0;
    if (len < u+8+34) return 0;
    client_port = get16(f+u)==68;
    xid = get32(f+u+8+4);
    if (client_port) {
        clients[next_client].xid=xid;
        copy(clients[next_client].mac,f+6,6);
        next_client=(next_client+1)&31;
    } else {
        for(i=0;i<32;i++) {
            if(clients[i].xid==xid && !same(f,clients[i].mac,6)) {
                copy(out,f,len);
                copy(out,clients[i].mac,6);
                copy(out+u+8+28,clients[i].mac,6);
                put16(out+u+6,0); /* UDP checksum zero is valid for IPv4. */
                if(output_count++<20) {
                    static const char message[]="DHCP reply MAC repaired\n";
                    sys3(4004,1,(long)message,sizeof(message)-1);
                }
                sys4(4178,bound_fd,(long)out,len,0);
                break;
            }
        }
    }
    line[n++]='D'; line[n++]='H'; line[n++]='C'; line[n++]='P'; line[n++]=' ';
    line[n++]=get16(f+u)==67?'S':'C'; line[n++]=' ';
    n+=mac(line+n,f+6); line[n++]=' ';
    n+=mac(line+n,f); line[n++]=' ';
    line[n++]='c'; line[n++]='h'; line[n++]='=';
    n+=mac(line+n,f+u+8+28);
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
    bound_fd=fd;
    while(seen<200) {
        len=sys4(4175,fd,(long)packet,sizeof(packet),0);
        if(len>0) seen+=note(packet,len);
    }
    sys3(4001,0,0,0);
    __builtin_unreachable();
}
