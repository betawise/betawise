#include "Search.h"
#include <string.h>
static uint16_t be16(const volatile uint8_t*p){return ((uint16_t)p[0]<<8)|p[1];}
static uint32_t be24(const volatile uint8_t*p){return ((uint32_t)p[0]<<16)|((uint32_t)p[1]<<8)|p[2];}
static uint32_t be32(const volatile uint8_t*p){return ((uint32_t)p[0]<<24)|be24(p+1);}
#if BIBLE_PRUNE
extern const uint8_t BibleGrammarSummary[];
#endif
static uint16_t packed14(const uint8_t*p,unsigned id){unsigned bit=14u*id,shift=bit&7;uint32_t v=((uint32_t)p[bit/8]<<16)|((uint32_t)p[bit/8+1]<<8)|p[bit/8+2];return (v>>(10-shift))&16383;}
static uint16_t mapped(BibleSearch*s,unsigned terminal){uint16_t x=s->kind>=5?packed14(s->mapping,terminal):be16(s->mapping+2u*terminal);if(s->kind>=5){if(x==s->words)return 65534;if(x==s->words+1)return 65535;}return x;}
static uint16_t canonical(BibleSearch*s,unsigned id){return s->kind==5?be32(s->records+4u*id)>>18:be16(s->records+((s->kind==4||s->kind>=6)?2u:5u)*id);}
static uint32_t posting_offset(BibleSearch*s,unsigned id){return s->kind==5?be32(s->records+4u*id)&262143:be24(s->records+5u*id+2);}
static unsigned bit(const uint8_t*p,unsigned n){return(p[n/8]>>(n&7))&1;}
static void mark_group(uint8_t*bits,unsigned value,unsigned group,unsigned clear){unsigned c,last=(value+1)*group;
 if(last>SEARCH_CHAPTERS)last=SEARCH_CHAPTERS;
 for(c=value*group;c<last;++c){if(clear)bits[c/8]&=~(1<<(c&7));else bits[c/8]|=1<<(c&7);}
}
static int read_span(BibleSearch*s,const uint8_t*p,const uint8_t*end,uint8_t*bits,unsigned hybrid,unsigned group){
 int32_t chapter=-1;unsigned mode=0,universe=(SEARCH_CHAPTERS+group-1)/group;
 if(p>end||end>s->end)return 0;
 if(hybrid){if(p==end)return 0;mode=*p++;if(mode>5)return 0;}
 memset(bits,mode>=3?255:0,SEARCH_FILTER_BYTES);
 if(mode==5)return p==end;
 if(mode==2){unsigned v;if(end-p!=(universe+7)/8)return 0;for(v=0;v<universe;++v)if(bit(p,v))mark_group(bits,v,group,0);return 1;}
 if(mode==1||mode==4){unsigned n,l,j=0,i,lowbits;if(end-p<3)return 0;n=be16(p);l=p[2];p+=3;if(l>10||n>universe)return 0;lowbits=n*l;
  for(i=lowbits;i<(unsigned)(end-p)*8&&j<n;++i)if(bit(p,i)){unsigned k,value=0;for(k=0;k<l;++k)value|=bit(p,j*l+k)<<k;value|=(i-lowbits-j)<<l;
   if(value>=universe)return 0;mark_group(bits,value,group,mode==4);++j;}
  return j==n;
 }
 while(p<end){uint32_t delta=0;unsigned shift=0,c;do{if(p==end||shift>21)return 0;c=*p++;delta|=(uint32_t)(c&127)<<shift;shift+=7;}while(c&128);
  if(!delta||delta>universe)return 0;chapter+=delta;if(chapter>=universe)return 0;mark_group(bits,chapter,group,mode==3);
 }
 return 1;
}
static int read_postings(BibleSearch*s,unsigned id,uint8_t*bits){
 return read_span(s,s->postings+posting_offset(s,id),s->postings+posting_offset(s,id+1),bits,s->kind==5,1);
}
static unsigned letter(unsigned c){return(c>='a'&&c<='z')||(c>='A'&&c<='Z');}
static unsigned lower(unsigned c){return c>='A'&&c<='Z'?c+32:c;}
static int compare_word(BibleSearch*s,uint32_t id,const char*word,unsigned prefix){
 char spelling[64];unsigned i=0,j=0;uint16_t terminal=canonical(s,id);
 if(!BibleGetWord(&s->decoder,terminal,spelling,sizeof(spelling)))return -32768;
 if(spelling[0]==' ')++i;
 while(spelling[i]&&word[j]){int d=(int)(unsigned char)word[j]-(int)lower(spelling[i]);if(d)return d;++i;++j;}
 if(prefix&&!word[j])return 0;
 return(int)(unsigned char)word[j]-(int)lower(spelling[i]);
}
/* Prefix completions occupy a contiguous range of normalized word IDs. */
static uint32_t bound(BibleSearch*s,const char*word,unsigned upper){uint32_t lo=0,hi=s->words;
 while(lo<hi){uint32_t mid=(lo+hi)/2;int cmp=compare_word(s,mid,word,s->prefix_match);if(cmp==-32768)return UINT32_MAX;if(cmp>0||(upper&&!cmp))lo=mid+1;else hi=mid;}return lo;
}
static uint32_t bucket_key(BibleSearch*s,unsigned id){return be32(s->filter+7u*id);}
static int filter(BibleSearch*s,const char*word,uint16_t*first,uint16_t*last){
 uint32_t lo=bound(s,word,0),hi=bound(s,word,1),i;uint8_t bits[SEARCH_FILTER_BYTES],one[SEARCH_FILTER_BYTES];
 if(lo==UINT32_MAX||hi==UINT32_MAX)return 0;*first=lo;*last=hi;
 memset(bits,0,sizeof(bits));
 if(lo<hi){
  if(s->kind==4||s->kind==6)memset(bits,255,sizeof(bits));
  else if(s->kind==7){uint32_t key=0,mask=UINT32_MAX,a=0,b=s->filter_count;unsigned n=0;
   while(n<4&&word[n]){key|=(uint32_t)(uint8_t)word[n]<<(24-8*n);++n;}if(n<4)mask=UINT32_MAX<<(32-8*n);
   while(a<b){uint32_t m=(a+b)/2;if(bucket_key(s,m)<key)a=m+1;else b=m;}
   for(i=a;i<s->filter_count&&(bucket_key(s,i)&mask)==key;++i){unsigned j;uint32_t start=be24(s->filter+7*i+4),end=i+1==s->filter_count?be24(s->filter+7*(i+1)):be24(s->filter+7*(i+1)+4);
    if(!read_span(s,s->postings+start,s->postings+end,one,1,s->filter_group))return 0;
    for(j=0;j<sizeof(bits);++j)bits[j]|=one[j];
   }
  }else for(i=lo;i<hi;++i){unsigned j;if(!read_postings(s,i,one))return 0;for(j=0;j<sizeof(bits);++j)bits[j]|=one[j];}
 }
 for(i=0;i<sizeof(bits);++i)s->candidates[i]&=bits[i];return 1;
}

#if BIBLE_VERSE_BOOST
#include "VerseBoost.h"
#endif
static int start_query(BibleSearch*s,const uint8_t*bible,uint32_t size,const uint8_t*index,uint32_t index_size,const char*query,unsigned prefix_match,unsigned match_mode){
 unsigned i=0,n=0,j;
#if !BIBLE_NOINDEX
 uint32_t terms,np;
#endif
 memset(s,0,sizeof(*s));s->verse=1;s->prefix_match=!!prefix_match;s->match_mode=match_mode;
 if(match_mode>SEARCH_NEARBY)return 0;
 if(!BibleInit(&s->decoder,bible,size))return 0;
 s->stop_chapter=SEARCH_CHAPTERS;
#if !BIBLE_NOINDEX
 if(index_size<20)return 0;
#if BIBLE_CHECKPOINTS
 s->decoder.point_tracking=0;
#endif
 if(!memcmp(index,"BIBSRCH2",8))s->kind=2;
 else if(!memcmp(index,"BIBSRCH4",8))s->kind=4;
 else if(!memcmp(index,"IDXEXP02",8))s->kind=5;
 else if(!memcmp(index,"PFXLEX01",8))s->kind=6;
 else return 0;
 if(s->kind==6){uint32_t mapbytes=be32(index+16);s->words=be16(index+8);terms=be16(index+10);if(be32(index+12)||mapbytes!=(14u*terms+7)/8)return 0;np=0;}
 else if(s->kind==5){s->words=be16(index+8);terms=be16(index+10);if(be32(index+12)!=1)return 0;np=be32(index+16);}
 else{s->words=be32(index+8);terms=be32(index+12);np=be32(index+16);}
 if(s->words>=65534||terms!=s->decoder.terminals)return 0;
 s->index=index;s->records=index+20;s->end=index+index_size;s->filter_group=1;
 s->mapping=s->records+((s->kind==4||s->kind==6)?2u*s->words:s->kind==5?4u*(s->words+1):5u*(s->words+1));
 s->postings=s->mapping+(s->kind>=5?(14u*terms+7)/8:2u*terms);
 if(s->postings>s->end)return 0;
 if(s->kind==6&&s->postings<s->end){const uint8_t*f=s->postings;uint32_t bytes;
  if(s->end-f<20||memcmp(f,"PFXGRP01",8)||be16(f+8)!=4)return 0;
  s->filter_group=be16(f+10);s->filter_count=be16(f+12);bytes=be32(f+16);
  if(!s->filter_group||s->filter_group>SEARCH_CHAPTERS||be16(f+14)!=(SEARCH_CHAPTERS+s->filter_group-1)/s->filter_group)return 0;
  s->filter=f+20;s->postings=s->filter+7u*s->filter_count+3;
  if(s->postings>s->end||s->end-s->postings!=bytes)return 0;s->kind=7;
 }else if(s->kind!=6&&np!=(uint32_t)(s->end-s->postings))return 0;

#endif
 memset(s->candidates,255,sizeof(s->candidates));
 while(query[i]){
  while(query[i]&&!letter(query[i])){if(query[i]=='*')return 0;++i;}
  if(!query[i])break;
  if(s->phrase_length==8)return 0;
  s->offsets[s->phrase_length++]=n;
  while(letter(query[i])||(query[i]=='\''&&n>s->offsets[s->phrase_length-1]&&letter(query[i+1]))){if(n>=sizeof(s->query)-2)return 0;s->query[n++]=lower(query[i++]);}
  if(prefix_match==1)s->query_prefixes|=1u<<(s->phrase_length-1);
  if(query[i]=='*'){if(prefix_match!=2)return 0;s->query_prefixes|=1u<<(s->phrase_length-1);++i;if(letter(query[i])||query[i]=='*'||query[i]=='\'')return 0;}
  s->query[n++]=0;
 }
 if(!s->phrase_length)return 0;

#if !BIBLE_NOINDEX
 for(j=0;j<s->phrase_length;++j){s->prefix_match=(s->query_prefixes>>j)&1;if(!filter(s,s->query+s->offsets[j],s->query_ids+j,s->query_ends+j))return 0;}
#if BIBLE_PRUNE
 for(j=0;j<s->decoder.rule_count;++j){const uint8_t*r=s->decoder.grammar+4u*j;unsigned a=be16(r),b=be16(r+2),nt=s->decoder.terminals;
  unsigned ca=a>=nt?bit(s->contains,a-nt):0,cb=b>=nt?bit(s->contains,b-nt):0,k,limit=match_mode==SEARCH_PHRASE?1:s->phrase_length;
  unsigned wa=a<nt?mapped(s,a):65535,wb=b<nt?mapped(s,b):65535;
  for(k=0;k<limit;++k){ca|=wa>=s->query_ids[k]&&wa<s->query_ends[k];cb|=wb>=s->query_ids[k]&&wb<s->query_ends[k];}
  if(ca||cb)s->contains[j/8]|=1<<(j&7);
 }
#endif
#if BIBLE_VERSE_BOOST
 if(match_mode!=SEARCH_NEARBY&&!verse_query(s))return 0;
#endif
#else
 (void)index;(void)index_size;
 s->pending_byte=-3;
 /* Per-term character KMP tables. Word-start checks retain prefix semantics;
  * Shift-And combines accepted word prefixes without unsafe KMP overlap links. */
 for(j=0;j<s->phrase_length;++j){unsigned k,f=0,off=s->offsets[j];const char*q=s->query+off;
  for(k=1;q[k];++k){while(f&&q[k]!=q[f])f=s->char_failure[off+f-1];if(q[k]==q[f])++f;s->char_failure[off+k]=f;}
 }
#endif
 return 1;
}
int SearchStartMode(BibleSearch*s,const uint8_t*b,uint32_t n,const uint8_t*i,uint32_t z,const char*q,unsigned prefix){return start_query(s,b,n,i,z,q,!!prefix,SEARCH_PHRASE);}
int SearchBegin(BibleSearch*s,const uint8_t*b,uint32_t n,const uint8_t*i,uint32_t z,const char*q,unsigned mode){return start_query(s,b,n,i,z,q,2,mode);}
int SearchStart(BibleSearch*s,const uint8_t*b,uint32_t n,const uint8_t*i,uint32_t z,const char*q){return SearchBegin(s,b,n,i,z,q,SEARCH_SAME_VERSE);}
#include "SearchMatch.h"
#if BIBLE_NOINDEX
#include "NoIndex.h"
#else
static int step_forward(BibleSearch*s,unsigned budget){
 if(s->restore_verse){s->verse=s->resume_verse;s->restore_verse=0;}
 if(s->done)return -1;
 while(budget--){int terminal;uint16_t word;
  if(!s->open){
#if BIBLE_VERSE_BOOST
   if(s->verse_active){int r=verse_open_next(s);if(r<0){s->done=1;return -1;}if(!r)return -2;}
   else
#endif
   {while(s->chapter<s->stop_chapter&&!(s->candidates[s->chapter/8]&(1<<(s->chapter%8))))++s->chapter;
   if(s->chapter>=s->stop_chapter){s->done=1;return -1;}
   if(!BibleOpenChapter(&s->decoder,s->chapter))return -2;
   s->open=1;s->verse=1;s->matched=s->word_count=0;s->position=s->rank=s->suppressed=0;memset(s->assigned,0,sizeof(s->assigned));}
  }
#if BIBLE_PRUNE
  terminal=BibleReadNode(&s->decoder);
  if(terminal>=s->decoder.terminals){unsigned rule=terminal-s->decoder.terminals;
   if((s->match_mode==SEARCH_PHRASE?!s->matched:1)&&!bit(s->contains,rule)){const uint8_t*r=BibleGrammarSummary+3u*rule;s->position+=r[0];s->verse+=r[1];s->word_count=r[1]?r[2]:s->word_count+r[0];
    if(r[1]&&s->match_mode==SEARCH_SAME_VERSE)match_reset(s);
#if BIBLE_VERSE_BOOST
    if(s->verse_active&&r[1])s->open=0;
#endif
    continue;}
   if(!BiblePushRule(&s->decoder,terminal))return -2;
   continue;
  }
#else
  terminal=BibleReadTerminal(&s->decoder);
#endif
  if(terminal<-1)return -2;
  if(terminal==-1){s->open=0;++s->chapter;continue;}
  word=mapped(s,terminal);
  if(word==65534){++s->verse;s->word_count=s->matched=0;
   if(s->match_mode==SEARCH_SAME_VERSE)match_reset(s);
#if BIBLE_VERSE_BOOST
   if(s->verse_active)s->open=0;
#endif
   continue;}
  if(word==65535)continue;
  {unsigned i,mask=0;for(i=0;i<s->phrase_length;++i)if(word>=s->query_ids[i]&&word<s->query_ends[i])mask|=1u<<i;
   if(match_word(s,mask))return 1;}
 }
 return 0;
}

#endif
static int position_compare(unsigned c,unsigned v,unsigned w,const uint16_t*p){
 if(c!=p[0])return c<p[0]?-1:1;
 if(v!=p[1])return v<p[1]?-1:1;
 return w<p[2]?-1:w>p[2];
}
void SearchFrom(BibleSearch*s,unsigned chapter,unsigned verse,unsigned word,int direction,unsigned inclusive){
 /* Continuing forward from the just-returned hit can reuse the live decoder. */
 unsigned reuse=direction>0&&s->navigating&&s->direction>0&&!s->done&&s->chapter==chapter&&s->verse==verse&&s->hit_word==word&&!inclusive;
 s->origin[0]=chapter;s->origin[1]=verse;s->origin[2]=word;s->direction=direction<0?-1:1;s->inclusive=!!inclusive;s->navigating=1;s->previous_valid=0;s->stop_chapter=s->direction<0?chapter+1:SEARCH_CHAPTERS;s->nav_chapter=chapter;
#if BIBLE_VERSE_BOOST
 s->verse_active=0;
#endif
 if(!reuse){s->chapter=chapter;s->open=s->done=s->restore_verse=0;
#if BIBLE_NOINDEX
 s->token_open=s->quote=0;s->pending_byte=-3;
#endif
 }
}
int SearchStep(BibleSearch*s,unsigned budget){
 if(!s->navigating)return step_forward(s,budget);
 if(s->done)return -1;
 while(budget--){int r=step_forward(s,1),cmp;
  if(r==-2)return r;
  if(r==1){cmp=position_compare(s->chapter,s->verse,s->hit_word,s->origin);
   if(s->direction>0){if(cmp>0||(!cmp&&s->inclusive))return 1;}
   else if(cmp<0||(!cmp&&s->inclusive)){s->previous[0]=s->chapter;s->previous[1]=s->verse;s->previous[2]=s->hit_word;s->previous_valid=1;}
   else r=-1;
  }
  if(r==-1){
   if(s->direction>0)return -1;
   if(s->previous_valid){s->chapter=s->previous[0];s->verse=s->previous[1];s->hit_word=s->previous[2];s->done=1;return 1;}
   if(!s->nav_chapter){s->done=1;return -1;}
   --s->nav_chapter;s->chapter=s->nav_chapter;s->stop_chapter=s->chapter+1;s->open=s->done=s->restore_verse=0;
#if BIBLE_NOINDEX
   s->token_open=s->quote=0;s->pending_byte=-3;
#endif
  }
 }
 return 0;
}
