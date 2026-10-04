/* Bounded upstream frame identity observer, MIPS o32/no libc. */
typedef unsigned char u8;
typedef unsigned short u16;
struct sockaddr_ll { u16 family, protocol; int ifindex; u16 hatype; u8 pkttype, halen, addr[8]; };
static u8 frame[2048];
static long sys3(long nr,long x,long y,long z)
{
    register long v0 __asm__("$2")=nr;
    register long a0 __asm__("$4")=x,a1 __asm__("$5")=y,a2 __asm__("$6")=z,a3 __asm__("$7");
    __asm__ volatile("syscall":"+r"(v0),"=r"(a3):"r"(a0),"r"(a1),"r"(a2):
     "memory","$3","$8","$9","$10","$11","$12","$13","$14","$15","$24","$25","hi","lo");
    return a3?-v0:v0;
}
static long sys4(long nr,long x,long y,long z,long w)
{
    register long v0 __asm__("$2")=nr;
    register long a0 __asm__("$4")=x,a1 __asm__("$5")=y,a2 __asm__("$6")=z,a3 __asm__("$7")=w;
    __asm__ volatile("syscall":"+r"(v0),"+r"(a3):"r"(a0),"r"(a1),"r"(a2):
     "memory","$3","$8","$9","$10","$11","$12","$13","$14","$15","$24","$25","hi","lo");
    return a3?-v0:v0;
}
static int same(const u8*a,const u8*b,int n){while(n--)if(*a++!=*b++)return 0;return 1;}
static void decimal(char *buf,int *at,u8 v)
{
    if(v>=100)buf[(*at)++]='0'+v/100;
    if(v>=10)buf[(*at)++]='0'+(v/10)%10;
    buf[(*at)++]='0'+v%10;
}
static void ip_text(char *buf,int *at,const u8 *ip)
{
    int i;
    for(i=0;i<4;i++){if(i)buf[(*at)++]='.';decimal(buf,at,ip[i]);}
}
static void mac_text(char *buf,int *at,const u8 *mac)
{
    static const char h[]="0123456789ABCDEF";
    int i;
    for(i=0;i<6;i++){
        if(i)buf[(*at)++]=':';
        buf[(*at)++]=h[mac[i]>>4];buf[(*at)++]=h[mac[i]&15];
    }
}
void _start(void)
{
    static const u8 device_mac[6]={0x20,0xe5,0x2a,0x02,0x15,0xd0};
    struct sockaddr_ll addr;
    u8 *p=(u8*)&addr;
    char line[128];
    int i,n,len,seen=0,eligible=0;
    long child=sys3(4002,0,0,0),fd;
    if(child!=0)sys3(4001,child<0,0,0);
    sys3(4066,0,0,0);
    fd=sys3(4183,17,3,0x0300);
    for(i=0;i<(int)sizeof(addr);i++)p[i]=0;
    addr.family=17;addr.protocol=0x0300;addr.ifindex=3;/* eth1 */
    if(fd<0||sys3(4169,fd,(long)&addr,sizeof(addr))<0)sys3(4001,2,0,0);
    while(seen<40){
        len=sys4(4175,fd,(long)frame,sizeof(frame),0);
        if(len<34||frame[12]!=0x08||frame[13]!=0x00||(frame[14]>>4)!=4)continue;
        if(!same(frame+6,device_mac,6))continue;
        eligible++;
        if(eligible%10!=1)continue;
        n=0;line[n++]='W';line[n++]='A';line[n++]='N';line[n++]=' ';
        line[n++]='s';line[n++]='r';line[n++]='c';line[n++]='M';line[n++]='A';line[n++]='C';line[n++]='=';
        mac_text(line,&n,frame+6);line[n++]=' ';
        line[n++]='s';line[n++]='r';line[n++]='c';line[n++]='I';line[n++]='P';line[n++]='=';
        ip_text(line,&n,frame+26);line[n++]=' ';
        line[n++]='d';line[n++]='s';line[n++]='t';line[n++]='I';line[n++]='P';line[n++]='=';
        ip_text(line,&n,frame+30);line[n++]='\n';
        sys3(4004,1,(long)line,n);seen++;
    }
    sys3(4001,0,0,0);__builtin_unreachable();
}
