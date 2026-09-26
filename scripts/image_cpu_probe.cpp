// Nexo7, MIT. This baseline executable checks CPU AND OS AVX state support.
#include <cstdio>
#if defined(_MSC_VER)
#include <intrin.h>
static void cpuid(int leaf, int subleaf, int out[4]) { __cpuidex(out, leaf, subleaf); }
static unsigned long long xcr0() { return _xgetbv(0); }
#else
#include <cpuid.h>
static void cpuid(int leaf, int subleaf, int out[4]) {
    unsigned a,b,c,d; __cpuid_count(leaf, subleaf, a,b,c,d);
    out[0]=a;out[1]=b;out[2]=c;out[3]=d;
}
static unsigned long long xcr0() {
    unsigned a,d; __asm__ volatile("xgetbv" : "=a"(a), "=d"(d) : "c"(0));
    return (static_cast<unsigned long long>(d)<<32)|a;
}
#endif
int main() {
    int r[4];cpuid(0,0,r);const int maximum=r[0];
    bool fast=false;
    if(maximum>=7) {
        cpuid(1,0,r);
        const unsigned required=(1u<<27)|(1u<<28)|(1u<<12)|(1u<<29)|(1u<<0)|(1u<<9)|(1u<<19)|(1u<<20);
        if((static_cast<unsigned>(r[2])&required)==required && (xcr0()&6)==6) {
            cpuid(7,0,r);fast=(static_cast<unsigned>(r[1])&(1u<<5))!=0;
        }
    }
    std::puts(fast?"avx2":"baseline");return 0;
}
