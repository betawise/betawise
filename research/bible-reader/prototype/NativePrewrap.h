/* Controlled reader text only: ASCII plus balanced B1/B2 font markers.
 * Produce native cache bytes in-place, without changing encoded length.
 * The resident file remains current and is not resized during this pass. */
static struct {uint32_t pos,split;unsigned x,after,flags;} prewrap;
static unsigned prewrap_raw(unsigned p){return p+(p>=editor.gap_start?editor.gap_end-editor.gap_start:0);}
static int prewrap_more(void){uint8_t *data;unsigned end=g_reader.bytes,p=prewrap.pos,x=prewrap.x,split=prewrap.split,after=prewrap.after,flags=prewrap.flags;
 data=FileBindState(1,0,0,0,0);if(!data)return 0;
 while(p<end){unsigned raw=prewrap_raw(p),c=data[raw],w;FontHeader_t*f;
  if(c==0xb1||c==0xb2){if(p+3>end||data[raw+2]!=c)return 0;if(c==0xb1)flags|=data[raw+1];else flags&=~data[raw+1];p+=3;continue;}
  if(c==0x81)c=' ';if(c==0xad)c='-';
  f=((flags&12)==12)?&super_font:faces[(flags&12)>>2];
  w=f->width_table?f->width_table[c]:f->max_width;x+=w;
  if(x>editor.width){
   if(c==' '){data[raw]=0x81;x=0;split=UINT32_MAX;}
   else if(split!=UINT32_MAX){unsigned s=prewrap_raw(split);data[s]=data[s]=='-'?0xad:0x81;x-=after;split=UINT32_MAX;}
   else {g_reader.error=21;return 0;} /* hard-wrap insertion is a separate case */
   if(x>editor.width){g_reader.error=21;return 0;}
  }
  if(c==' '&&x){split=p;after=x;}else if(c=='-'&&x){split=p;after=x;}
  ++p;
 }
 prewrap.pos=p;prewrap.x=x;prewrap.split=split;prewrap.after=after;prewrap.flags=flags;return 1;
}
static void prewrap_start(void){memset(&prewrap,0,sizeof(prewrap));prewrap.split=UINT32_MAX;}
