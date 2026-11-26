#!/usr/bin/env python3
"""Full streaming viewer: independent source/cursor/selection/LCD-roll oracle."""
import argparse,hashlib,importlib.util,json,os,re,shlex,shutil,struct,subprocess,sys
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw
from check import ROOT,HERE,prepare_session
from bible_layout import captured_font,render,font as terminal_font
from neo_reader import lcd_frames
from screen_bitmap import compare
APP=ROOT/'betawise/applets/BibleReader'
spec=importlib.util.spec_from_file_location('repl',HERE/'check-repl.py');repl=importlib.util.module_from_spec(spec);spec.loader.exec_module(repl)
WORD=re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")
def pitch(f):return max(4,f['height'])
def cap_top(f):
 w=f['widths'][ord('A')];g=f['glyphs'][ord('A')]
 return min(y for y in range(f['height'])for x in range(w)if g[(y//8)*w+x]>>(y%8)&1)
def lines_for(verses,start,ordinal,numbers,widths,forced_break=0):
 offsets=[];raw=0
 for v in verses:offsets.append(raw);raw+=len(v)+1
 words=[]
 for vi,text in enumerate(verses[start-1:],start):
  base=offsets[vi-1]
  if vi==start and ordinal:
   n=list(WORD.finditer(text))[ordinal].start();text=text[n:];base+=n
  for wi,m in enumerate(re.finditer(r'[^ ]+',text)):
   chars=([(d,True,base+m.start())for d in str(vi)]if numbers and wi==0 and not(vi==start and ordinal)else[])+[(c,False,base+m.start()+j)for j,c in enumerate(m.group())]
   words.append((chars,vi,base+m.start()))
 result=[];cells=[];bounds=[];x=0;start_offset=None;end_offset=0
 def flush():
  nonlocal cells,bounds,x,start_offset
  if cells:result.append(dict(cells=cells,bounds=bounds,start=start_offset,end=end_offset,width=x))
  cells=[];bounds=[];x=0;start_offset=None
 def add(c,sup,off):
  nonlocal x,start_offset,end_offset
  w=4 if sup else widths[ord(c)];cells.append((c,sup,off,x,w))
  if not sup:
   if start_offset is None:start_offset=off
   bounds.extend([(off,x),(off+1,x+w)]);end_offset=off+1
  x+=w
 for chars,vi,base in words:
  total=sum(4 if sup else widths[ord(c)]for c,sup,off in chars)
  if cells and(forced_break and base==forced_break or x+widths[32]+total>264):flush()
  if cells:add(' ',False,base-1)
  for c,sup,off in chars:
   w=4 if sup else widths[ord(c)]
   if x+w>264 or(x and forced_break and off==forced_break and base!=forced_break):flush()
   add(c,sup,off)
 flush();return result,offsets
class Model:
 def __init__(self,books,version="KJV"):self.version=version;self.books=books;self.chapters=[c for b in books for c in b['chapters']];self.ref=(0,1,0);self.forced_break=0;self.numbered=1;self.mode=0;self.clip=None;self.font_hash=None;self.search_mode=0
 def setfont(self,f):
  self.f=f;self.stride=pitch(f);self.trim=int(cap_top(f)>0);self.rows=min(16,(65+self.trim)//self.stride);self.extra=65+self.trim-self.rows*self.stride
  if getattr(self,'lcd_roll',False):self.rows=64//self.stride;self.extra=self.trim=0
 def y(self,row):return row*self.stride+(row*self.extra//(self.rows-1)if self.rows>1 else 0)-self.trim
 def band(self,row):return max(0,self.y(row)),max(0,self.y(row+1))if row+1<self.rows else (64 if getattr(self,'lcd_roll',False)else 65)
 def reset(self,ref=None,offset=None):
  if ref is not None:self.ref=tuple(ref)
  ch,v,w=self.ref;self.forced_break=0;self.lines,self.offsets=lines_for(self.chapters[ch],1,0,self.numbered,self.f['widths']);target=self.offsets[v-1]+(list(WORD.finditer(self.chapters[ch][v-1]))[w].start()if w else 0)if offset is None else offset
  self.row=next(i for i,l in enumerate(self.lines)if l['start']<=target<=l['end']);self.top=self.row;self.caret=self.anchor=target;self.anchor_row=self.row;self.sel=False;self.roll=0;self.goal=None;self.mode=0;self.prompt_kind=0;self.command=''
 def x(self):return next(x for off,x in reversed(self.lines[self.row]['bounds'])if off==self.caret)
 def closest(self,row,x):return min(self.lines[row]['bounds'],key=lambda p:abs(p[1]-x))[0]
 def normalize(self):pass
 def cursor_rect(self):
  y,end=self.band(self.row-self.top);return y,end-y
 def mov(self,key,shift=False,control=False):
  if shift:
   if not self.sel:self.anchor=self.caret;self.anchor_row=self.row;self.sel=True
  else:
   if self.sel and self.anchor!=self.caret and key in['Left','Right']:
    if(key=='Left'and self.anchor<self.caret)or(key=='Right'and self.anchor>self.caret):self.caret=self.anchor;self.row=self.anchor_row
    self.sel=False;self.goal=None;return
   self.sel=False
  line=self.lines[self.row]
  if control and key in['Left','Right']:
   raw='\n'.join(self.chapters[self.ref[0]])+'\n';starts=[m.start()for m in WORD.finditer(raw)]
   if key=='Left':self.caret=max([o for o in starts if self.lines[0]['start']<=o<self.caret]or[self.lines[0]['start']])
   else:self.caret=next((o for o in starts if o>self.caret),len(raw)-1)
   self.row=next(i for i,l in enumerate(self.lines)if l['start']<=self.caret<=l['end']);self.goal=None
  elif key=='Left':
   if self.caret>line['start']:self.caret-=1
   elif self.row:self.row-=1;self.caret=self.lines[self.row]['end']
   self.goal=None
  elif key=='Right':
   if self.caret<line['end']:self.caret+=1
   elif self.row+1<len(self.lines):self.row+=1;self.caret=self.lines[self.row]['start']
   self.goal=None
  elif key in['Home','End']:self.caret=line['start'if key=='Home'else'end'];self.goal=None
  else:
   if self.goal is None:self.goal=self.x()
   row=max(0,self.row-1)if key=='Up'else min(len(self.lines)-1,self.row+1);self.row=row;self.caret=self.closest(row,self.goal)
  target=self.top
  if self.row<self.top:target=self.row
  elif self.row>=self.top+self.rows:target=self.row-self.rows+1
  self.roll=(self.roll+(target-self.top)*self.stride)%64 if getattr(self,'lcd_roll',False)and abs(target-self.top)==1 else self.roll if getattr(self,'lcd_roll',False)and target==self.top else 0
  self.top=target;self.normalize()
 def page(self,d):
  row=self.top+self.rows if d>0 else max(0,self.top-self.rows)
  if row<len(self.lines):self.caret=self.closest(row,self.x());self.top=self.row=row;self.roll=0
  self.sel=False;self.normalize()
 def copy(self):
  ch,v,w=self.ref;raw='\n'.join(self.chapters[ch])+'\n';verse=next((i for i,off in enumerate(self.offsets[1:],1)if off>self.caret),len(self.offsets))
  if self.sel and self.anchor!=self.caret:
   lo,hi=sorted((self.anchor,self.caret));text=raw[lo:hi].replace('\n',' ');a=raw[:lo].count('\n')+1;b=raw[:max(lo,hi-1)].count('\n')+1
  else:a=b=verse;text=self.chapters[ch][verse-1]
  book=max(i for i in range(66)if sum(len(b['chapters'])for b in self.books[:i])<=ch);local=ch-sum(len(b['chapters'])for b in self.books[:book])+1;ref=f"{self.books[book]['name']} {local}:{a}"+(f'-{b}'if b!=a else'')+f' ({self.version})';self.notice='Copied';self.clip=(text+'\r'+ref).encode();self.mode=3
 def image(self):
  im=Image.new('1',(264,65));px=im.load()
  small_rows=['111/101/101/111','010/110/010/111','110/001/010/111','110/011/001/110','101/101/111/001','111/100/011/110','011/100/111/111','111/001/010/010','111/111/101/111','111/111/001/110']
  normal=[[31,17,31],[18,31,16],[29,21,23],[21,21,31],[7,4,31],[23,21,29],[31,21,29],[1,1,31],[31,21,31],[23,21,31]]
  for row,line in enumerate(self.lines[self.top:self.top+self.rows]):
   for c,sup,off,x,w in line['cells']:
    y0=self.y(row)+(cap_top(self.f)if sup else 0);h=(4 if self.f['height']<8 else 5)if sup else self.f['height']
    for y in range(h):
     yy=y0+y
     if not 0<=yy<65:continue
     for dx in range(3 if sup else w):
      bit=(small_rows[int(c)].split('/')[y][dx]=='1'if self.f['height']<8 else normal[int(c)][dx]>>y&1)if sup else self.f['glyphs'][ord(c)][(y//8)*w+dx]>>(y%8)&1
      if bit:px[x+dx,yy]=1
  if self.sel:
   lo,hi=sorted((self.anchor,self.caret))
   for r,line in enumerate(self.lines[self.top:self.top+self.rows]):
    selected=[(x,x+w)for c,sup,off,x,w in line['cells']if lo<=off<hi]
    if selected:
     y,end=self.band(r);box=(min(x for x,z in selected),y,max(z for x,z in selected),end);im.paste(ImageChops.invert(im.crop(box).convert('L')).convert('1'),box)
  if self.mode:
   draw=ImageDraw.Draw(im);draw.rectangle((6,14,257,49),fill=0,outline=1)
   def text(value,y,center=False):
    f=self.ui;total=sum(f['widths'][ord(c)]for c in value);x=(264-total)//2 if center and total<240 else 12
    for c in value:
     w=f['widths'][ord(c)];g=f['glyphs'][ord(c)]
     if x+w>250:break
     for yy in range(f['height']):
      for dx in range(w):
       if g[(yy//8)*w+dx]>>(yy%8)&1:im.putpixel((x+dx,y+yy),1)
     x+=w
   if self.mode==3:text(self.notice,24,True)
   else:text('Go to:'if self.mode==1 else['Find: Same verse [Tab]','Find: Exact phrase [Tab]','Find: Nearby 20 words [Tab]'][self.search_mode],16,True);text(self.command,32);draw.line((12+6*len(self.command),32,12+6*len(self.command),47),fill=1)
  return im

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--search-modes',action='store_true');ap.add_argument('--readthrough',choices=['line','page']);ap.add_argument('--work-profile',action='store_true');ap.add_argument('--lcd-roll',action='store_true');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--version',choices=['KJV','NKJV','ESV','NIV','NASB','CSB'],default='KJV');ap.add_argument('--all-vendor-fonts',action='store_true');ap.add_argument('--no-terminal-font',action='store_true');ap.add_argument('--vendor-font',choices=['small','medium','large','vlarge','xlarge','tiny']);ap.add_argument('--verify-only',action='store_true');ap.add_argument('--quick',action='store_true');ap.add_argument('--benchmark',action='store_true');ap.add_argument('--production',action='store_true');ap.add_argument('--direct',action='store_true');ap.add_argument('--combined',action='store_true');ap.add_argument('--experiment',choices=['huffman-prune'],default='huffman-prune');a=ap.parse_args();out=a.output.resolve()
 if a.verify_only:verify(out);return
 assert not a.lcd_roll or a.readthrough,'LCD roll comparison currently verifies system-font read-throughs only'
 out.mkdir(parents=True,exist_ok=False);fw=ROOT/'Ghidra/Alphasmart Neo/SmartApplets';vendor=(ROOT/'betawise/fonts/BetaWiseTerminal-Tiny.OS3KApp'if a.vendor_font=='tiny'else fw/f'neofont{a.vendor_font}.os3kapp')if a.vendor_font else None;stem='BibleReader-Stream'+(''if a.version=='KJV'else'-'+a.version);args=['READER=Streaming',f'LCD_ROLL={int(a.lcd_roll)}',f'WORK_PROFILE={int(a.work_profile)}',f'VERSION={a.version}','STREAM_SEARCH=1','PRUNE=1','DIRECT_DRAW=1',f'PROFILE={int(not a.production)}',f'TEST_FONT={int(bool(vendor))}',f'TEST_FONT_ID={hex(int.from_bytes(vendor.read_bytes()[20:22],"big"))if vendor else ""}',]
 with(out/'build.log').open('w')as log:subprocess.run(['make','-C',str(APP),'-B',*args],stdout=log,stderr=subprocess.STDOUT,check=True)
 mame=ROOT/'mame/neodiag';prepare_session(out,fw,'extra',mame);flash=bytearray((out/'nvram/asneo/flashnv').read_bytes());flash[0x70000:]=b'\xff'*(len(flash)-0x70000);offset=0x70000;(out/'artifacts').mkdir();images=[fw/'alphawordplus.os3kapp',APP/(stem+'.OS3KApp'),ROOT/'betawise/fonts/BetaWiseTerminal-Medium.OS3KApp']
 if a.no_terminal_font:
  assert not vendor,'--no-terminal-font cannot supply a test font'
  images=images[:2]
 if a.all_vendor_fonts:
  assert not vendor,'--all-vendor-fonts starts with the system font'
  images +=[fw/f'neofont{f}.os3kapp'for f in ['small','medium','large','vlarge','xlarge']]
 if vendor:
  if a.vendor_font=='tiny':images[-1]=vendor
  else:images.append(vendor)
 for p in images:b=p.read_bytes();assert offset+len(b)<=len(flash);flash[offset:offset+len(b)]=b;offset+=len(b);shutil.copyfile(p,out/'artifacts'/p.name)
 (out/'nvram/asneo/flashnv').write_bytes(flash);nm=subprocess.check_output(['m68k-linux-gnu-nm','-n',str(APP/(stem+'.elf'))],text=True);sym={s[2]:int(s[0],16)for l in nm.splitlines()if len(s:=l.split())==3};(out/'symbols.json').write_text(json.dumps(sym,indent=2));data=ROOT/f'.research-work/bible-compression/reader-viewer/{a.version.lower()}/source.json';shutil.copyfile(data,out/'source.json');books=json.loads(data.read_bytes());ch=lambda b,c:sum(len(x['chapters'])for x in books[:b-1])+c-1
 height=dict(small=11,medium=13,large=16,vlarge=21,xlarge=32,tiny=6).get(a.vendor_font,16);rowcount=min(16,(65+(0 if height in [6,8]else 1))//max(4,height))
 def ck(name,keys=None,actions=None,**kw):return dict(name=name,keys=keys or[],actions=actions or[],**kw)
 def move_case(name,key,shift=False):return ck(name,[["Left Shift",key]]if shift else[key],[['move',key,shift]])
 def ref_case(name,b,c,v):return ck(name,['G']+[('Space'if x==' 'else x)for x in f'{b} {c} {v}']+['Enter'],[['ref',ch(b,c),v,0]])
 checks=[ck('Initial Genesis',actions=[['ref',0,1,0]]),move_case('Cursor right','Right'),move_case('Select one character','Right',True),ck('Copy selected character',[['Left Ctrl','C']],[['copy']],mode=3,clipboard=True),ck('Dismiss copy',['Escape'],[['escape']]),move_case('Home','Home'),ck('Move to viewport bottom',['Down']*(rowcount-1),[['move','Down',False]]*(rowcount-1)),move_case('Roll one line down','Down'),move_case('Roll second line down','Down'),move_case('Move cursor up','Up'),move_case('Extend selection down','Down',True),move_case('Extend selection right','Right',True),move_case('Shrink selection up','Up',True),ck('Copy multiline selection',[['Left Ctrl','C']],[['copy']],mode=3,clipboard=True),ck('Dismiss multiline copy',['Escape'],[['escape']]),ck('Next page',['N'],[['page',1]]),ck('Previous page',['P'],[['page',-1]]),ref_case('Jump median chapter',40,2,1),move_case('End of line','End'),move_case('Select to next line','Down',True),ck('Copy selected wrapped text',[['Left Ctrl','C']],[['copy']],mode=3,clipboard=True),ck('Dismiss selected wrapped copy',['Escape'],[['escape']]),ck('Select whole chapter',[['Left Ctrl','A']],[['all']]),ck('Copy whole chapter',[['Left Ctrl','C']],[['copy']],mode=3,clipboard=True),ck('Dismiss whole chapter copy',['Escape'],[['escape']]),ck('Copy current verse',[['Left Ctrl','C']],[['copy']],mode=3,clipboard=True),ck('Dismiss current verse copy',['Escape'],[['escape']]),ref_case('Jump John3:16',43,3,16),move_case('Read before jump anchor','Up'),ref_case('Return John3:16',43,3,16),ck('Next word',[['Left Ctrl','Right']],[['move','Right',False,True]]),ck('Previous word',[['Left Ctrl','Left']],[['move','Left',False,True]]),ck('Hide verse numbers',['V'],[['numbers']])]
 if not a.quick:
  checks[3:3]=[ck('Expand selection by one character',[['Left Shift','Right']],[['move','Right',True]],no_repaint=True,max_data_writes=24 if not vendor else None),ck('Shrink selection by one character',[['Left Shift','Left']],[['move','Left',True]],no_repaint=True,max_data_writes=24 if not vendor else None)]
  # Independent source token ordinals for the first two prefix search matches.
  matches=[(ci,vi,j)for ci,chapter in enumerate(c for b in books for c in b['chapters'])for vi,v in enumerate(chapter,1)for j,m in enumerate(WORD.finditer(v))if m.group().lower().startswith('believe')];first,second=[h for h in matches if h>=(ch(43,3),16,0)][:2]
  checks +=[ck('Find word prefix',['Find','Tab']+list('BELIEVE')+[['Left Shift','8'],'Enter'],[['search-mode',1],['ref',*first]]),ck('Find next occurrence',[['Command','G']],[['ref',*second]]),ck('Previous search result',[['Command','Left Shift','G']],[['ref',*first]]),ck('Replay next search result',[['Command','G']],[['ref',*second]]),ck('Previous via modified Find',[['Command','Left Shift','Find']],[['ref',*first]]),ck('Next via modified Find',[['Command','Find']],[['ref',*second]]),ck('CtrlG verse jump',[['Left Ctrl','G']]+list('43')+['Space','3','Space','1','6','Enter'],[['ref',ch(43,3),16,0]]),ck('CtrlF prefix search',[['Left Ctrl','F']]+list('BELIEVE')+[['Left Shift','8'],'Enter'],[['ref',*first]]),ck('Native font picker',[['Left Ctrl','Left Alt','Command','F'],'Home','Enter'],[['reflow']]),ref_case('Return median numbered view',40,2,1),ck('Enable numbers',['V'],[['numbers']]),ck('Scroll after font change',['Down']*4,[['move','Down',False]]*4),ck('Resume after AlphaWord',['Applets','Home','Enter','Applets','Down','Enter'],[['resume']],resume=True)]
 if not a.quick:
  checks += [ck('Chapter beginning',[['Left Ctrl','Home']],[['start',False]]),ck('Chapter end',[['Left Ctrl','End']],[['end',False]]),ck('Select back to chapter beginning',[['Left Ctrl','Left Shift','Home']],[['start',True]]),ck('Copy reverse selection',[['Left Ctrl','C']],[['copy']],mode=3,clipboard=True),ck('Dismiss reverse selection',['Escape'],[['escape']])]
 if a.vendor_font and not a.quick and not a.benchmark:
  checks +=[ck('Re-select vendor font',[['Left Ctrl','Left Alt','Command','F'],'End','Enter'],[['reflow']]),ck('LCD wrap forward',['Down']*20,[['move','Down',False]]*20),ck('LCD wrap backward',['Up']*20,[['move','Up',False]]*20)]
 if a.benchmark:
  checks=[ck('Initial Genesis',actions=[['ref',0,1,0]]),ref_case('Fresh median chapter',40,2,1),ck('Cached median redraw',['R'],[['resume']]),ck('Median page forward',['N'],[['page',1]]),ck('Median page backward',['P'],[['page',-1]]),ck('Median cursor right',['Right'],[['move','Right',False]]),ck('Median selection',[['Left Shift','Right']],[['move','Right',True]]),ck('Clear selection',['Escape'],[['escape']]),ck('Bottom of median screen',['Down']*(rowcount-1),[['move','Down',False]]*(rowcount-1)),move_case('Roll median line down','Down'),ck('Top of median screen',['Up']*(rowcount-1),[['move','Up',False]]*(rowcount-1)),move_case('Roll median line up','Up'),ref_case('Fresh John chapter',43,3,1),ref_case('Psalm119 last verse',19,119,176),ref_case('Psalm119 beginning',19,119,1)]
  checks +=[ck('Checkpoint eviction forward '+str(i),['N'],[['page',1]])for i in range(10)]+[ck('Checkpoint eviction backward '+str(i),['P'],[['page',-1]])for i in range(10)]
 if not a.quick and not a.benchmark:
  checks +=[ck('Jump panel after scrolling',[['Left Ctrl','G']],[['prompt',1]],mode=1,no_repaint=True),ck('Edit reference panel',list('43')+['Space','3','Space','1','6'],[['type','43 3 16']],mode=1,no_repaint=True),ck('Correct reference field',['Clear File']+list('43')+['Space','3','Space','1','7','Backspace','6'],[['type','43 3 16']],mode=1,no_repaint=True),ck('Accept centered reference',['Enter'],[['ref',ch(43,3),16,0]]),ck('Search panel after scrolling',['Find'],[['prompt',2]],mode=2,no_repaint=True),ck('Dismiss search panel',['Escape'],[['escape']]),ck('Open invalid-reference panel',[['Left Ctrl','G']],[['prompt',1]],mode=1,no_repaint=True),ck('Reject invalid reference',list('1')+['Space','1','Space','9','9','Enter'],[['notice','Invalid reference; Esc returns']],mode=3),ck('Dismiss invalid-reference notice',['Escape'],[['escape']])]
 if not a.quick and not a.benchmark:
  rare=[]
  for ci,chapter in enumerate(c for b in books for c in b['chapters']):
   for vi,text in enumerate(chapter,1):
    words=[m.group().lower()for m in WORD.finditer(text)]
    rare +=[(ci,vi,j)for j in range(len(words)-3)if words[j:j+4]==['maher','shalal','hash','baz']]
  assert len(rare)==2,'source-backed two-hit search fixture'
  # Place these before the font cycle, so the final demo still leaves Small selected.
  at=next((i for i,c in enumerate(checks)if 'font_entry'in c),len(checks))
  checks[at:at]=[ref_case('Reset before rare phrase',1,1,1),ck('Find hyphenated name',['Find']+[('Space'if c==' 'else c)for c in 'MAHER SHALAL HASH BAZ']+['Enter'],[['ref',*rare[0]]]),ck('Next name occurrence',[['Command','Find']],[['ref',*rare[1]]]),ck('Search exhausted notice',[['Command','Find']],[['notice','No more matches']],mode=3),ck('Previous result from notice',[['Command','Left Shift','Find']],[['ref',*rare[0]]]),ck('Copy before switching applets',[['Left Ctrl','C']],[['copy']],mode=3,clipboard=True),ck('Dismiss notice across applet switch',['Applets','Home','Enter','Applets','Down','Enter'],[['resume']],resume=True)]
 if a.search_modes:
  sys.path.insert(0,str(ROOT/'betawise/research/bible-reader'));spec_modes=importlib.util.spec_from_file_location('mode_oracle',ROOT/'betawise/research/bible-reader/check-search-modes.py');mo=importlib.util.module_from_spec(spec_modes);spec_modes.loader.exec_module(mo)
  flat=[c for b in books for c in b['chapters']];checks=[ck('Initial Genesis',actions=[['ref',0,1,0]])];current_mode=0
  def typekeys(q):return ['Space'if c==' 'else['Left Shift','8']if c=='*'else c.upper()for c in q]
  for mode,query in [(0,'faith works'),(1,'kingdom of God'),(2,'life God'),(0,'be* bel*')]:
   checks.append(ref_case('Reset '+query,43,3,16));hs=mo.oracle(flat,query,mode);first=next(h for h in hs if h>=(ch(43,3),16,0));second=next(h for h in hs if h>first)
   checks +=[ck('Open search '+query,['Find'],[['prompt',2]],mode=2,no_repaint=True),ck('Choose mode '+str(mode),['Tab']*((mode-current_mode)%3),[['search-mode',mode]],mode=2,no_repaint=True)]if mode!=current_mode else[ck('Open search '+query,['Find'],[['prompt',2]],mode=2,no_repaint=True)]
   checks +=[ck('Enter query '+query,typekeys(query),[['type',query.lower()]],mode=2,no_repaint=True),ck('Result '+query,['Enter'],[['ref',*first]]),ck('Next '+query,[['Command','Find']],[['ref',*second]]),ck('Previous '+query,[['Command','Left Shift','Find']],[['ref',*first]])];current_mode=mode
  checks +=[ck('Mode shortcut prompt',['Find'],[['prompt',2]],mode=2),ck('Preserve typed query',typekeys('faith works'),[['type','faith works']],mode=2),ck('Reverse mode shortcut',[['Left Shift','Tab']],[['search-mode',2]],mode=2),ck('Forward mode shortcut',['Tab'],[['search-mode',0]],mode=2),ck('Cancel mode selection',['Escape'],[['escape']]),ck('Wildcard error prompt',['Find'],[['prompt',2]],mode=2),ck('Reject infix wildcard',typekeys('go*d')+['Enter'],[['notice','Use 1-8 words; Esc returns']],mode=3),ck('Dismiss wildcard error',['Escape'],[['escape']])]
 if a.quick:checks=checks[:10]
 checks[0]['font_height']=height
 (out/'config.json').write_text(json.dumps(dict(version=a.version,applet=stem+'.OS3KApp',all_vendor_fonts=a.all_vendor_fonts,lcd_roll=a.lcd_roll),indent=2)+'\n')
 if a.all_vendor_fonts and not a.quick and not a.benchmark:
  for i in range(6 if a.no_terminal_font else 7):
   checks +=[ck('Installed font entry '+str(i),[['Left Ctrl','Left Alt','Command','F'],'Home']+['Down']*i+['Enter'],[['reflow']],font_entry=i),ck('Scroll installed font '+str(i),['Down']*16,[['move','Down',False]]*16)]
  checks +=[ck('Leave demo in Small font',[['Left Ctrl','Left Alt','Command','F'],'Home']+['Down']*(1 if a.no_terminal_font else 2)+['Enter'],[['reflow']])]
 if a.readthrough:
  assert not a.production and not vendor and not a.all_vendor_fonts,'read-through profiles system 6x16'
  chapter=ch(19,119);ls,_=lines_for([c for b in books for c in b['chapters']][chapter],1,0,1,[6]*256);last=len(ls)-1
  checks=[ck('Initial Genesis',actions=[['ref',0,1,0]],font_height=16),ref_case('Load Psalm119',19,119,1)]
  if a.readthrough=='line':checks +=[move_case('Readthrough '+str(i),'Down')for i in range(1,last+1)]
  else:
   checks +=[ck('Readthrough '+str(i),['N'],[['page',1]])for i in range(1,last//4+1)]
   checks +=[move_case('Finish page cursor '+str(i),'Down')for i in range(last%4)]
  checks +=[move_case('Finish at EOF','End'),ck('Pure chapter decode',['T'],[['resume']])]
  (out/'readthrough.json').write_text(json.dumps(dict(reader='streaming-roll'if a.lcd_roll else'streaming',version=a.version,mode=a.readthrough,work=a.work_profile,wrapped_lines=len(ls),source_bytes=sum(len(v)+1 for v in [c for b in books for c in b['chapters']][chapter])),indent=2))
 (out/'checks.json').write_text(json.dumps(checks,indent=2));script='local lcd_module='+repl.lua(str(HERE/'NeoLCD.lua'))+'\nlocal capture_directory='+repl.lua(str(out))+'\nlocal checks='+repl.lua(checks)+'\nlocal work_offset='+str(sym.get('g_decode_work',0x80000000)-0x80000000)+'\nlocal work_enabled='+('true'if a.work_profile else'false')+'\nlocal reader_offset='+str(sym['g_stream']-0x80000000)+'\nlocal font_offset='+str(sym['stream_font']-0x80000000)+'\nlocal uifont_offset='+str(sym['ui_font']-0x80000000)+'\n'+(HERE/'BibleStreamHarness.lua').read_text();(out/'run.lua').write_text(script)
 launcher='#!/usr/bin/env bash\nset -euo pipefail\ndemo_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\nsession="$(mktemp -d /tmp/neo-bible.XXXXXX)"\ncp -a "$demo_dir/roms" "$demo_dir/cfg" "$demo_dir/nvram" "$session/"\nexec '+shlex.quote(str(mame))+' asneo -rompath "$session/roms" -cfg_directory "$session/cfg" -nvram_directory "$session/nvram" -window -skip_gameinfo\n'
 (out/'launch.sh').write_text(launcher);(out/'launch.sh').chmod(0o755)
 (out/'manifest.json').write_text(json.dumps([dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in images+[APP/'Streaming.c',APP/'HuffmanDecoder.c',HERE/'BibleStreamHarness.lua',Path(__file__),mame]],indent=2))
 with(out/'mame.log').open('w')as log:r=subprocess.run([str(mame),'asneo','-rompath',str(out/'roms'),'-nvram_directory',str(out/'nvram'),'-cfg_directory',str(out/'cfg'),'-video','none','-sound','none','-nothrottle','-autoboot_delay','0','-autoboot_script',str(out/'run.lua'),'-seconds_to_run','1000'],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,SDL_VIDEODRIVER='dummy'),timeout=800)
 log=(out/'mame.log').read_text();assert r.returncode==0 and 'PASS BibleReader suite'in log and 'FAIL BibleReader'not in log,log[-1600:];verify(out)
def verify(out):
 books=json.loads((out/'source.json').read_bytes());config=json.loads((out/'config.json').read_text())if(out/'config.json').exists()else dict(version='KJV',applet='BibleReader-Stream.OS3KApp');model=Model(books,config['version']);model.lcd_roll=config.get('lcd_roll',False);checks=json.loads((out/'checks.json').read_text());reports=[]
 for i,c in enumerate(checks,1):
  f=captured_font(out,i);model.setfont(f);model.ui=captured_font(out,i,'uifont')
  firmware=(ROOT/'Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos').read_bytes();assert(out/f'uifont-{i:02}.bin').read_bytes()==firmware[0x44af8e-0x410000:0x44af8e-0x410000+16],('UI must use the original firmware system font')
  if i==1:initial_font=f
  if c['name']=='Leave demo in Small font':assert f['height']==11,('demo must finish in original Small font')
  if c.get('font_height'):assert f['height']==c['font_height'],('requested installed font must actually be active')
  if c['name']=='Re-select vendor font':assert(f['height'],f['widths'],f['glyphs'])==(initial_font['height'],initial_font['widths'],initial_font['glyphs']),('native picker selected original vendor font')
  for action in c['actions']:
   a,*args=action
   if a=='ref':model.reset(args)
   elif a=='move':model.mov(*args)
   elif a=='copy':model.copy()
   elif a=='escape':model.sel=False;model.mode=0;model.roll=0
   elif a=='page':model.page(*args)
   elif a in ['start','end']:
    shift=args[0];old=model.anchor if model.sel else model.caret;model.reset((model.ref[0],1,0));model.row=len(model.lines)-1 if a=='end'else 0;model.top=max(0,model.row-model.rows+1);model.caret=model.lines[model.row]['end']if a=='end'else 0;model.anchor=old if shift else model.caret;model.anchor_row=next((i for i,l in enumerate(model.lines)if l['start']<=old<=l['end']),0)if shift else model.row;model.sel=shift
   elif a=='all':model.ref=(model.ref[0],1,0);model.reset();model.row=len(model.lines)-1;model.top=max(0,model.row-model.rows+1);model.caret=model.lines[-1]['end'];model.anchor=0;model.anchor_row=0;model.sel=True
   elif a=='numbers':model.numbered=1-model.numbered;model.reset(offset=model.caret)
   elif a=='reflow':model.reset(offset=model.caret)
   elif a=='resume':
    if c['name']!='Pure chapter decode':model.roll=0
    model.mode=0;model.command=''
   elif a=='prompt':model.mode=args[0];model.command=''
   elif a=='notice':model.mode=3;model.notice=args[0]
   elif a=='type':model.command=args[0]
   elif a=='search-mode':model.search_mode=args[0]
  if c.get('no_repaint'):assert struct.unpack('>35I',(out/f'stream-{i:02}.bin').read_bytes())[32]==0,(c['name'],'dialog opening must not repaint text')
  path=out/f'checkpoint-{i:02}.lcd.json';lcd_frames(path);m=struct.unpack('>35I',(out/f'stream-{i:02}.bin').read_bytes());assert m[0]==0x42535452 and m[2]==4 and m[3]==0
  assert(m[4],m[5],m[11],m[21])==(*model.ref[:2],model.numbered,model.ref[2]),(c['name'],'reference',m[:22],model.ref)
  expected=(model.top,model.caret,model.anchor,int(model.sel and model.anchor!=model.caret),min(263,model.x()),model.cursor_rect()[0],model.roll,model.stride,model.rows)
  assert tuple(m[22:31])==expected,(c['name'],'independent cursor/selection/roll',tuple(m[22:31]),expected)
  assert m[34]==model.cursor_rect()[1],(c['name'],'native caret segment')
  cursor=json.loads((out/f'cursor-{i:02}.json').read_text());assert(cursor['x'],cursor['y'])==(expected[4],(expected[5]+model.roll)%64);
  if model.lcd_roll:
   samples=json.loads(path.read_text())['samples'];assert all(ctrl['m_start_line']==model.roll for sample in samples for ctrl in sample['controllers']),(c['name'],'LCD controller start-line')
  assert cursor['mode']==(12 if model.mode else 15)
  if c.get('clipboard'):assert(out/f'clipboard-{i:02}.bin').read_bytes()==model.clip,(c['name'],'clipboard citation')
  if c.get('max_data_writes')is not None:assert json.loads((out/f'display-{i:02}.json').read_text())['writes']<=c['max_data_writes'],(c['name'],'only the changed character and native caret may be written')
  im=model.image();ref=out/f'expected-{i:02}.png';ImageChops.invert(im.convert('L')).save(ref);pixels=compare([path],ref,out/f'comparison-{i:02}',screen_size=(264,65))
  for sample in json.loads(path.read_text())['samples']:
   for ctrl in sample['controllers']:
    for key,value in dict(m_start_line=model.roll,m_display_on=1,m_adc=0,m_com_reverse=0,m_reverse=0,m_all_points=0,m_reset=0).items():assert ctrl[key]==value,(c['name'],key)
  reports.append(dict(name=c['name'],bitmap=pixels,top_line=m[22],caret=m[23],anchor=m[24],selection=m[25],roll=m[28],pitch=m[29],rows=m[30],lines_painted=m[32],roll_count=m[33],total_ms=m[16]-m[13],data_writes=json.loads((out/f'display-{i:02}.json').read_text())['writes']))
 font_entries=[];selected_vendors=set()
 for i,c in enumerate(checks,1):
  if 'font_entry'not in c:continue
  raw=(out/f'font-pixels-{i:02}.bin').read_bytes();matches=[p.stem for p in(out/'artifacts').glob('neofont*.os3kapp')if raw in p.read_bytes()]
  assert len(matches)<=1,('ambiguous vendor font identity',matches)
  selected_vendors.update(matches);font_entries.append(dict(entry=c['font_entry'],height=captured_font(out,i)['height'],vendor=matches[0]if matches else None))
 if config.get('all_vendor_fonts')and font_entries:
  assert selected_vendors=={'neofontsmall','neofontmedium','neofontlarge','neofontvlarge','neofontxlarge'},('every original vendor font must actually be selected',selected_vendors)
 image=(out/'artifacts'/config['applet']).read_bytes();assert image[23]==0 and struct.unpack_from('>H',image,20)[0]==0xFF22
 if config['version']!='KJV':assert image[24:60].split(b'\0')[0].decode()==Path(config['applet']).stem
 (out/'results.json').write_text(json.dumps(dict(status='passed',version=config['version'],rom_bytes=len(image),static_ram_bytes=struct.unpack_from('>I',image,8)[0],file_count=0,installed_font_entries=font_entries,results=reports),indent=2)+'\n');print('PASS',len(reports),'streaming viewer checks')
if __name__=='__main__':main()
