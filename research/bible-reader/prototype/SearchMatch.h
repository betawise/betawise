/* Shared bounded matcher. An occurrence may satisfy only one query term.
 * Unordered modes keep a maximum-cardinality, newest occurrence basis of the
 * term/occurrence bipartite graph (at most eight slots). On dependent insertion,
 * replace the oldest element of its alternating-path circuit. This preserves
 * the newest possible cover even for nested wildcard sets and repeated terms. */
static void match_reset(BibleSearch*s){s->rank=s->suppressed=0;memset(s->assigned,0,sizeof(s->assigned));}
static int match_augment(BibleSearch*s,unsigned mask,unsigned verse,unsigned word,uint32_t pos,unsigned*seen){unsigned i;
 for(i=0;i<s->phrase_length;++i)if((mask&(1u<<i))&&!(*seen&(1u<<i))){*seen|=1u<<i;
  if(!s->assigned[i].mask||match_augment(s,s->assigned[i].mask,s->assigned[i].verse,s->assigned[i].word,s->assigned[i].position,seen)){
   s->assigned[i].mask=mask;s->assigned[i].verse=verse;s->assigned[i].word=word;s->assigned[i].position=pos;return 1;
  }
 }
 return 0;
}
static int match_word(BibleSearch*s,unsigned mask){unsigned i,seen=0,oldest=8;uint32_t pos=s->position++;
 ++s->word_count;
 if(s->match_mode==SEARCH_PHRASE){
  s->matched=((s->matched<<1)|1)&mask;
  if(s->matched&(1u<<(s->phrase_length-1))){s->hit_word=s->word_count-s->phrase_length;
#if BIBLE_SEARCH_CLEAR_COMPLETE
   s->matched&=(1u<<(s->phrase_length-1))-1;
#endif
   return 1;
  }
  return 0;
 }
 if(s->suppressed)return 0;
 if(s->match_mode==SEARCH_NEARBY)for(i=0;i<s->phrase_length;++i)if(s->assigned[i].mask&&pos-s->assigned[i].position>=SEARCH_NEAR_WORDS){s->assigned[i].mask=0;--s->rank;}
 if(!mask)return 0;
 if(match_augment(s,mask,s->verse,s->word_count-1,pos,&seen))++s->rank;
 else{
  for(i=0;i<s->phrase_length;++i)if((seen&(1u<<i))&&(oldest==8||s->assigned[i].position<s->assigned[oldest].position))oldest=i;
  if(oldest<8){s->assigned[oldest].mask=0;seen=0;if(!match_augment(s,mask,s->verse,s->word_count-1,pos,&seen))return 0;}
 }
 if(s->rank<s->phrase_length)return 0;
 oldest=0;for(i=1;i<s->phrase_length;++i)if(s->assigned[i].position<s->assigned[oldest].position)oldest=i;
 s->hit_word=s->assigned[oldest].word;s->resume_verse=s->verse;s->verse=s->assigned[oldest].verse;s->restore_verse=1;
 match_reset(s);if(s->match_mode==SEARCH_SAME_VERSE)s->suppressed=1;
 return 1;
}
