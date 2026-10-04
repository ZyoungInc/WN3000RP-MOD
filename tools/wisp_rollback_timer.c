/* Detached, RAM-only safety timer. Runs /tmp/wisp-restore.sh after 30 minutes. */
typedef unsigned int u32;
struct timespec32 { long seconds, nanoseconds; };
static long sys3(long nr, long x, long y, long z)
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
    static const char sh[] = "/bin/sh";
    static const char script[] = "/tmp/wisp-restore.sh";
    static const char done[] = "/tmp/wisp-done";
    static const char *const argv[] = {sh, script, 0};
    static const char *const envp[] = {"PATH=/bin:/sbin:/usr/bin:/usr/sbin", 0};
    struct timespec32 delay = {1800, 0};
    long pid = sys3(4002, 0, 0, 0);
    if (pid != 0) sys3(4001, pid < 0, 0, 0);
    sys3(4066, 0, 0, 0);
    sys3(4166, (long)&delay, 0, 0);
    if (sys3(4005, (long)done, 0, 0) < 0)
        sys3(4011, (long)sh, (long)argv, (long)envp);
    sys3(4001, 0, 0, 0);
    __builtin_unreachable();
}
