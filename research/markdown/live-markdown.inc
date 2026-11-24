/* Fixed-workspace native Markdown prototype. No borrowed pointer survives an edit. */
#define LIVE_LIMIT 2048
#define LIVE_BULLET 0x95
static uint8_t live_source[LIVE_LIMIT+1],live_previous[LIVE_LIMIT+1];
static uint8_t live_encoded[LIVE_LIMIT*10+12] __attribute__((aligned(2)));
static uint8_t live_backup[LIVE_LIMIT*10+12] __attribute__((aligned(2)));
static uint8_t live_flags[LIVE_LIMIT],live_wanted[LIVE_LIMIT];
static uint8_t live_actual_bullet[LIVE_LIMIT];
static uint32_t live_offsets[LIVE_LIMIT+1],live_n;
static uint32_t live_previous_n;
static uint16_t live_file;
static uint8_t live_mode,live_hidden[LIVE_LIMIT],live_code[LIVE_LIMIT],live_code_end;
static int live_changed;
static uint8_t live_end_flags,live_end_quick;
static uint32_t live_saved_raw,live_saved_source;

/* Decode only the verified native subset, directly in C rather than invoking
 * the layout scanner once per source byte. 81 is a native soft-wrapped space. */
static int live_read(void){
 uint32_t i,n=0,length;uint8_t flags=0,ch;const uint8_t* raw;
 int32_t size=FileQuerySize(ed->file_id);if(size<0)return 26;length=size;
 raw=FileBindState(ed->file_id,0,0,0,0);if(!raw||length>sizeof(live_backup))return 26;
 for(i=0;i<length;){
  if(i==ed->gap_start&&ed->gap_end>i){i=ed->gap_end;continue;}
  ch=raw[i];
  if(ch==0xb1||ch==0xb2){
   if(i+2>=length||raw[i+2]!=ch||(raw[i+1]&~13))return 27;
   if(ch==0xb1)flags|=raw[i+1];else flags&=~raw[i+1];i+=3;continue;
  }
  if(ch==0xb0){
   if(i+2>=length||raw[i+2]!=0xb0)return 27;
   ch=raw[i+1];
   if(ch==LIVE_BULLET){
    if(!n||(live_source[n-1]!='-'&&live_source[n-1]!='+'&&live_source[n-1]!='*'))return 27;
    live_actual_bullet[n-1]=1;i+=3;continue;
   }
  }
  if(ch==0x81)ch=' ';
  if((ch<32&&ch!='\r'&&ch!='\n'&&ch!='\t')||ch>=127)return 21;
  if(n==LIVE_LIMIT)return 20;
  live_offsets[n]=i;live_source[n]=ch;live_flags[n]=flags;live_actual_bullet[n]=0;++n;
  i+=raw[i]==0xb0?3:1;
 }
 live_n=n;live_offsets[n]=length;live_source[n]=0;g_perf.decoded+=n;return 0;
}
static uint32_t plain_offset(uint32_t raw){
 uint32_t n=0;while(n<live_n&&live_offsets[n]<raw)++n;return n;
}
/* Native plain scanning counts the generated bullet as well as its hidden
 * source marker. Translate our source offset to that native counting unit. */
static int live_position(TextScan_t* s,uint32_t index){
 uint32_t i,count=index;for(i=0;i<index&&i<live_n;++i)count+=live_actual_bullet[i];
 return position(s,count);
}
static void live_observe(void){
 uint32_t n;
 g_probe.length=FileQuerySize(ed->file_id);g_probe.caret=ed->caret_offset;
 g_probe.gap_start=ed->gap_start;g_probe.gap_end=ed->gap_end;
 g_probe.caret_flags=ed->caret_scan_flags;g_probe.viewport=ed->viewport_offset;g_probe.selected=ed->selection_state;
 n=live_n<255?live_n:255;memcpy((void*)g_probe.source,live_source,n);g_probe.source[n]=0;g_probe.source_length=n;
}

static int live_is_bullet(uint32_t i,uint32_t n){
 uint32_t j=i;if(i+1>=n||live_source[i+1]!=' ')return 0;
 while(j&&(live_source[j-1]==' '||live_source[j-1]=='\t'))--j;
 return !j||live_source[j-1]=='\r'||live_source[j-1]=='\n';
}
/* Recognize literal code without reserving a fifth font. Backticks remain
 * visible; fences suppress Markdown/list processing across hard newlines. */
static void live_mark_code(uint32_t n){
 uint32_t start=0,end,lead,i,j,r,fence=0,span=0;int only_space,escaped;
 memset(live_code,0,n);live_code_end=0;
 while(start<n){
  end=start;while(end<n&&live_source[end]!='\r'&&live_source[end]!='\n')++end;
  lead=start;while(lead<end&&lead-start<3&&live_source[lead]==' ')++lead;
  r=0;while(lead+r<end&&live_source[lead+r]=='`')++r;
  only_space=1;for(j=lead+r;j<end;++j)if(live_source[j]!=' '&&live_source[j]!='\t')only_space=0;
  if(fence){
   memset(live_code+start,1,end-start+(end<n));
   if(r>=fence&&only_space)fence=0;
  }else if(r>=3){
   int valid=1;for(j=lead+r;j<end;++j)if(live_source[j]=='`')valid=0;
   if(valid){fence=r;memset(live_code+start,1,end-start+(end<n));}
  }
  if(!fence&&!live_code[start]){
   span=0;escaped=0;
   for(i=start;i<end;){
    if(live_source[i]=='`'&&!escaped){
     r=1;while(i+r<end&&live_source[i+r]=='`')++r;
     memset(live_code+i,1,r);
     if(!span)span=r;else if(span==r)span=0;
     i+=r;escaped=0;continue;
    }
    if(span)live_code[i]=1;
    escaped=live_source[i]=='\\'&&!escaped;++i;
   }
   if(end==n)live_code_end=span!=0;
  }
  if(fence)live_code_end=1;else if(end<n)live_code_end=0;
  start=end+1;
 }
}
static int live_word(uint8_t c){return(c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9');}
static int live_space(uint8_t c){return !c||c==' '||c=='\t'||c=='\r'||c=='\n';}
static int live_punct(uint8_t c){return c>=33&&c<=126&&!live_word(c);}
/* ASCII flanking rules for underscores. A pending opener at EOF provides
 * immediate styling when its first content character arrives. */
static unsigned live_under(uint32_t i,uint32_t r,uint32_t n){
 uint8_t before=i?live_source[i-1]:0,after=i+r<n?live_source[i+r]:0;
 int left=!live_space(after)&&(!live_punct(after)||live_space(before)||live_punct(before));
 int right=!live_space(before)&&(!live_punct(before)||live_space(after)||live_punct(after));
 unsigned flags=0;
 if((left&&(!right||live_punct(before)))||(i+r==n&&(live_space(before)||live_punct(before))))flags|=1;
 if(right&&(!left||live_punct(after)))flags|=2;
 return flags;
}
/* Hide only matching marker characters and lengths, outside code. */
static void live_pairs(uint32_t n){
 struct Pair {uint16_t at;uint8_t run,marker;} stack[32];
 unsigned depth=0,i,j,run,flank;int escaped=0;
 memset(live_hidden,0,n);if(g_probe.command!=11)return;
 for(i=0;i<n;){
  uint8_t ch=live_source[i];run=1;
  if(ch=='\r'||ch=='\n'){depth=0;escaped=0;++i;continue;}
  if(live_code[i]){escaped=0;++i;continue;}
  if((ch=='*'||ch=='_')&&!escaped&&!(ch=='*'&&live_is_bullet(i,n))){
   while(i+run<n&&live_source[i+run]==ch)++run;
   flank=ch=='_'?live_under(i,run,n):3;
   if(run<=3){
    if(depth&&stack[depth-1].run==run&&stack[depth-1].marker==ch&&(flank&2)){
     --depth;for(j=0;j<run;++j){live_hidden[stack[depth].at+j]=1;live_hidden[i+j]=1;}
    }else if((flank&1)&&depth<32){stack[depth].at=i;stack[depth].marker=ch;stack[depth++].run=run;}
   }
  }
  escaped=ch=='\\'&&!escaped;i+=run;
 }
}

/* Delete an empty pair only when a deletion removed its last content byte.
 * Literal runs typed by the user are never treated as empty formatting. */
static uint32_t live_empty_pair(uint32_t n,uint32_t* caret,uint32_t* anchor){
 uint32_t i,r,j,removed;
 if(g_probe.command!=11||live_mode!=11||live_file!=ed->file_id||live_previous_n!=n+1)return n;
 for(i=0;i<live_previous_n;++i){
  if((live_previous[i]!='*'&&live_previous[i]!='_')||!live_hidden[i]||(i&&live_previous[i-1]==live_previous[i]))continue;
  for(r=1;i+r<live_previous_n&&live_previous[i+r]==live_previous[i];++r){}
  if(r>3||i+2*r+1>live_previous_n||live_previous[i+r]==live_previous[i])continue;
  for(j=0;j<r;++j)if(live_previous[i+r+1+j]!=live_previous[i]||!live_hidden[i+r+1+j])break;
  if(j!=r)continue;
  if(memcmp(live_source,live_previous,i+r)||memcmp(live_source+i+r,live_previous+i+r+1,live_previous_n-i-r-1))continue;
  removed=2*r;
  memmove(live_source+i,live_source+i+removed,n-i-removed);n-=removed;
  if(*caret>i)*caret=*caret>=i+removed?*caret-removed:i;
  if(*anchor>i)*anchor=*anchor>=i+removed?*anchor-removed:i;
  return n;
 }
 return n;
}
/* Source prefix at a hard-line boundary. Soft wrapping does not start a block. */
static uint32_t live_lead(uint32_t start,uint32_t n){
 while(start<n&&(live_source[start]==' '||live_source[start]=='\t'))++start;return start;
}
static int live_list(uint32_t start,uint32_t end,uint32_t* marker,uint32_t* body){
 uint32_t i=live_lead(start,end),j=i;*marker=i;
 if(i+1<end&&(live_source[i]=='-'||live_source[i]=='+'||live_source[i]=='*')&&live_source[i+1]==' '){*body=i+2;return 1;}
 while(j<end&&live_source[j]>='0'&&live_source[j]<='9'&&j-i<6)++j;
 if(j>i&&j+1<end&&(live_source[j]=='.'||live_source[j]==')')&&live_source[j+1]==' '){*body=j+2;return 2;}
 return 0;
}
static void live_plan(uint32_t n){
 uint32_t i=0,j,run,start=0,end,lead,body,marker;unsigned state=0,under=0,base=0,target,mask,flank;int escaped=0,list=0;
 live_mark_code(n);live_pairs(n);g_perf.parsed+=n;live_end_quick=1;
 while(i<n){
  if(i==start){
   end=i;while(end<n&&live_source[end]!='\r'&&live_source[end]!='\n')++end;
   lead=live_lead(start,end);base=0;body=lead;list=live_code[i]?0:live_list(start,end,&marker,&body);
   if(!live_code[i]&&!list&&lead<end&&live_source[lead]=='#'){
    j=lead;while(j<end&&live_source[j]=='#'&&j-lead<6)++j;
    if(j<end&&live_source[j]==' '&&j+1==end)live_end_quick=0;
    if(j+1<end&&live_source[j]==' '){base=4;if(g_probe.command==11)for(run=lead;run<=j;++run)live_hidden[run]=1;}
   }else if(!live_code[i]&&!list&&lead+1<end&&live_source[lead]=='>'&&live_source[lead+1]==' ')base=8;
  }
  run=1;target=state|under|base;
  if(live_source[i]=='\r'||live_source[i]=='\n'){state=under=0;target=0;start=i+1;}
  else if(live_code[i])target=0;
  else if(base==8&&i<lead+2&&live_source[lead]=='>')target=0;
  else if(list==1&&i==marker)target=0; /* Keep the original ASCII list marker. */
  else if((live_source[i]=='*'||live_source[i]=='_')&&!escaped){
   while(i+run<n&&live_source[i+run]==live_source[i])++run;
   if(run<=3){
    mask=run==1?8:run==2?4:12;
    if(live_source[i]=='*'){target=live_hidden[i]?1:0;state^=mask;}
    else{
     flank=live_under(i,run,n);
     if(((under&mask)==mask&&(flank&2))||(flank&1)){target=live_hidden[i]?1:0;under^=mask;}
    }
   }
  }
  if(live_hidden[i]&&live_source[i]!='*'&&live_source[i]!='_')target=1;
  for(j=0;j<run;++j)live_wanted[i+j]=target;
  escaped=live_source[i]=='\\'&&!escaped;i+=run;
 }
 live_end_flags=live_code_end?0:state|under|base;
}
static void live_remember(uint32_t n){
 memcpy(live_previous,live_source,n);
 live_previous_n=n;live_file=ed->file_id;live_mode=g_probe.command;live_saved_raw=ed->caret_offset;live_saved_source=plain_offset(ed->caret_offset);
}
static int live_restyle(void){
 TextScan_t s;uint32_t n,i,k=0,caret,anchor=0,backup_n,length;uint16_t selected=ed->selection_state;
 unsigned emitted=0,target;const uint8_t* raw;int err,changed=0;
 live_changed=0;if((err=live_read()))return err;n=live_n;
 caret=plain_offset(ed->caret_offset);if(selected)anchor=plain_offset(ed->selection_anchor);
 n=live_empty_pair(n,&caret,&anchor);
 changed=n!=live_n;live_plan(n);
 for(i=0;i<n&&!changed;++i)if(live_flags[i]!=live_wanted[i]||live_actual_bullet[i])changed=1;
 if(!changed){++g_perf.fastpath;live_remember(n);live_observe();return 0;}
 /* Save the original encoded bytes before any editing routine can move RAM. */
 length=FileQuerySize(ed->file_id);raw=FileBindState(ed->file_id,0,0,0,0);backup_n=0;
 if(!raw||length>=sizeof(live_backup))return 26;
 for(i=0;i<length;++i)if(i<ed->gap_start||i>=ed->gap_end)live_backup[backup_n++]=raw[i];
 k=0;
 for(i=0;i<n;++i){
  target=live_wanted[i];
  if(target!=emitted){
   if(emitted){live_encoded[k++]=0xb2;live_encoded[k++]=emitted;live_encoded[k++]=0xb2;}
   if(target){live_encoded[k++]=0xb1;live_encoded[k++]=target;live_encoded[k++]=0xb1;}emitted=target;
  }
  live_encoded[k++]=live_source[i];

 }
 if(emitted){live_encoded[k++]=0xb2;live_encoded[k++]=emitted;live_encoded[k++]=0xb2;}
 ++g_perf.rewrites;live_changed=1;
 TextScanInit(ed,&s,TEXT_POSITION_START);
 if(TextScanDelete(&s,0xffffffff,TEXT_BYTES_ENCODED,false,false))return 22;
 TextScanInit(ed,&s,TEXT_POSITION_START);
 if(TextScanInsert(&s,live_encoded,k,TEXT_BYTES_ENCODED)){
  TextScanInit(ed,&s,TEXT_POSITION_START);TextScanDelete(&s,0xffffffff,TEXT_BYTES_ENCODED,false,false);
  TextScanInit(ed,&s,TEXT_POSITION_START);if(TextScanInsert(&s,live_backup,backup_n,TEXT_BYTES_ENCODED))return 28;
  TextEditorRefresh(ed);return 23;
 }
 ed->selection_state=0;if(TextEditorRefresh(ed)||(err=live_read()))return 24;
 if(!live_position(&s,caret)||TextEditorSetScanPosition(&s,false))return 24;
 if(selected){TextScan_t a;if(!live_position(&a,anchor))return 25;ed->selection_anchor=a.offset;ed->selection_flags=a.flags;ed->selection_state=selected;}
 live_remember(n);live_observe();return 0;
}
/* List entry assistance uses native text insertion; it does not add file markup. */
static int live_enter(uint8_t* prefix,uint32_t* prefix_n){
 TextScan_t s;uint32_t caret,start,end,marker,body,i,j,value=0;int kind;
 *prefix_n=0;if(ed->selection_state||live_read())return 0;live_mark_code(live_n);
 caret=plain_offset(ed->caret_offset);if((caret<live_n&&live_code[caret])||(caret&&live_code[caret-1]))return 0;start=caret;while(start&&live_source[start-1]!='\r'&&live_source[start-1]!='\n')--start;
 end=caret;while(end<live_n&&live_source[end]!='\r'&&live_source[end]!='\n')++end;
 kind=live_list(start,end,&marker,&body);if(!kind||caret<body||body-start>48)return 0;
 for(i=body;i<end&&(live_source[i]==' '||live_source[i]=='\t');++i){}
 if(i==end){
  uint32_t count=end-start;for(i=start;i<end;++i)count+=live_actual_bullet[i];
  if(!live_position(&s,start)||TextScanDelete(&s,count,TEXT_BYTES_PLAIN,false,false)||TextEditorRefresh(ed))return 0;
  if(live_read()||!live_position(&s,start)||TextEditorSetScanPosition(&s,false))return 0;
  return 1;
 }
 memcpy(prefix,live_source+start,body-start);*prefix_n=body-start;
 if(kind==2){
  for(i=marker;i<body-2;++i)value=value*10+live_source[i]-'0';if(value==999999){*prefix_n=0;return 0;}++value;
  j=marker-start;i=0;do{prefix[56+i++]=(value%10)+'0';value/=10;}while(value);
  while(i)prefix[j++]=prefix[56+--i];prefix[j++]=live_source[body-2];prefix[j++]=' ';*prefix_n=j;
 }
 return 0;
}
/* Native selection deletion skips hidden regions. A whole-document selection
 * must remove its source markers and generated glyphs as well as visible text.
 * Keep partial-selection behavior native; only claim the complete source range. */
static int live_delete_all(int cut,int32_t* status){
 TextScan_t s;uint32_t a,b;int32_t error;
 if(!ed->selection_state||live_read())return 0;
 a=plain_offset(ed->selection_anchor);b=plain_offset(ed->caret_offset);
 if(!((a==0&&b==live_n)||(b==0&&a==live_n)))return 0;
 if(cut){
  if(ClipboardSet(live_source,live_n,CLIPBOARD_TEXT_PLAIN)!=(int32_t)live_n){*status=TEXT_ERROR_FILE;return 1;}
  g_probe.clip_length=ClipboardGet((void*)g_probe.clip,127,CLIPBOARD_TEXT_PLAIN);
 }
 error=TextScanInit(ed,&s,TEXT_POSITION_START);
 if(!error)error=TextScanDelete(&s,0xffffffff,TEXT_BYTES_ENCODED,false,false);
 if(error){*status=error;return 1;}
 ed->selection_state=0;ed->selection_flags=0;ed->selection_anchor=0;
 error=TextEditorRefresh(ed);
 if(!error)error=TextScanInit(ed,&s,TEXT_POSITION_START);
 if(!error)error=TextEditorSetScanPosition(&s,false);
 *status=error;return 1;
}
static int live_event(uint32_t message,uint32_t param,struct Control* c){
 int32_t status=0,used;uint32_t copy_begin=0,copy_end=0,prefix_n=0,i;int copy=0,quick,manual;uint8_t prefix[64];
 ++g_perf.events;g_perf.message=message;g_perf.param=param;g_perf.phase=1;
 if(!locate()){g_perf.phase=4;return 0;}
 if(ed->selection_state&&((message==0x1000003&&param==0x8041)||(message==0x1000001&&param==3))){
  if(!live_read()){uint32_t a=plain_offset(ed->selection_anchor),b=plain_offset(ed->caret_offset);copy_begin=a<b?a:b;copy_end=a<b?b:a;copy=1;}
 }
 quick=message==0x1000001&&param>32&&param<127&&param!='*'&&param!='_'&&param!='`'&&param!='\\'&&param!='#'&&param!='>'&&param!='-'&&param!='+'&&
  !ed->selection_state&&live_file==ed->file_id&&live_mode==g_probe.command&&live_end_quick&&live_previous_n<LIVE_LIMIT&&
  ed->caret_offset==live_saved_raw&&live_saved_source==live_previous_n&&(ed->caret_scan_flags&13)==live_end_flags;
 used=0;
 if(ed->selection_state){
  uint32_t key=param&~KEY_MOD_CAPS_LOCK;
  int cut=(message==0x1000003&&key==(KEY_MOD_CTRL|KEY_X))||(message==0x1000001&&param==24);
  int erase=(message==0x1000003&&(key==KEY_DELETE||key==KEY_BACKSPACE))||(message==0x1000001&&(param==8||param==127));
  if(cut||erase)used=live_delete_all(cut,&status);
 }
 if(!used&&message==0x1000001&&param==13)used=live_enter(prefix,&prefix_n);
 manual=used;
 if(!used)used=TextEditorHandleMessage(ed,message==0x1000001?MSG_CHAR:MSG_KEY,param,0,&status);
 if(used==1&&prefix_n)for(i=0;i<prefix_n;++i)TextEditorHandleMessage(ed,MSG_CHAR,prefix[i],0,&status);
 g_perf.phase=2;
 if(used==1){
  if(quick&&!status){
   i=live_previous_n++;live_source[i]=live_previous[i]=param;live_source[live_previous_n]=0;live_n=live_previous_n;
   live_hidden[i]=live_actual_bullet[i]=0;live_flags[i]=live_wanted[i]=live_end_flags;live_code[i]=live_code_end;
   live_saved_raw=ed->caret_offset;live_saved_source=live_previous_n;live_changed=0;++g_perf.fastpath;
   g_probe.error=0;live_observe();
  }else g_probe.error=status?30:live_restyle();g_perf.phase=3;
  if(!g_probe.error&&copy&&copy_end<=live_previous_n){
   if(ClipboardSet(live_source+copy_begin,copy_end-copy_begin,CLIPBOARD_TEXT_PLAIN)!=(int32_t)(copy_end-copy_begin))g_probe.error=31;
   g_probe.clip_length=ClipboardGet((void*)g_probe.clip,127,CLIPBOARD_TEXT_PLAIN);
  }
  c->action=(live_changed||manual)?3:0;g_perf.phase=4;return 1;
 }
 g_perf.phase=4;return 0;
}
static int live_seed(void){
 TextScan_t s;uint32_t i,n=g_seed_length;if(n>LIVE_LIMIT-32)return 40;
 for(i=0;i<n;++i)live_source[i]="word "[i%5];
 TextScanInit(ed,&s,TEXT_POSITION_START);if(TextScanDelete(&s,0xffffffff,TEXT_BYTES_ENCODED,false,false))return 41;
 TextScanInit(ed,&s,TEXT_POSITION_START);if(TextScanInsert(&s,live_source,n,TEXT_BYTES_PLAIN))return 42;
 if(TextEditorRefresh(ed)||!position(&s,n)||TextEditorSetScanPosition(&s,false))return 43;
 live_file=0;return 0;
}
