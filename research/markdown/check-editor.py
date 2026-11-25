#!/usr/bin/env python3
"""Original AlphaWord, hidden companion, exact independent bitmap/state checks."""
import argparse,hashlib,importlib.util,json,os,shutil,struct,subprocess,sys
from pathlib import Path
from PIL import Image,ImageChops
here=Path(__file__).resolve().parent;root=here.parents[2];tests=root/'betawise/tests/mame/asneo';sys.path.insert(0,str(tests))
from check import prepare_session
from screen_bitmap import compare
ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--live',action='store_true');ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--case',choices=['style','padding','keyboard','preview','paste','live','wrap','backspace','repeat','hidden','profile','lists','blocks','selection','underscore','code','shortcuts','demo'],default='style');a=ap.parse_args()
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
with(out/'build.log').open('w')as log:subprocess.run(['make','-C',str(here)]+(['hook'if a.case=='shortcuts'else'live']if a.live else []),stdout=log,stderr=subprocess.STDOUT,check=True)
fw=root/'Ghidra/Alphasmart Neo/SmartApplets';mame=root/'mame/neodiag';prepare_session(out,fw,'extra',mame)
flash=bytearray((out/'nvram/asneo/flashnv').read_bytes());flash[0x70000:]=b'\xff'*(len(flash)-0x70000);offset=0x70000
(out/'artifacts').mkdir()
for p in [fw/'alphawordplus.os3kapp',here/('MarkdownFont.OS3KApp'if a.live else'FontProbe.OS3KApp'),here/('BeamerHookProbe.OS3KApp'if a.case=='shortcuts'else'LiveMarkdown.OS3KApp'if a.live else'EditorProbe.OS3KApp')]:
 b=bytearray(p.read_bytes())
 if a.case=='shortcuts' and p.name=='BeamerHookProbe.OS3KApp':
  assert struct.unpack_from('>H',b,20)[0]==0xFF14
  # Only this disposable copy impersonates the vendor Beamer callback target.
  struct.pack_into('>H',b,20,0xA006)
 flash[offset:offset+len(b)]=b;offset+=len(b);(out/'artifacts'/p.name).write_bytes(b)
 if a.case=='shortcuts' and p.name=='BeamerHookProbe.OS3KApp':
  (out/'packaged-BeamerHookProbe.OS3KApp').write_bytes(p.read_bytes())
  (out/'applet-id-alias.json').write_text(json.dumps(dict(packaged_id=0xFF14,disposable_id=0xA006,reason='Original AlphaWord Beamer lookup compatibility fixture'),indent=2)+'\n')
(out/'nvram/asneo/flashnv').write_bytes(flash)
if a.prepare_only:
 print('Prepared interactive prototype:',out);sys.exit(0)
symbols={line.split()[2]:int(line.split()[0],16)&0x7fffffff for line in subprocess.check_output(['m68k-linux-gnu-nm',str(here/('BeamerHookProbe.elf'if a.case=='shortcuts'else'LiveMarkdown.elf'if a.live else'EditorProbe.elf'))],text=True).splitlines()if len(line.split())==3}
hot=['Left Ctrl','Left Alt','M']
def typing(s):
 mapping={'*':['Left Shift','8'],'#':['Left Shift','3'],'>':['Left Shift','Period'],'+':['Left Shift','Equals'],'_':['Left Shift','Minus'],' ':'Space','\n':'Enter','\\':'Backslash','`':'Grave','-':'Minus','.':'Period',')':['Left Shift','0'],'(' :['Left Shift','9']}
 return [mapping.get(c,c.upper())for c in s]

def check(name,keys,command=0,**kw):return dict(name=name,keys=keys+[hot],command=command,**kw)
if a.case=='demo':
 assert a.live
 checks=[]
 demo_source=''
 def demo(name,keys,addition,render):
  global demo_source
  demo_source+=addition
  checks.append(dict(name=name,keys=keys,command=11,automatic=True,text=demo_source,render=render))
 title=[('neo writing',1)]
 demo('a heading at the current font size',typing('# neo writing'),'# neo writing',title)
 demo('Start a paragraph',['Enter']+typing('a '),'\ra ',title+[('\ra ',0)])
 demo('Type a bold opener',typing('**bold'),'**bold',title+[('\ra **',0),('bold',1)])
 demo('Close the bold span',typing('**'),'**',title+[('\ra ',0),('bold',1)])
 demo('Continue in regular text',['End']+typing(' and '),' and ',title+[('\ra ',0),('bold',1),(' and ',0)])
 demo('Type an italic opener',typing('*italic'),'*italic',title+[('\ra ',0),('bold',1),(' and *',0),('italic',2)])
 body=title+[('\ra ',0),('bold',1),(' and ',0),('italic',2)]
 demo('Close the italic span',typing('*'),'*',body)
 body=body+[('.',0)]
 demo('Continue after emphasis',['End']+typing('.'),'.',body)
 demo('Keep literal list markers',['Enter']+typing('- first item'),'\r- first item',body+[('\r- first item',0)])
 complete=body+[('\r- first item\r- second item',0)]
 demo('Enter continues the list',['Enter']+typing('second item'),'\r- second item',complete)
 # Source visibility retains heading style on its prefix as well as its text.
 # live_plan's heading base applies to the full line; only hiding is toggled.
 checks.append(dict(name='Reveal the original Markdown',keys=[hot],command=11,automatic=True,text=demo_source,render=[('# neo writing',1),('\ra **',0),('bold',1),('** and *',0),('italic',2),('*.\r- first item\r- second item',0)]))
 checks.append(dict(name='Return to styled writing',keys=[hot],command=10,automatic=True,text=demo_source,render=complete))
 checks.append(dict(name='Copy preserves the complete Markdown source',keys=[['Left Ctrl','A'],['Left Ctrl','C']],command=11,automatic=True,text=demo_source,clip=demo_source,selection=True))
elif a.case=='shortcuts':
 assert a.live
 checks=[dict(name='Ctrl B invokes hidden ID A006 receive',keys=typing('source')+[['Left Ctrl','B']],command=0,text='source',preview=0,reply_message=0x1000003,render=[('source',0)]),
 dict(name='Ctrl Send invokes hidden ID A006 send',keys=[['Left Ctrl','Send']],command=0,text='source',preview=0,reply_message=0x1000001,render=[('source',0)])]
elif a.case=='underscore':
 assert a.live
 text='_italic_ __bold__ ___both___'
 rendered=[('italic',2),(' ',0),('bold',1),(' ',0),('both',3)]
 checks=[dict(name='underscore emphasis',keys=typing(text),command=11,automatic=True,text=text,render=rendered),
 dict(name='intraword underscores stay literal',keys=['Enter']+typing('snake_case_name'),command=11,automatic=True,text=text+'\rsnake_case_name',render=rendered+[('\rsnake_case_name',0)]),
 dict(name='underscore source copied',keys=[['Left Ctrl','A'],['Left Ctrl','C']],command=11,automatic=True,text=text+'\rsnake_case_name',clip=text+'\rsnake_case_name',selection=True),
 dict(name='underscore source deleted entirely',keys=['Delete'],command=11,automatic=True,text='',empty_file=True,render=[]),
 dict(name='mixed markers',keys=typing('**bold _both_ bold**'),command=11,automatic=True,text='**bold _both_ bold**',render=[('bold ',1),('both',3),(' bold',1)])]
 for run,face in [(1,2),(2,1),(3,3)]:
  word='_'*run+'a'+'_'*run
  checks.extend([dict(name='underscore single-letter '+str(run),keys=['File '+str(run+1)]+typing(word),command=11,automatic=True,text=word,render=[('a',face)]),dict(name='erase underscore span '+str(run),keys=['Backspace'],command=11,automatic=True,text='',empty_file=True,render=[])])
 checks.append(dict(name='escaped and intraword underscores remain literal',keys=typing('\\_literal_ foo_bar __bold__'),command=11,automatic=True,text='\\_literal_ foo_bar __bold__',render=[('\\_literal_ foo_bar ',0),('bold',1)]))
elif a.case=='code':
 assert a.live
 checks=[dict(name='inline backticks suppress emphasis',keys=typing('`**literal** _literal_`'),command=11,automatic=True,text='`**literal** _literal_`',render=[('`**literal** _literal_`',0)]),
 dict(name='fence begins',keys=['File 2']+typing('```'),command=11,automatic=True,text='```',render=[('```',0)]),
 dict(name='fenced emphasis stays literal',keys=['Enter']+typing('**literal** _literal_'),command=11,automatic=True,text='```\r**literal** _literal_',render=[('```\r**literal** _literal_',0)]),
 dict(name='fenced list stays literal',keys=['Enter']+typing('* item'),command=11,automatic=True,text='```\r**literal** _literal_\r* item',render=[('```\r**literal** _literal_\r* item',0)]),
 dict(name='Enter in fence does not continue list',keys=['Enter']+typing('```'),command=11,automatic=True,text='```\r**literal** _literal_\r* item\r```',render=[('```\r**literal** _literal_\r* item\r```',0)]),
 dict(name='emphasis resumes after fence',keys=['Enter']+typing('__bold__'),command=11,automatic=True,text='```\r**literal** _literal_\r* item\r```\r__bold__',render=[('```\r**literal** _literal_\r* item\r```\r',0),('bold',1)])]
elif a.case=='selection':
 assert a.live
 source='**bold** *italic* ***both***'
 checks=[dict(name='hidden mixed emphasis',keys=typing(source),command=11,automatic=True,text=source,render=[('bold',1),(' ',0),('italic',2),(' ',0),('both',3)]),
 dict(name='select all source',keys=[['Left Ctrl','A']],command=11,automatic=True,text=source,selection=True),
 dict(name='delete all includes hidden markers',empty_file=True,keys=['Delete'],command=11,automatic=True,text='',render=[]),
 dict(name='retype after full deletion',keys=typing('new'),command=11,automatic=True,text='new',render=[('new',0)]),
 dict(name='select all Backspace',keys=[['Left Ctrl','A'],'Backspace'],command=11,automatic=True,text='',empty_file=True,render=[]),
 dict(name='bullet and hidden emphasis',keys=typing('* **item**'),command=11,automatic=True,text='* **item**',render=[('* ',0),('item',1)]),
 dict(name='delete bullet source and display glyph',keys=[['Left Ctrl','A'],'Delete'],command=11,automatic=True,text='',empty_file=True,render=[]),
 dict(name='heading and nested emphasis',keys=typing('# *title*'),command=11,automatic=True,text='# *title*',render=[('title',3)]),
 dict(name='delete hidden heading source',keys=[['Left Ctrl','A'],'Delete'],command=11,automatic=True,text='',empty_file=True,render=[]),
 dict(name='prepare complete cut',keys=typing(source),command=11,automatic=True,text=source,render=[('bold',1),(' ',0),('italic',2),(' ',0),('both',3)]),
 dict(name='cut all keeps Markdown on clipboard',keys=[['Left Ctrl','A'],['Left Ctrl','X']],command=11,automatic=True,text='',empty_file=True,clip=source,render=[]),
 dict(name='paste complete Markdown after cut',keys=[['Left Ctrl','V']],command=11,automatic=True,text=source,render=[('bold',1),(' ',0),('italic',2),(' ',0),('both',3)]),
 dict(name='delete reverse whole-source selection',keys=['End',['Left Shift','Home'],'Delete'],command=11,automatic=True,text='',empty_file=True,render=[]),
 dict(name='literal asterisks stay literal',keys=typing('keep ****'),command=11,automatic=True,text='keep ****',render=[('keep ****',0)]),
 dict(name='partial plain deletion preserves literal asterisks',keys=['Home']+[['Left Shift','Right']]*4+['Delete'],command=11,automatic=True,text=' ****',caret_chars=0,render=[(' ****',0)]),
 dict(name='delete all in source-visible mode',keys=[['Left Ctrl','A'],'Delete'],command=10,automatic=True,text='',empty_file=True,render=[]),
 dict(name='reopen remains genuinely empty',keys=['File 2','File 1'],command=11,automatic=True,text='',empty_file=True,render=[])]
elif a.case=='lists':
 assert a.live
 checks=[dict(name='hyphen bullet',keys=typing('- first'),command=11,automatic=True,text='- first',render=[('- first',0)]),
 dict(name='continue bullet on Enter',keys=['Enter']+typing('second'),command=11,automatic=True,text='- first\r- second',render=[('- first\r- second',0)]),
 dict(name='empty bullet on next line',keys=['Enter'],command=11,automatic=True,text='- first\r- second\r- ',render=[('- first\r- second\r- ',0)]),
 dict(name='Enter exits empty bullet',keys=['Enter'],command=11,automatic=True,text='- first\r- second\r',render=[('- first\r- second\r',0)]),
 dict(name='bullet Markdown source copied',keys=[['Left Ctrl','A'],['Left Ctrl','C']],command=11,automatic=True,text='- first\r- second\r',clip='- first\r- second\r',selection=True),
 dict(name='asterisk bullet with emphasis',keys=['File 2']+typing('* **bold**'),command=11,automatic=True,text='* **bold**',render=[('* ',0),('bold',1)]),
 dict(name='delete literal bullet marker',caret_chars=0,keys=['Home','Right','Backspace'],command=11,automatic=True,text=' **bold**',render=[(' ',0),('bold',1)]),
 dict(name='ordered list',keys=['File 3']+typing('9. nine'),command=11,automatic=True,text='9. nine',render=[('9. nine',0)]),
 dict(name='ordered list increments across digit boundary',keys=['Enter']+typing('ten'),command=11,automatic=True,text='9. nine\r10. ten',render=[('9. nine\r10. ten',0)]),
 dict(name='empty numbered item',keys=['Enter'],command=11,automatic=True,text='9. nine\r10. ten\r11. ',render=[('9. nine\r10. ten\r11. ',0)]),
 dict(name='exit empty numbered item',keys=['Enter'],command=11,automatic=True,text='9. nine\r10. ten\r',render=[('9. nine\r10. ten\r',0)]),
 dict(name='indented plus bullet',keys=['File 4']+typing('  + indented'),command=11,automatic=True,text='  + indented',render=[('  + indented',0)]),
 dict(name='continued indent and marker preserved',keys=['Enter']+typing('next'),command=11,automatic=True,text='  + indented\r  + next',render=[('  + indented\r  + next',0)]),
 dict(name='bullet source view',keys=[hot],command=11,automatic=True,text='  + indented\r  + next',render=[('  + indented\r  + next',0)]),
 dict(name='bullet rendered view restored',keys=[hot],command=10,automatic=True,text='  + indented\r  + next',render=[('  + indented\r  + next',0)]),
 dict(name='plus source copied',keys=[['Left Ctrl','A'],['Left Ctrl','C']],command=11,automatic=True,text='  + indented\r  + next',clip='  + indented\r  + next',selection=True)]
elif a.case=='blocks':
 assert a.live
 checks=[dict(name='heading is bold at native size',keys=typing('# title'),command=11,automatic=True,text='# title',render=[('title',1)]),
 dict(name='heading with italic emphasis',keys=typing(' *both*'),command=11,automatic=True,text='# title *both*',render=[('title ',1),('both',3)]),
 dict(name='heading ends at hard newline',keys=['Enter']+typing('plain'),command=11,automatic=True,text='# title *both*\rplain',render=[('title ',1),('both',3),('\rplain',0)]),
 dict(name='blockquote',keys=['Enter']+typing('> quoted'),command=11,automatic=True,text='# title *both*\rplain\r> quoted',render=[('title ',1),('both',3),('\rplain\r> ',0),('quoted',2)])]
elif a.case=='profile':
 assert a.live
 checks=[]
 for size in [50,500,1500]:
  text=('word '*300)[:size]
  checks.append(dict(name='seed '+str(size),keys=[hot],command=12,seed=size,text=text[:255],full_text=text))
  checks.append(dict(name='type after '+str(size),keys=typing('a'),command=11,automatic=True,text=(text+'a')[:255],full_text=text+'a'))
  checks.append(dict(name='steady typing after '+str(size),keys=typing('bc'),command=11,automatic=True,text=(text+'abc')[:255],full_text=text+'abc'))
elif a.case=='hidden':
 assert a.live
 checks=[dict(name='unmatched bold stays visible',keys=typing('**word'),command=11,automatic=True,text='**word',render=[('**',0),('word',1)]),
 dict(name='matched bold delimiters hidden',keys=typing('**'),command=11,automatic=True,text='**word**',render=[('word',1)]),
 dict(name='hidden source plain copy',keys=[['Left Ctrl','A'],['Left Ctrl','C']],command=11,automatic=True,text='**word**',clip='**word**',selection=True),
 dict(name='backspace skips hidden closing markers',keys=['End','Backspace'],command=11,automatic=True,text='**wor**',render=[('wor',1)]),
 dict(name='retype inside hidden bold pair',keys=typing('d'),command=11,automatic=True,text='**word**',render=[('word',1)]),
 dict(name='type regular after hidden bold',keys=['End']+typing(' plain *italic*'),command=11,automatic=True,text='**word** plain *italic*',render=[('word',1),(' plain ',0),('italic',2)]),
 dict(name='toggle source markers visible',keys=[hot],command=11,automatic=True,text='**word** plain *italic*',render=[('**',0),('word',1),('** plain *',0),('italic',2),('*',0)]),
 dict(name='toggle completed markers hidden',keys=[hot],command=10,automatic=True,text='**word** plain *italic*',render=[('word',1),(' plain ',0),('italic',2)]),
 dict(name='nested completed markers hidden',keys=['File 2']+typing('**bold *both* bold**'),command=11,automatic=True,text='**bold *both* bold**',render=[('bold ',1),('both',3),(' bold',1)]),
 dict(name='combined completed markers hidden',keys=['File 3']+typing('***both***'),command=11,automatic=True,text='***both***',render=[('both',3)])]
 for run,face in [(1,2),(2,1),(3,3)]:
  text='*'*run+'a'+'*'*run
  checks.extend([dict(name='one-letter hidden span '+str(run),keys=['File '+str(run+3)]+typing(text),command=11,automatic=True,text=text,render=[('a',face)]),
   dict(name='delete last visible letter '+str(run),keys=['Backspace'],command=11,automatic=True,text='',render=[])])
elif a.case=='repeat':
 assert a.live
 checks=[check('native held Backspace baseline',typing('abc')+[dict(names=['Backspace'],frames=120)],0,text='',render=[]),
 dict(name='live held Backspace',keys=typing('abc')+[dict(names=['Backspace'],frames=120)],command=10,automatic=True,text='',render=[])]
elif a.case=='backspace':
 assert a.live
 checks=[dict(name='type one character',keys=typing('a'),command=10,automatic=True,text='a',render=[('a',0)]),
 dict(name='backspace to empty',keys=['Backspace'],command=10,automatic=True,text='',render=[]),
 dict(name='retype after empty',keys=typing('**a'),command=10,automatic=True,text='**a',render=[('**',0),('a',1)]),
 dict(name='backspace unclosed bold content',keys=['Backspace'],command=10,automatic=True,text='**',render=[('**',0)]),
 dict(name='backspace marker',keys=['Backspace'],command=10,automatic=True,text='*',render=[('*',0)]),
 dict(name='backspace last marker',keys=['Backspace'],command=10,automatic=True,text='',render=[])]
elif a.case=='wrap':
 assert a.live
 text='word '*12
 # Explicit expected line break: nine 27-pixel words fit; the tenth wraps.
 rows='word '*9+'\n'+'word '*3
 checks=[dict(name='wrap onto second display line',keys=typing(text),command=10,automatic=True,text=text,render=[(rows,0)]),
 dict(name='bold after soft wrap',keys=typing('**bold**'),command=10,automatic=True,text=text+'**bold**',render=[(rows+'**',0),('bold',1),('**',0)]),
 dict(name='backspace after wrapped closing delimiter',keys=['Backspace'],command=10,automatic=True,text=text+'**bold*',render=[(rows+'**',0),('bold',1),('*',0)]),
 dict(name='hidden bold spans two wrapped lines',keys=['File 3']+typing('**'+text+'**'),command=11,automatic=True,text='**'+text+'**',render=[(rows,1)]),
 dict(name='copy source containing soft wrap bytes',keys=[['Left Ctrl','A'],['Left Ctrl','C']],command=11,automatic=True,text='**'+text+'**',clip='**'+text+'**',selection=True),
 dict(name='edit on second wrapped bold line',keys=['End','Backspace'],command=11,automatic=True,text='**'+text[:-1]+'**',render=[(rows[:-1],1)]),
 dict(name='held Backspace clears across soft wrap',keys=[dict(names=['Backspace'],frames=800)],command=11,automatic=True,text='',render=[])]
elif a.case=='live':
 assert a.live,'--case live requires --live'
 checks=[check('live bold opener',typing('**bold'),10,text='**bold',render=[('**',0),('bold',1)]),
 check('close bold and type regular',typing('** plain '),10,text='**bold** plain ',render=[('**',0),('bold',1),('** plain ',0)]),
 check('live italic',typing('*italic* '),10,text='**bold** plain *italic* ',render=[('**',0),('bold',1),('** plain *',0),('italic',2),('* ',0)]),
 check('live combined',typing('***both***'),10,text='**bold** plain *italic* ***both***',render=[('**',0),('bold',1),('** plain *',0),('italic',2),('* ***',0),('both',3),('***',0)]),
 check('edit closing delimiter',['Backspace'],10,text='**bold** plain *italic* ***both**',render=[('**',0),('bold',1),('** plain *',0),('italic',2),('* ***',0),('both',3),('**',0)]),
 check('type after changed delimiter',typing('x'),10,text='**bold** plain *italic* ***both**x',render=[('**',0),('bold',1),('** plain *',0),('italic',2),('* ***',0),('both',3),('**',0),('x',2)])]
 for c in checks:
  c['automatic']=True;c['keys']=c['keys'][:-1]
 checks.extend([
 dict(name='move and copy native bold selection',keys=['Home','Right','Right']+[['Left Shift','Right']]*4+[['Left Ctrl','C']],command=10,automatic=True,text='**bold** plain *italic* ***both**x',clip='bold',selection=True),
 dict(name='edit within bold span',keys=['Home']+['Right']*6+['Backspace',['Left Shift','D']],command=10,automatic=True,text='**bolD** plain *italic* ***both**x',render=[('**',0),('bolD',1),('** plain *',0),('italic',2),('* ***',0),('both',3),('**',0),('x',2)]),
 dict(name='reopen formatted document',keys=['File 2','File 1'],command=10,automatic=True,text='**bolD** plain *italic* ***both**x',render=[('**',0),('bolD',1),('** plain *',0),('italic',2),('* ***',0),('both',3),('**',0),('x',2)]),
 dict(name='copy exact Markdown source',keys=[['Left Ctrl','A'],['Left Ctrl','C']],command=10,automatic=True,text='**bolD** plain *italic* ***both**x',clip='**bolD** plain *italic* ***both**x',selection=True),
 dict(name='collapse selection and start new line',keys=['End','Enter']+typing('**new'),command=10,automatic=True,text='**bolD** plain *italic* ***both**x\r**new',render=[('**',0),('bolD',1),('** plain *',0),('italic',2),('* ***',0),('both',3),('**',0),('x',2),('\r**',0),('new',1)]),
 dict(name='line break resets emphasis',keys=['Enter']+typing('plain'),command=10,automatic=True,text='**bolD** plain *italic* ***both**x\r**new\rplain',render=[('**',0),('bolD',1),('** plain *',0),('italic',2),('* ***',0),('both',3),('**',0),('x',2),('\r**',0),('new',1),('\rplain',0)])])
 checks.append(dict(name='escaped asterisks and inline code remain literal',keys=['Enter']+typing('\\*literal\\* `**code**` ****plain'),command=10,automatic=True,text='**bolD** plain *italic* ***both**x\r**new\rplain\r\\*literal\\* `**code**` ****plain',render=[('**',0),('bolD',1),('** plain *',0),('italic',2),('* ***',0),('both',3),('**',0),('x',2),('\r**',0),('new',1),('\rplain\r\\*literal\\* `**code**` ****plain',0)]))
elif a.case=='style':
 checks=[check('literal source',typing('**word**'),text='**word**',x=64,render=[('**word**',0)]),
  check('safe native token insertion',[],2,text='**word**',x=64,render=[('**',0),('word',1),('**',0)]),
  check('caret enters styled word',['Home','Right','Right'],text='**word**',x=16,render=[('**',0),('word',1),('**',0)]),
  check('native selection copy',[['Left Shift','Right']]*4+[['Left Ctrl','C']],7,text='**word**',clip='word',selection=True,x=48),
  check('edit a styled letter',['End','Left','Left','Backspace',['Left Shift','W']],text='**worW**',render=[('**',0),('worW',1),('**',0)]),
  check('leave style and type',['End',['Left Shift','1']],text='**worW**!',render=[('**',0),('worW',1),('**!',0)]),
  check('switch files and reopen',['File 2','File 1'],text='**worW**!',render=[('**',0),('worW',1),('**!',0)]),
  check('shortcut opens preview',[],5,text='**worW**!',preview=1,render=[('worW!',1)]),
  check('shortcut returns to AlphaWord',[],6,text='**worW**!',preview=0,render=[('**',0),('worW',1),('**!',0)]),
  check('plain clipboard preserves Markdown',[['Left Ctrl','A'],['Left Ctrl','C']],7,text='**worW**!',clip='**worW**!',selection=True)]
elif a.case=='padding':
 checks=[check('literal padding',typing('   word   '),text='   word   ',x=80,render=[('   word   ',0)]),
  check('same-size token replacement',[],4,text='word',same_size=True,render=[('word',1)]),
  check('native movement through tokens',['Home','Right','Right','Right','Right'],text='word',x=32,render=[('word',1)]),
  check('copy formatted word',[['Left Ctrl','A'],['Left Ctrl','C']],7,text='word',clip='word',selection=True),
  check('collapse selection and reopen',['End','File 2','File 1'],text='word',render=[('word',1)])]
elif a.case=='preview':
 checks=[check('literal source',typing('**word**'),text='**word**',render=[('**word**',0)]),check('shortcut preview',[],9,text='**word**',preview=1,render=[('word',1)]),check('return to unmodified source',[],9,text='**word**',preview=0,render=[('**word**',0)])]
elif a.case=='paste':
 checks=[check('prepare encoded clipboard',[],8,text='',render=[]),check('native paste of encoded tokens',[['Left Ctrl','V']],text='word',render=[('word',1)])]
else:checks=[check('companion keyboard bytes are escaped',[],3,raw_keyboard=True)]
if a.live:
 profile=json.loads((here/'markdown-font.json').read_text())
 for c in checks:
  if 'render' not in c:continue
  count=c.get('caret_chars',6 if c['name'] in ['edit within bold span','reopen formatted document'] else sum(len(t)for t,_ in c['render']))
  x=y=seen=0
  for text,face in c['render']:
   for ch in text:
    if seen==count:break
    if ch in '\r\n':x=0;y+=12
    else:x+=profile[face]['widths'][ord(ch)]
    seen+=1
  c['x']=x;c['y']=y
 if a.case=='live':checks[6]['x']=sum(profile[f]['widths'][ord(ch)] for text,f in [('**',0),('bold',1)] for ch in text);checks[6]['y']=0
# References are authored from input strings + independently transformed source
# glyph pixels before the emulator runs; never derived from a failed capture.
source=Image.open(root/'betawise/tests/fonts/fixtures/glyphs.png').convert('L')
for index,c in enumerate(checks,1):
 if 'render'not in c:continue
 ref=Image.new('1',(264,64));px=ref.load();x=0;yline=0
 profile=json.loads((here/'markdown-font.json').read_text())if a.live else None
 for text,face in c['render']:
  for ch in text:
   if a.live and ch in '\r\n':x=0;yline+=12;continue
   if a.live:
    glyph=profile[face]['glyphs'][ord(ch)];w=profile[face]['widths'][ord(ch)]
    if x+w>264:x=0;yline+=12
    for yy,row in enumerate(glyph):
     for xx,bit in enumerate(row):
      if bit=='1' and yline+yy<64:px[x+xx,yline+yy]=1
    x+=w;continue
   for y in range(8):
    for dx in range(6):
     if source.getpixel((ord(ch)*6+dx,y))<128:
      xx=x+dx+((7-y)//3 if face&2 else 0)
      if xx<x+8:px[xx,y]=1
      if face&1 and xx+1<x+8:px[xx+1,y]=1
   x+=8
 ImageChops.invert(ref.convert('L')).save(out/f'expected-{index:02d}.png')
(out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
def lua(v):
 if isinstance(v,str):return json.dumps(v,ensure_ascii=False)
 if isinstance(v,bool):return 'true'if v else'false'
 if isinstance(v,(int,float)):return str(v)
 if isinstance(v,(list,tuple)):return '{'+','.join(lua(x)for x in v)+'}'
 if isinstance(v,dict):return '{'+','.join('['+lua(k)+']='+lua(x)for k,x in v.items())+'}'
 raise TypeError(v)
script='local lcd_module='+lua(str(tests/'NeoLCD.lua'))+'\nlocal capture_directory='+lua(str(out))+'\nlocal font_height='+str(12 if a.live else 8)+'\nlocal probe_offset='+str(symbols['g_probe'])+'\nlocal private_probe_id='+str(0xFF11 if a.live else 0xFF10)+'\nlocal shortcut_mode='+lua(a.case=='shortcuts')+'\nlocal perf_offset='+str(symbols.get('g_perf',0))+'\nlocal seed_offset='+str(symbols.get('g_seed_length',0))+'\nlocal checks='+lua(checks)+'\n'+(here/'EditorHarness.lua').read_text()
(out/'run.lua').write_text(script)
with(out/'mame.log').open('w')as log:subprocess.run(list(map(str,[mame,'asneo','-rompath',out/'roms','-nvram_directory',out/'nvram','-cfg_directory',out/'cfg','-video','none','-sound','none','-nothrottle','-seconds_to_run','300','-autoboot_delay','0','-autoboot_script',out/'run.lua'])),stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'SDL_VIDEODRIVER':'dummy'},timeout=180,check=True)
log=(out/'mame.log').read_text();assert 'PASS AlphaWord companion editor suite'in log and 'FAIL 'not in log,log[-1800:]
results=[]
for i,c in enumerate(checks,1):
 raw_probe=(out/f'probe-{i:02d}.bin').read_bytes();n=int.from_bytes(raw_probe[68:72],'big')
 r=dict(name=c['name'],source_hex=raw_probe[92:92+n].hex(),state=json.loads((out/f'state-{i:02d}.json').read_text()))
 if 'render'in c:r['bitmap']=compare([out/f'checkpoint-{i:02d}.lcd.json'],out/f'expected-{i:02d}.png',out/f'comparison-{i:02d}')
 if a.case=='lists':
  payload=(out/f'file-{i:02d}.bin').read_bytes();assert bytes([0xb0,0x95,0xb0])not in payload,'generated bullet escaped into file'
 if 'full_text'in c:
  raw=(out/f'file-{i:02d}.bin').read_bytes();st=r['state'];raw=raw[:st['gap_start']]+raw[st['gap_end']:]
  assert raw.replace(b'\x81',b' ')==c['full_text'].encode(),c['name']+' full source mismatch'
 results.append(r)
sources=[here/'EditorProbe.c',here/'EditorHarness.lua',Path(__file__),tests/'NeoLCD.lua']
sources+=([here/x for x in ['LiveMarkdown.c','live-markdown.inc','MarkdownFont.c','MarkdownGlyphs.h','markdown-font.json','build-markdown-font.py']]if a.live else[here/'FontProbe.c',here/'ProbeGlyphs.h'])
manifest=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in [*sources,*sorted((out/'artifacts').iterdir())]]
(out/'experiment-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS',a.case,len(checks),'checkpoints',out)
