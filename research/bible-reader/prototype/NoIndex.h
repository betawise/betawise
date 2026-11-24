/* No search lexicon, map, postings or grammar summaries. Decode one byte at a
 * time; no whole chapter buffer. Character KMP identifies term prefixes at word
 * starts; word-level Shift-And preserves overlapping prefix phrases. */
static void stream_char(BibleSearch*s,unsigned c){unsigned i;s->token_open=1;++s->token_length;c=lower(c);
 for(i=0;i<s->phrase_length;++i){unsigned off=s->offsets[i],k=s->char_state[i];const char*q=s->query+off;
  while(k&&c!=(unsigned char)q[k])k=s->char_failure[off+k-1];
  if(c==(unsigned char)q[k])++k;
  if(!q[k]){if(s->token_length==k)s->token_mask|=1u<<i;k=s->char_failure[off+k-1];}
  s->char_state[i]=k;
 }
}
static int stream_word(BibleSearch*s){unsigned mask=s->token_mask,i;
 for(i=0;i<s->phrase_length;++i)if(!(s->query_prefixes&(1u<<i))&&s->token_length!=strlen(s->query+s->offsets[i]))mask&=~(1u<<i);
 s->token_open=s->token_mask=s->token_length=s->quote=0;memset(s->char_state,0,sizeof(s->char_state));
 return match_word(s,mask);
}
static int step_forward(BibleSearch*s,unsigned budget){
 if(s->restore_verse){s->verse=s->resume_verse;s->restore_verse=0;}
 if(s->done)return -1;
 while(budget--){int c;
  if(!s->open){if(s->chapter>=s->stop_chapter){s->done=1;return -1;}
   if(!BibleOpenChapter(&s->decoder,s->chapter))return -2;
   s->open=1;s->verse=1;s->word_count=s->matched=0;s->position=0;match_reset(s);
   s->token_open=s->token_mask=s->token_length=s->quote=0;s->pending_byte=-3;memset(s->char_state,0,sizeof(s->char_state));
  }
  c=s->pending_byte!=-3?s->pending_byte:BibleReadByte(&s->decoder);s->pending_byte=-3;
  if(c<-1)return -2;
  if(c>=0&&letter(c)){if(s->quote){stream_char(s,'\'');s->quote=0;}stream_char(s,c);continue;}
  if(c=='\''&&s->token_open&&!s->quote){s->quote=1;continue;}
  if(s->token_open){s->pending_byte=c;if(stream_word(s))return 1;continue;}
  if(c==-1){s->open=0;++s->chapter;}
  else if(c=='\n'){++s->verse;s->word_count=s->matched=0;if(s->match_mode==SEARCH_SAME_VERSE)match_reset(s);}
 }
 return 0;
}
