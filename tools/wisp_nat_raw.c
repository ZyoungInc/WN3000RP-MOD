/*
 * Temporary IPv4 NAT experiment for WN3000RP v1 / Linux 2.6.22 MIPS o32.
 * Runs entirely from /tmp with no libc and no kernel modules. Test network only.
 * Handles TCP, UDP and ICMP echo; deliberately drops fragments and IPv6.
 */

#define WAN_INDEX 3             /* eth1, confirmed via /sys/class/net */
#define LAN_INDEX 6             /* br0 */
#define WAN_IP 0xc0a89d16u     /* 192.168.157.22 */
#define WAN_GATEWAY 0xc0a89df5u /* 192.168.157.245 */
#define LAN_NET 0xc0a83200u    /* 192.168.50.0 */
#define LAN_MASK 0xffffff00u
#define MAP_SIZE 384
#define ETH_P_ALL_BE 0x0300

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

struct sockaddr_ll {
    u16 family;
    u16 protocol;
    int ifindex;
    u16 hatype;
    u8 pkttype;
    u8 halen;
    u8 addr[8];
};
struct pollfd { int fd; short events; short revents; };
struct mapping {
    u32 src_ip, dst_ip;
    u16 src_port, dst_port, nat_port;
    u8 proto, mac[6];
};
static struct mapping maps[MAP_SIZE];
static u8 frame[2048];
static u8 wan_mac[6] = {0x20,0xe5,0x2a,0x02,0x15,0xd0};
static u8 gw_mac[6] = {0x0a,0x3c,0x63,0x86,0x4d,0x9f};
static int wan_fd, lan_fd, next_map;
static u32 forwarded_out, forwarded_in, dropped;
static int arp_requests;

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
static void log_text(const char *s)
{
    const char *p = s;
    while (*p) ++p;
    sys3(4004, 1, (long)s, p-s);
}
static void log_number(const char *label, long value)
{
    char b[48];
    int n = 0, start, end;
    unsigned long v;
    while (*label && n < 24) b[n++] = *label++;
    if (value < 0) { b[n++] = '-'; v = (unsigned long)(-value); }
    else v = (unsigned long)value;
    start = n;
    do { b[n++] = '0' + v % 10; v /= 10; } while (v && n < 44);
    end = n - 1;
    while (start < end) {
        char c = b[start]; b[start++] = b[end]; b[end--] = c;
    }
    b[n++] = '\n';
    sys3(4004, 1, (long)b, n);
}
static void copy(u8 *to, const u8 *from, int n)
{
    while (n--) *to++ = *from++;
}
static int same(const u8 *a, const u8 *b, int n)
{
    while (n--) if (*a++ != *b++) return 0;
    return 1;
}
static u16 get16(const u8 *p) { return ((u16)p[0] << 8) | p[1]; }
static u32 get32(const u8 *p) { return ((u32)get16(p) << 16) | get16(p+2); }
static void put16(u8 *p, u16 v) { p[0] = v >> 8; p[1] = v; }
static void put32(u8 *p, u32 v) { put16(p, v >> 16); put16(p+2, v); }
static u32 csum_add(u32 sum, const u8 *p, int n)
{
    while (n > 1) { sum += get16(p); p += 2; n -= 2; }
    if (n) sum += (u16)p[0] << 8;
    return sum;
}
static u16 csum_done(u32 sum)
{
    while (sum >> 16) sum = (sum & 0xffff) + (sum >> 16);
    return (u16)~sum;
}
static void recalc(u8 *ip, int ihl, int total)
{
    u8 *l4 = ip + ihl;
    int l4len = total - ihl;
    u8 proto = ip[9];
    put16(ip+10, 0);
    put16(ip+10, csum_done(csum_add(0, ip, ihl)));
    if (proto == 6 || proto == 17) {
        int at = proto == 6 ? 16 : 6;
        u32 sum;
        put16(l4+at, 0);
        sum = csum_add(0, ip+12, 8);
        sum += proto + l4len;
        sum = csum_add(sum, l4, l4len);
        put16(l4+at, csum_done(sum));
        if (proto == 17 && get16(l4+at) == 0) put16(l4+at, 0xffff);
    } else if (proto == 1) {
        put16(l4+2, 0);
        put16(l4+2, csum_done(csum_add(0, l4, l4len)));
    }
}
static int packet_socket(int index)
{
    int fd = sys3(4183, 17, 3, ETH_P_ALL_BE);
    struct sockaddr_ll addr;
    u8 *p = (u8 *)&addr;
    int i;
    if (fd < 0) return fd;
    for (i = 0; i < (int)sizeof(addr); i++) p[i] = 0;
    addr.family = 17;
    addr.protocol = ETH_P_ALL_BE;
    addr.ifindex = index;
    long result = sys3(4169, fd, (long)&addr, sizeof(addr));
    log_number("bind result=", result);
    if (result < 0) return -1;
    return fd;
}
static void arp_reply(u8 *f, int len)
{
    u8 out[42];
    if (len < 42 || get16(f+12) != 0x0806 || get16(f+20) != 1 ||
        get32(f+38) != WAN_IP) return;
    copy(out, f+22, 6); copy(out+6, wan_mac, 6);
    put16(out+12, 0x0806); put16(out+14, 1); put16(out+16, 0x0800);
    out[18] = 6; out[19] = 4; put16(out+20, 2);
    copy(out+22, wan_mac, 6); put32(out+28, WAN_IP);
    copy(out+32, f+22, 6); copy(out+38, f+28, 4);
    if (arp_requests++ < 3) log_number("WAN ARP reply send=", sys4(4178, wan_fd, (long)out, 42, 0));
    else sys4(4178, wan_fd, (long)out, 42, 0);
}
static struct mapping *outbound_map(u32 src, u16 sport, u32 dst, u16 dport,
                                    u8 proto, const u8 *mac)
{
    int i;
    struct mapping *m;
    for (i = 0; i < MAP_SIZE; i++) {
        m = &maps[i];
        if (m->proto == proto && m->src_ip == src && m->src_port == sport &&
            m->dst_ip == dst && m->dst_port == dport) {
            copy(m->mac, mac, 6);
            return m;
        }
    }
    m = &maps[next_map];
    m->src_ip = src; m->src_port = sport;
    m->dst_ip = dst; m->dst_port = dport;
    m->proto = proto; m->nat_port = 40000 + next_map;
    copy(m->mac, mac, 6);
    next_map++;
    if (next_map == MAP_SIZE) next_map = 0;
    return m;
}
static struct mapping *inbound_map(u32 src, u16 sport, u16 nport, u8 proto)
{
    int i = (int)nport - 40000;
    struct mapping *m;
    if (i < 0 || i >= MAP_SIZE) return 0;
    m = &maps[i];
    return m->proto == proto && m->dst_ip == src && m->dst_port == sport ? m : 0;
}
static void handle_ipv4(u8 *f, int len, int from_wan)
{
    u8 *ip = f+14, *l4;
    u32 src, dst;
    u16 sport, dport;
    int ihl, total, proto;
    struct mapping *m;
    if (len < 34 || get16(f+12) != 0x0800 || (ip[0] >> 4) != 4) return;
    ihl = (ip[0] & 15)*4;
    total = get16(ip+2);
    if (ihl < 20 || total < ihl + 8 || len < 14+total ||
        (get16(ip+6) & 0x3fff) || ip[8] < 2) { dropped++; return; }
    proto = ip[9];
    if (proto != 6 && proto != 17 && proto != 1) return;
    l4 = ip + ihl;
    src = get32(ip+12); dst = get32(ip+16);
    if (proto == 1) {
        if ((from_wan && l4[0] != 0) || (!from_wan && l4[0] != 8)) return;
        sport = get16(l4+4); dport = 0;
    } else {
        sport = get16(l4); dport = get16(l4+2);
    }
    if (from_wan) {
        if (dst != WAN_IP) return;
        m = inbound_map(src, sport, dport, proto);
        if (proto == 1) m = inbound_map(src, 0, sport, proto);
        if (!m) return;
        put32(ip+16, m->src_ip);
        if (proto == 1) put16(l4+4, m->src_port);
        else put16(l4+2, m->src_port);
        copy(f, m->mac, 6); copy(f+6, wan_mac, 6);
        ip[8]--;
        recalc(ip, ihl, total);
        int result = sys4(4178, lan_fd, (long)f, 14+total, 0);
        if (forwarded_in < 4) log_number("send LAN=", result);
        if (result > 0) forwarded_in++;
    } else {
        if ((src & LAN_MASK) != LAN_NET || (dst & LAN_MASK) == LAN_NET ||
            dst == 0xffffffffu || same(f+6, wan_mac, 6)) return;
        m = outbound_map(src, sport, dst, dport, proto, f+6);
        put32(ip+12, WAN_IP);
        if (proto == 1) put16(l4+4, m->nat_port);
        else put16(l4, m->nat_port);
        copy(f, gw_mac, 6); copy(f+6, wan_mac, 6);
        ip[8]--;
        recalc(ip, ihl, total);
        int result = sys4(4178, wan_fd, (long)f, 14+total, 0);
        if (forwarded_out < 4) log_number("send WAN=", result);
        if (result > 0) forwarded_out++;
    }
}
void _start(void)
{
    struct pollfd p[2];
    int i, len, received[2] = {0, 0};
    long child = sys3(4002, 0, 0, 0);
    if (child != 0) sys3(4001, child < 0, 0, 0);
    sys3(4066, 0, 0, 0);
    wan_fd = packet_socket(WAN_INDEX);
    lan_fd = packet_socket(LAN_INDEX);
    if (wan_fd < 0 || lan_fd < 0) {
        log_text("packet socket bind failed\n");
        sys3(4001, 1, 0, 0);
    }
    log_text("RAM NAT started: eth1 192.168.157.22, br0 192.168.50.0/24\n");
    p[0].fd = wan_fd; p[0].events = 1;
    p[1].fd = lan_fd; p[1].events = 1;
    for (;;) {
        if (sys3(4188, (long)p, 2, 1000) <= 0) continue;
        for (i = 0; i < 2; i++) {
            if (!(p[i].revents & 1)) continue;
            len = sys4(4175, p[i].fd, (long)frame, sizeof(frame), 0);
            if (len < 14) continue;
            if (received[i]++ < 5) {
                log_number(i == 0 ? "WAN recv=" : "LAN recv=", len);
                log_number("ethertype=", get16(frame+12));
            }
            if (i == 0) {
                if (get16(frame+12) == 0x0806) {
                    if (len >= 42 && get16(frame+20) == 2 &&
                        get32(frame+28) == WAN_GATEWAY)
                        copy(gw_mac, frame+22, 6);
                    arp_reply(frame, len);
                } else handle_ipv4(frame, len, 1);
            } else handle_ipv4(frame, len, 0);
        }
    }
}
