/* Experimental selective verse acceleration; normal chapter index is retained. */
extern const uint8_t BibleVerseBoost[],BibleVerseBoostEnd[];
static int verse_query(BibleSearch*s){
 const uint8_t*b=BibleVerseBoost,*offsets,*posts;unsigned lo,hi,total,nc,id;uint32_t na,np;
 if(BibleVerseBoostEnd-b<24||memcmp(b,"VBOOST03",8))return 0;
 lo=be16(b+8);hi=be16(b+10);total=be16(b+12);nc=be16(b+14);na=be32(b+16);np=be32(b+20);
 if(hi<lo||total>sizeof(s->verse_candidates)*8||nc!=SEARCH_CHAPTERS)return 0;
 s->verse_records=b+24;offsets=s->verse_records+2u*(nc+1);s->verse_anchors=offsets+3u*(hi-lo+1);posts=s->verse_anchors+na;
 if(posts+np!=BibleVerseBoostEnd||be16(s->verse_records+2u*nc)!=total||na%6)return 0;
 if(s->query_ids[0]<lo||s->query_ends[0]>hi||s->query_ids[0]==s->query_ends[0])return 1;
 for(id=s->query_ids[0];id<s->query_ends[0];++id){const uint8_t*p=posts+be24(offsets+3u*(id-lo)),*end=posts+be24(offsets+3u*(id-lo+1));int32_t value=-1;
  if(p>end||end>posts+np)return 0;
  while(p<end){uint32_t n=0;unsigned shift=0,c;do{if(p==end||shift>28)return 0;c=*p++;n|=(uint32_t)(c&127)<<shift;shift+=7;}while(c&128);
   if(!n||n>total)return 0;value+=n;if(value>=total)return 0;s->verse_candidates[value/8]|=1<<(value&7);
  }
 }
 s->verse_total=total;s->verse_active=1;s->verse_cursor=s->verse_anchors;return 1;
}
static int verse_open_next(BibleSearch*s){unsigned target,v;const uint8_t*end= s->verse_anchors+be32(BibleVerseBoost+16);
 for(;;){while(s->verse_next<s->verse_total&&!bit(s->verse_candidates,s->verse_next))++s->verse_next;
  if(s->verse_next==s->verse_total)return -1;target=s->verse_next++;
  while(s->chapter+1<SEARCH_CHAPTERS&&target>=be16(s->verse_records+2u*(s->chapter+1)))++s->chapter;
  if(bit(s->candidates,s->chapter))break;
 }
 v=target-be16(s->verse_records+2u*s->chapter)+1;
 while(s->verse_cursor<end&&be16(s->verse_cursor)<target)s->verse_cursor+=6;
 if(s->verse_cursor>=end||be16(s->verse_cursor)!=target)return 0;
 if(!BibleOpenVerse(&s->decoder,s->chapter,be24(s->verse_cursor+2),s->verse_cursor[5]))return 0;s->verse_cursor+=6;
 s->open=1;s->verse=v;s->matched=s->word_count=0;return 1;
}
