#include "SearchBloom.h"
#include <string.h>
static uint16_t be16(const volatile uint8_t*p){return ((uint16_t)p[0]<<8)|p[1];}
static uint32_t be24(const volatile uint8_t*p){return ((uint32_t)p[0]<<16)|((uint32_t)p[1]<<8)|p[2];}
static uint32_t be32(const volatile uint8_t*p){return ((uint32_t)p[0]<<24)|be24(p+1);}
static unsigned letter(unsigned c){return(c>='a'&&c<='z')||(c>='A'&&c<='Z');}
static unsigned lower(unsigned c){return c>='A'&&c<='Z'?c+32:c;}
static int compare_word(BibleBloomSearch*s,uint32_t id,const char*word){
 char spelling[64];unsigned i=0,j=0;uint16_t terminal=be16(s->records+2*id);
 if(!BibleGetWord(&s->decoder,terminal,spelling,sizeof(spelling)))return -32768;
 if(spelling[0]==' ')++i;
 while(spelling[i]&&word[j]){int d=(int)(unsigned char)word[j]-(int)lower(spelling[i]);if(d)return d;++i;++j;}
 return(int)(unsigned char)word[j]-(int)lower(spelling[i]);
}
static int lookup(BibleBloomSearch*s,const char*word,uint16_t*id){
 uint32_t lo=0,hi=s->words;*id=65535;
 while(lo<hi){uint32_t mid=(lo+hi)/2;int cmp=compare_word(s,mid,word);if(cmp==-32768)return 0;if(cmp>0)lo=mid+1;else hi=mid;}
 if(lo<s->words&&!compare_word(s,lo,word))*id=lo;
 return 1;
}

int BloomSearchStart(BibleBloomSearch*s,const uint8_t*bible,uint32_t size,const uint8_t*index,uint32_t index_size,const char*query){
 unsigned i=0,n=0,j,k;uint32_t terms,nv;memset(s,0,sizeof(*s));s->verse=1;
 if(index_size<20||memcmp(index,"BIBSRCH3",8)||!BibleInit(&s->decoder,bible,size))return 0;
 s->words=be32(index+8);terms=be32(index+12);nv=be32(index+16);
 if(s->words>=65534||terms!=s->decoder.terminals||!nv||nv>=65536||20+2*s->words+2*terms+2380+12*nv!=index_size)return 0;
 s->index=index;s->records=index+20;s->mapping=s->records+2*s->words;s->chapter_offsets=s->mapping+2*terms;s->verses=s->chapter_offsets+2380;s->end=index+index_size;s->verse_total=nv;
 if(be16(s->chapter_offsets)||be16(s->chapter_offsets+2*1189)!=nv)return 0;
 while(query[i]){
  while(query[i]&&!letter(query[i]))++i;
  if(!query[i])break;
  if(s->phrase_length==8)return 0;
  s->offsets[s->phrase_length++]=n;
  while(letter(query[i])||(query[i]=='\''&&n>s->offsets[s->phrase_length-1]&&letter(query[i+1]))){if(n>=sizeof(s->query)-2)return 0;s->query[n++]=lower(query[i++]);}
  s->query[n++]=0;
 }
 if(!s->phrase_length)return 0;
 for(j=0;j<s->phrase_length;++j){if(!lookup(s,s->query+s->offsets[j],s->query_ids+j))return 0;
  if(s->query_ids[j]==65535)s->done=1;else{unsigned bit=(s->query_ids[j]^(s->query_ids[j]>>6))&63;s->mask[bit>>5]|=1u<<(bit&31);}
  if(j){k=s->prefix[j-1];while(k&&s->query_ids[j]!=s->query_ids[k])k=s->prefix[k-1];if(s->query_ids[j]==s->query_ids[k])++k;s->prefix[j]=k;}}
 return 1;
}
int BloomSearchStep(BibleBloomSearch*s,unsigned budget){
 if(s->done)return -1;
 while(budget--){int terminal;uint16_t word;
  if(!s->open){const uint8_t*r;
   if(s->verse_index==s->verse_total){s->done=1;return -1;}
   r=s->verses+12u*s->verse_index;
   if((be32(r)&s->mask[0])!=s->mask[0]||(be32(r+4)&s->mask[1])!=s->mask[1]){++s->verse_index;continue;}
   while(s->chapter<1188&&s->verse_index>=be16(s->chapter_offsets+2u*(s->chapter+1)))++s->chapter;
   s->verse=s->verse_index-be16(s->chapter_offsets+2u*s->chapter)+1;
   if(!BibleOpenVerse(&s->decoder,s->chapter,be24(r+8),r[11]))return -2;
   s->open=1;s->matched=s->word_count=0;
  }
  terminal=BibleReadTerminal(&s->decoder);if(terminal<-1)return -2;
  if(terminal==-1)return -2;
  word=be16(s->mapping+2u*terminal);
  if(word==65534){s->open=0;++s->verse_index;continue;}
  if(word==65535)continue;
  ++s->word_count;
  while(s->matched&&word!=s->query_ids[s->matched])s->matched=s->prefix[s->matched-1];
  if(word==s->query_ids[s->matched])++s->matched;
  if(s->matched==s->phrase_length){s->hit_word=s->word_count-s->phrase_length;s->matched=s->prefix[s->matched-1];return 1;}
 }
 return 0;
}
