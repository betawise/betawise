#include "Decoder.h"
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char**argv){if(argc!=2)return 2;FILE*f=fopen(argv[1],"rb");fseek(f,0,2);long n=ftell(f);rewind(f);unsigned char*b=malloc(n);fread(b,1,n,f);fclose(f);BibleDecoder d,e,t;BiblePoint p;unsigned long points=0;int c;
if(!BibleInit(&d,b,n))return 3;
for(unsigned ch=0;ch<1189;++ch){if(!BibleOpenChapter(&d,ch))return 4;unsigned pos=0;do{if(pos%31==0){BibleSavePoint(&d,&p);e=d;t=d;if(!BibleRestorePoint(&t,ch,&p)){printf("restore %u %u\n",ch,pos);return 5;}for(unsigned i=0;i<97;++i){int a=BibleReadByte(&e),z=BibleReadByte(&t);if(a!=z){printf("mismatch %u %u %u %d %d\n",ch,pos,i,a,z);return 6;}if(a<0)break;}++points;}c=BibleReadByte(&d);++pos;}while(c>=0);if(c!=-1)return 7;}
printf("PASS %lu compact checkpoints across all chapters; size %zu\n",points,sizeof(p));return 0;}
