/* Temporary RAM-only capability probe for Linux/MIPS o32. */
static long call3(long nr, long x, long y, long z)
{
    register long v0 __asm__("$2") = nr;
    register long a0 __asm__("$4") = x;
    register long a1 __asm__("$5") = y;
    register long a2 __asm__("$6") = z;
    register long a3 __asm__("$7");
    __asm__ volatile("syscall" : "+r"(v0), "=r"(a3) : "r"(a0), "r"(a1), "r"(a2) : "memory");
    return a3 ? -v0 : v0;
}

void _start(void)
{
    long fd = call3(4183, 17, 3, 0x0300); /* socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL)) */
    static const char ok[] = "AF_PACKET works\n";
    static const char fail[] = "AF_PACKET failed\n";
    if (fd >= 0) {
        call3(4004, 1, (long)ok, sizeof(ok)-1);
        call3(4006, fd, 0, 0);
        call3(4001, 0, 0, 0);
    } else {
        call3(4004, 1, (long)fail, sizeof(fail)-1);
        call3(4001, 1, 0, 0);
    }
    __builtin_unreachable();
}
