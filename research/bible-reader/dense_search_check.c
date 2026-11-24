/* Host-only correctness oracle for dense-stream KMP; not Neo applet code.
 * Auxiliary rank-normalization and chapter-offset files are test fixtures.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
static unsigned char *load(const char *p,size_t *size){FILE*f=fopen(p,"rb");if(!f)exit(2);fseek(f,0,2);*size=ftell(f);rewind(f);unsigned char*b=malloc(*size+1);if(fread(b,1,*size,f)!=*size)exit(2);fclose(f);return b;}
static unsigned be16(unsigned char*p){return p[0]*256u+p[1];}
static unsigned be32(unsigned char*p){return be16(p)*65536u+be16(p+2);}
int main(int argc,char**argv){
 if(argc<6)return 2;
 size_t nb,ni,nm;unsigned char*b=load(argv[1],&nb),*ix=load(argv[2],&ni),*map=load(argv[3],&nm);
 unsigned s=atoi(argv[4]),c=256-s,q[8],prefix[8]={0},n=argc-5;if(n>8||!s||s>255)return 2;
 for(unsigned i=0;i<n;++i){q[i]=atoi(argv[i+5]);if(i){unsigned k=prefix[i-1];while(k&&q[i]!=q[k])k=prefix[k-1];if(q[i]==q[k])++k;prefix[i]=k;}}
 for(unsigned ch=0;ch+1<ni/4;++ch){
  unsigned start=be32(ix+4*ch),end=be32(ix+4*(ch+1)),rank=0,base=0,capacity=s,matched=0,verse=1,word=0;if(start>end||end>nb)return 3;
  for(unsigned j=start;j<end;++j){unsigned x=b[j];if(x<c){rank=rank*c+x;base+=capacity;capacity*=c;continue;}
   unsigned r=base+rank*s+x-c;rank=base=0;capacity=s;if(2*r+1>=nm)return 3;unsigned id=be16(map+2*r);
   if(id==65534){++verse;matched=word=0;continue;}if(id==65535)continue;++word;
   while(matched&&id!=q[matched])matched=prefix[matched-1];
   if(id==q[matched])++matched;
   if(matched==n){printf("%u %u %u\n",ch,verse,word-n);matched=prefix[matched-1];}
  }
  if(rank||base)return 3;
 }
 return 0;
}
