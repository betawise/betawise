// Host experiment: deterministic static backoff model + 32-bit arithmetic code.
// Tables are serialized in big endian and never depend on host floating point.
// This is a verifier/measurement backend, not a hardened on-device parser.
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <vector>
using Bytes = std::vector<uint8_t>;
using Seq = std::vector<uint16_t>;
static void check(bool b) { if (!b) throw std::runtime_error("validation failed"); }
static Bytes read(const char* p) { std::ifstream f(p, std::ios::binary); check(bool(f)); return Bytes(std::istreambuf_iterator<char>(f), {}); }
static void write(const char* p, const Bytes& b) { std::ofstream f(p, std::ios::binary); f.write((const char*)b.data(), b.size()); check(bool(f)); }
static uint32_t u32(const Bytes& b, size_t p) { check(p + 4 <= b.size()); return uint32_t(b[p])<<24 | uint32_t(b[p+1])<<16 | uint32_t(b[p+2])<<8 | b[p+3]; }
static uint16_t u16(const Bytes& b, size_t p) { check(p + 2 <= b.size()); return uint16_t(b[p])<<8 | b[p+1]; }
static void put32(Bytes& b, uint32_t x) { for (int i=24;i>=0;i-=8) b.push_back(x>>i); }
static uint32_t hash(const Seq& s) { uint32_t h=2166136261u; for (auto x:s) { h=(h^(x>>8))*16777619u; h=(h^(x&255))*16777619u; } return h; }
struct BitsOut {
    Bytes bytes; unsigned n=0; uint8_t byte=0;
    void bit(unsigned v) { byte=(byte<<1)|v; if (++n==8) {bytes.push_back(byte);byte=n=0;} }
    Bytes finish() { if(n) bytes.push_back(byte<<(8-n)); return bytes; }
};
struct BitsIn {
    const Bytes& b; size_t p=0;
    unsigned bit() { size_t q=p++; return q/8 < b.size() ? (b[q/8]>>(7-q%8))&1 : 0; }
};
constexpr uint32_t HALF=0x80000000u, Q1=0x40000000u, Q3=0xc0000000u;
struct Encoder {
    uint32_t low=0, high=0xffffffffu; size_t pending=0; BitsOut out;
    void emit(unsigned b) { out.bit(b); while(pending) {out.bit(b^1); --pending;} }
    void symbol(uint32_t a,uint32_t b,uint32_t total) {
        check(a<b && b<=total);
        uint64_t range=uint64_t(high)-low+1;
        high=low+range*b/total-1; low=low+range*a/total;
        for (;;) {
            if (high<HALF) emit(0);
            else if(low>=HALF) {emit(1);low-=HALF;high-=HALF;}
            else if(low>=Q1 && high<Q3) {++pending;low-=Q1;high-=Q1;}
            else break;
            low<<=1; high=(high<<1)|1;
        }
    }
    Bytes finish() {++pending;emit(low<Q1?0:1);return out.finish();}
};
struct Decoder {
    uint32_t low=0,high=0xffffffffu,value=0; BitsIn in;
    explicit Decoder(const Bytes& b):in{b} { for(int i=0;i<32;++i) value=(value<<1)|in.bit(); }
    uint32_t target(uint32_t total) const {return ((uint64_t(value)-low+1)*total-1)/(uint64_t(high)-low+1);}
    void symbol(uint32_t a,uint32_t b,uint32_t total) {
        check(a<b && b<=total);
        uint64_t range=uint64_t(high)-low+1;
        high=low+range*b/total-1; low=low+range*a/total;
        for(;;) {
            if(high<HALF) {}
            else if(low>=HALF) {low-=HALF;high-=HALF;value-=HALF;}
            else if(low>=Q1 && high<Q3) {low-=Q1;high-=Q1;value-=Q1;}
            else break;
            low<<=1;high=(high<<1)|1;value=(value<<1)|in.bit();
        }
    }
};
struct Context { Seq symbols; std::vector<uint16_t> ends; uint32_t total() const {return ends.back();} };
struct Exclusion {
    const Context& c; const std::vector<uint32_t>& base;
    std::vector<uint16_t> removed16;std::vector<uint32_t> removed32;bool wide;
    Exclusion(const Context& c,const std::vector<uint32_t>& b):c(c),base(b),wide(b.back()>65535) {
        // Narrow CDF totals cannot exceed 65535, so neither can an excluded
        // prefix sum. Reserve exactly once: 512 followers need 1024 bytes.
        if(wide) removed32.reserve(c.symbols.size()-1);else removed16.reserve(c.symbols.size()-1);
        uint32_t total=0;
        for(size_t i=0;i+1<c.symbols.size();++i) {
            auto s=c.symbols[i];total+=base[s]-(s?base[s-1]:0);
            if(wide) removed32.push_back(total);else removed16.push_back(total);
        }
    }
    uint32_t removed(unsigned i) const {return wide?removed32[i]:removed16[i];}
    uint32_t end(unsigned s) const {
        auto j=std::upper_bound(c.symbols.begin(),c.symbols.end()-1,s)-c.symbols.begin();
        return base[s]-(j?removed(j-1):0);
    }
    uint32_t total() const {return base.back()-(c.symbols.size()>1?removed(c.symbols.size()-2):0);}
};
struct Model {
    unsigned alphabet,order; bool exclusion; std::vector<uint32_t> base; std::map<uint32_t,Context> contexts;
    explicit Model(const Bytes& b) {
        alphabet=u32(b,0);auto flags=u32(b,4);order=flags&255;unsigned count=u32(b,8);bool wide=flags&256;exclusion=flags&512;
        check(!exclusion || order<=1);
        check(alphabet<65535 && order<=3);
        size_t p=12;
        for(unsigned i=0;i<alphabet;++i,p+=wide?4:2) {base.push_back(wide?u32(b,p):u16(b,p));check(base.back()>=(i?base[i-1]:0));}
        check(base.back()>0);
        size_t entries=p+12*count;
        for(unsigned i=0;i<count;++i,p+=12) {
            auto key=u32(b,p); auto offset=u32(b,p+4);auto n=u16(b,p+8);auto total=u16(b,p+10);
            Context c;
            for(unsigned j=0;j<n;++j) {
                c.symbols.push_back(u16(b,entries+offset+4*j));c.ends.push_back(u16(b,entries+offset+4*j+2));
                check(c.ends.back()>(j?c.ends[j-1]:0));check(c.symbols.back()<=alphabet);
                if(j) check(c.symbols[j-1]<c.symbols[j]);
            }
            check(n && c.ends.back()==total);contexts.emplace(key,std::move(c));
        }
    }
    std::vector<uint32_t> keys(const Seq& history) const {
        std::vector<uint32_t> keys;
        for(unsigned n=1;n<=order && n<=history.size();++n) {
            uint64_t key=1;
            for(size_t i=history.size()-n;i<history.size();++i) key=key*(alphabet+1)+history[i]+1;
            check(key<=0xffffffffu);keys.push_back(key);
        }
        std::reverse(keys.begin(),keys.end());return keys;
    }
    void encode(Encoder& e,const Seq& history,uint16_t s) const {
        for(auto key:keys(history)) {
            auto it=contexts.find(key);if(it==contexts.end()) continue;
            const auto& c=it->second;
            auto jt=std::lower_bound(c.symbols.begin(),c.symbols.end(),s);
            bool found=jt!=c.symbols.end() && *jt==s;
            unsigned j=found ? jt-c.symbols.begin():c.symbols.size()-1;
            check(found || c.symbols[j]==alphabet);
            e.symbol(j?c.ends[j-1]:0,c.ends[j],c.total());if(found) return;
            if(exclusion) {Exclusion x(c,base);e.symbol(s?x.end(s-1):0,x.end(s),x.total());return;}
        }
        e.symbol(s?base[s-1]:0,base[s],base.back());
    }
    uint16_t decode(Decoder& d,const Seq& history) const {
        for(auto key:keys(history)) {
            auto it=contexts.find(key);if(it==contexts.end()) continue;
            const auto& c=it->second;auto target=d.target(c.total());
            unsigned j=std::upper_bound(c.ends.begin(),c.ends.end(),target)-c.ends.begin();
            check(j<c.symbols.size());d.symbol(j?c.ends[j-1]:0,c.ends[j],c.total());
            if(c.symbols[j]!=alphabet) return c.symbols[j];
            if(exclusion) {
                Exclusion x(c,base);auto t=d.target(x.total());unsigned a=0,b=alphabet;
                while(a<b) {unsigned mid=(a+b)/2;if(x.end(mid)<=t) a=mid+1;else b=mid;}
                check(a<alphabet);d.symbol(a?x.end(a-1):0,x.end(a),x.total());return a;
            }
        }
        auto target=d.target(base.back());unsigned s=std::upper_bound(base.begin(),base.end(),target)-base.begin();
        check(s<alphabet);d.symbol(s?base[s-1]:0,base[s],base.back());return s;
    }
};
static void remember(Seq& h,uint16_t s,unsigned order) {if(!order) return;h.push_back(s);if(h.size()>order) h.erase(h.begin());}
static std::vector<Seq> decode_archive(const Bytes& archive) {
    check(archive.size()>=16 && Bytes(archive.begin(),archive.begin()+8)==Bytes({'C','T','X','A','R','0','0','1'}));
    unsigned m=u32(archive,8),count=u32(archive,12);check(16ull+m+16ull*count<=archive.size());
    Model stored(Bytes(archive.begin()+16,archive.begin()+16+m));size_t ix=16+m,ps=ix+16*count;
    std::vector<Seq> decoded(count);
    for(int i=int(count)-1;i>=0;--i) {
        auto offset=u32(archive,ix+16*i),size=u32(archive,ix+16*i+4),n=u32(archive,ix+16*i+8);
        check(ps+offset+size<=archive.size());Bytes b(archive.begin()+ps+offset,archive.begin()+ps+offset+size);Decoder d(b);Seq h,seq;
        for(unsigned j=0;j<n;++j) {auto s=stored.decode(d,h);seq.push_back(s);remember(h,s,stored.order);}
        check(hash(seq)==u32(archive,ix+16*i+12));decoded[i]=std::move(seq);
    }
    return decoded;
}
static Bytes serialize_sequences(const std::vector<Seq>& decoded) {
    Bytes output;put32(output,decoded.size());for(auto& seq:decoded) {put32(output,seq.size());for(auto s:seq) {output.push_back(s>>8);output.push_back(s&255);}}return output;
}
int main(int argc,char**argv) {
    try {
        if(argc==4 && std::string(argv[1])=="--decode") {write(argv[3],serialize_sequences(decode_archive(read(argv[2]))));return 0;}
        check(argc==5);Bytes input=read(argv[1]), model_bytes=read(argv[2]);Model model(model_bytes);
        unsigned count=u32(input,0);size_t p=4;std::vector<Seq> chapters;
        for(unsigned i=0;i<count;++i) {unsigned n=u32(input,p);p+=4;Seq s;for(unsigned j=0;j<n;++j,p+=2) {s.push_back(u16(input,p));check(s.back()<model.alphabet);}chapters.push_back(std::move(s));}
        check(p==input.size());Bytes index,payload;
        for(const auto& seq:chapters) {
            Encoder e;Seq h;for(auto s:seq) {model.encode(e,h,s);remember(h,s,model.order);}auto b=e.finish();
            put32(index,payload.size());put32(index,b.size());put32(index,seq.size());put32(index,hash(seq));payload.insert(payload.end(),b.begin(),b.end());
        }
        Bytes archive={'C','T','X','A','R','0','0','1'};put32(archive,model_bytes.size());put32(archive,count);
        archive.insert(archive.end(),model_bytes.begin(),model_bytes.end());archive.insert(archive.end(),index.begin(),index.end());archive.insert(archive.end(),payload.begin(),payload.end());write(argv[3],archive);
        // Reopen the archive and seek every chapter independently in reverse.
        archive=read(argv[3]);auto decoded=decode_archive(archive);check(decoded==chapters);write(argv[4],serialize_sequences(decoded));
        unsigned m=u32(archive,8);
        std::cout << "{\"bytes\":" << archive.size() << ",\"model_bytes\":" << m << ",\"payload_bytes\":" << payload.size() << ",\"verified_chapters\":" << count << "}\n";
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
