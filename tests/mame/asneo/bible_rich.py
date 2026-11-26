"""Source-backed rich text and exact glyph/pixel validation; no image inference."""
import json
from pathlib import Path
import re
import struct
import sys
from PIL import Image, ImageChops
from bible_layout import captured_font, digits
from neo_reader import lcd_frames
from screen_bitmap import compare

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'betawise/applets/BibleWise'))
from convert_source import convert_text
from bible_fonts import FONT_FILES, private_bdf
sys.path.insert(0,str(ROOT/'betawise/os3k'))
from charsets import load as load_charset
PRIVATE_CHARSET=json.loads((ROOT/'betawise/os3k/charsets/neo-smallcaps.json').read_text())
PRIVATE_LETTERS={int(letter[style],16):(int(letter['canonical'],16),4|bit)
    for letter in PRIVATE_CHARSET['letters'] for style,bit in [('regular',0),('bold',2),('italic',1)]}
REGULAR_SLOTS={int(letter['italic'],16):int(letter['regular'],16)for letter in PRIVATE_CHARSET['letters']}
NATIVE_UNICODE=load_charset(ROOT/'betawise/os3k/charsets/neo-us.txt')



def private_font(out, index, profiles, check, rich=True):
    raw=(out/f'privatefont-pixels-{index:02}.bin').read_bytes()
    widths=list((out/f'privatefont-widths-{index:02}.bin').read_bytes())
    offsets=struct.unpack('>256H',(out/f'privatefont-offsets-{index:02}.bin').read_bytes())
    height=(out/f'privatefont-{index:02}.bin').read_bytes()[0]; bands=(height+7)//8
    glyphs=[raw[offsets[c]:offsets[c]+widths[c]*bands]for c in range(256)]
    if rich:
        sys.path.insert(0,str(ROOT/'betawise/fonts'))
        from fontgen import load
        expected=load(private_bdf(check['font_vendor']),'iso8859-1','blank')
        image=(out/'artifacts'/(FONT_FILES[check['font_vendor']]+'.OS3KApp')).read_bytes()
        assert raw in image, 'private glyphs must remain in provider ROM'
        for code in range(256):
            target=code
            glyph=expected[target]
            assert glyph.height==height and widths[code]==glyph.width, ('private BDF metrics',code)
            packed=bytes(sum(1<<(y%8)for y in range(band,min(band+8,height))if glyph.getpixel((x,y)))
                for band in range(0,height,8)for x in range(glyph.width))
            assert glyphs[code]==packed, ('private BDF bitmap',code,target)
    else:
        assert all(widths[c]==0 for c in range(256)if not 48<=c<=57), 'plain fonts have only superscripts'
        body=profiles[0];w=body['widths'][ord('H')];g=body['glyphs'][ord('H')]
        shift=min(next((y for y in range(body['height']) if any(g[y//8*w+x]>>(y%8)&1 for x in range(w))),0),body['height']-5)
        shift=4 if shift>=4 else shift
        assert height==min(body['height'],16), ('compact overlay height',height,body['height'])
        images=[p.read_bytes() for p in (out/'artifacts').glob('BibleWise*.OS3KApp')]
        assert any(raw in image for image in images), 'fallback digit bitmaps must be backed by applet ROM'
        for digit in range(10):
            expected=bytearray(4*bands)
            for x,column in enumerate(digits[digit]):
                for y in range(5):
                    if column>>y&1: expected[(shift+y)//8*4+x]|=1<<((shift+y)%8)
            assert widths[48+digit]==4 and glyphs[48+digit]==expected, ('superscript glyph',digit)
    return dict(height=height,widths=widths,glyphs=glyphs)


def tokens(raw):
    flags=0; i=0
    while i<len(raw):
        c=raw[i]
        if c in (0xb1,0xb2):
            assert i+2<len(raw)and raw[i+2]==c, ('native token',i)
            flags=flags|raw[i+1]if c==0xb1 else flags&~raw[i+1]
            i+=3;continue
        yield i,c,flags
        i+=1


def semantic(raw):
    body=[]; headings=[]; word=[]; styles=[]; header=[]
    def flush():
        if word:
            body.append((''.join(word),tuple(styles)));word.clear();styles.clear()
        if header:headings.append(''.join(header));header.clear()
    for offset,c,flags in tokens(raw):
        if c==0xad:c=ord('-')
        face=(flags>>2)&3
        if face==3 and 48<=c<=57:continue
        style=0
        if face==3:
            assert c in PRIVATE_LETTERS, ('unassigned private byte',offset,c)
            c,style=PRIVATE_LETTERS[c]
        elif face==1:style=2
        elif face==2:style=1
        if c in (13,32,0x81):flush()
        else:
            assert NATIVE_UNICODE[c] is not None, ('unrecognized native character',offset,c)
            word.append(chr(NATIVE_UNICODE[c]));styles.append(style)
    flush()
    return body,headings


def source_expected(version, book, chapter, rich=True):
    rows=json.loads((ROOT/f'betawise/applets/BibleWise/upstream/data/{version}/{version}.json').read_bytes())
    body=[];heads=[]
    for row in rows:
        _,b,ch,v=row['r'].split(':')
        if b!=book or int(ch)!=chapter:continue
        if 'h'in row:
            if row['h']==1 and row['t']==f'{book} {chapter}':continue
            title=re.sub(r'[\u0590-\u05ff]+\s*(?=[A-Za-z])','',row['t'])
            title=convert_text(title)
            body.extend((word,tuple([2]*len(word)))for word in title.split())
            continue
        for token in row['t'].split():
            flags=''.join(re.findall(r'\*([a-z]+)',token))
            text=convert_text(re.sub(r'\*[a-z]+','',token))
            # Bold/italic records survive absent faces; only private small-cap
            # glyph substitution depends on font support.
            style=sum(1<<i for i,f in enumerate('ibs')if f in flags and (i<2 or rich))
            for word in text.split():
                # Small caps affect letters, not punctuation. The native private
                # face replaces only the lower-case letters; capitals stay full.
                expected=[]
                for c in word:
                    expected.append(style if c.islower() else style&3)
                body.append((word,tuple(expected)))
    return body,heads


def render_native(raw, profiles, top_offset, width=252):
    """Render verified rich tokens; validate every firmware soft-wrap boundary."""
    all_tokens=list(tokens(raw)); height=profiles[0]['height'];lines=[[]];x=0;positions={};previous=0
    def advance():
        nonlocal x
        lines.append([]);x=0
    for i,(offset,c,flags)in enumerate(all_tokens):
        for pos in range(previous,offset+1): positions[pos]=(len(lines)-1,x)
        previous=offset+1
        if flags&1:continue
        if c==13:advance();continue
        if c==0x81:
            look=0
            for off,n,ff in all_tokens[i+1:]:
                if n in (13,32,0x81):break
                look+=profiles[(ff>>2)&3]['widths'][45 if n==0xad else n]
                if n in (45,0xad):break
            space=profiles[(flags>>2)&3]['widths'][32]
            assert x+space+look>width, ('premature soft wrap',offset,x,look)
            advance();continue
        wrapped_hyphen=c==0xad
        if wrapped_hyphen:c=ord('-')
        face=(flags>>2)&3; w=profiles[face]['widths'][c]
        if x+w>width:advance();positions[offset]=(len(lines)-1,x)
        lines[-1].append((offset,x,c,face));x+=w
        if wrapped_hyphen:advance()
    positions[len(raw)]=(len(lines)-1,x)
    top=next((li for li,line in enumerate(lines)if any(o>=top_offset for o,x,c,f in line)),0)
    expected=Image.new('1',(264,65))
    for row,line in enumerate(lines[top:top+(6 if height==11 else 65//height)]):
        for offset,x,c,face in line:
            glyph=profiles[face]['glyphs'][c];w=profiles[face]['widths'][c]
            for y in range(profiles[face]['height']):
                for dx in range(w):
                    if row*height+y<65 and glyph[y//8*w+dx]>>(y%8)&1:
                        expected.putpixel((x+dx,row*height+y),1)
    return expected,lines,top,positions


def verify_rich(out, sidebar_reference):
    checks=json.loads((out/'checks.json').read_text());books=json.loads((out/'source.json').read_bytes())
    version=json.loads((out/'source-version.json').read_text())['version'].lower()
    reports=[]
    system_preference=None
    view_states={}
    retained_files={}
    counters={}
    from picker_reference import PickerReference
    picker_reference=PickerReference()
    for index,check in enumerate(checks,1):
        if check.get('local_ui'):
            preference=json.loads((out/f'font-preference-{index:02}.json').read_text())
            if system_preference is None:system_preference=preference['system']
            assert preference['system']==system_preference, 'reader font selection must not alter system preference'
            if 'expected_reader_font'in check:assert preference['reader']==check['expected_reader_font'], 'selected reader font ID'
        options=out/f'options-{index:02}.bin'
        if options.exists(): assert options.read_bytes()==bytes([check['numbered'],check.get('italics',True),check.get('headings',True)]), 'independent display preference state'
        editor=(out/f'editor-{index:02}.bin').read_bytes(); start,end=struct.unpack_from('>II',editor,40)
        raw=(out/f'chapter-{index:02}.bin').read_bytes()
        if check.get('gap_at_eof'):
            assert start == len(raw) - (end - start), 'native gap remains at EOF for direct chapter access'
        raw=raw[:start]+raw[end:]
        if check.get('resume'):
            calls,status,position,saved_chapter,saved_numbered=struct.unpack('>5I',(out/f'saved-{index:02}.bin').read_bytes())
            assert calls>0 and status==0, 'reading position retained before releasing chapter'
            assert saved_chapter==check['chapter'] and saved_numbered==check['numbered'], 'saved chapter/options identity'
            assert position<=len(raw), 'saved position lies in chapter'
            if check.get('temporary_file_deleted'):
                allocated, missing = struct.unpack('>Ii', (out/f'file-lifecycle-{index:02}.bin').read_bytes())
                assert allocated > 512 and missing < 0, 'decoded chapter and gap deleted on kill focus'
        if check.get('find_form'):
            from bible_layout import system_font
            form=check['find_form'];font=system_font();expected=Image.new('1',(264,65))
            def draw_system(x,y,text):
                for column,character in enumerate(text):
                    for dy in range(16):
                        for dx in range(6):
                            if font[ord(character)*12+dy//8*6+dx]>>(dy%8)&1:
                                expected.putpixel((x+column*6+dx,y+dy),1)
            for row,label in enumerate([' Find:[                                ]',
                    '  exact: "so loved"      search: Enter',
                    ' nearby: love* world       exit: Esc',
                    form.get('error','  verse: John 3:16    next: Cmd/Ctrl-Find')]):
                draw_system(12,row*16,label)
            draw_system(54,0,form['text'])
            assert (out/f'find-{index:02}.bin').read_bytes().split(b'\0',1)[0].decode('ascii')==form['text']
            reference=out/f'find-reference-{index:02}.png';ImageChops.invert(expected.convert('L')).save(reference)
            capture=out/f'checkpoint-{index:02}.lcd.json'
            assert len(lcd_frames(capture,height=65))==3
            reports.append(compare([capture],reference,out/f'find-comparison-{index:02}',screen_size=(264,65)))
            continue
        if check.get('family_picker'):
            rom=(ROOT/'Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos').read_bytes()
            expected=picker_reference.render(check,rom)
            reference=out/f'picker-reference-{index:02}.png';expected.save(reference)
            capture=out/f'checkpoint-{index:02}.lcd.json'
            assert len(lcd_frames(capture,height=65))==3
            reports.append(compare([capture],reference,out/f'picker-comparison-{index:02}',screen_size=(264,65)))
            continue
        chapter=check['chapter']; first=0
        for book in books:
            if chapter<first+len(book['chapters']):break
            first+=len(book['chapters'])
        rich=check.get('font_vendor') in FONT_FILES or check.get('rich_font',False)
        for offset,character,flags in tokens(raw):
            if (flags&12)==12:
                assert (character in PRIVATE_LETTERS or 48<=character<=57), ('non-letter in private face',offset,character)
        if check.get('private_letters_only'):
            # Whole-chapter assertions include LORD + space + God in Genesis 3.
            assert any(character in (32,0x81) for _,character,_ in tokens(raw))
            assert all((flags&12)!=12 for _,character,flags in tokens(raw) if character in (32,0x81))
        source_styles=source_expected(version,book['name'],chapter-first+1,rich)
        if rich:
            provenance=[bool(flags&0x10) for _,code,flags in tokens(raw) if flags&12==12 and code in PRIVATE_LETTERS]
            original=[bool(style&1) for word,styles in source_styles[0] for style in styles if style&4]
            assert provenance==original, 'persistent italic provenance survives reflow and visibility toggles'
        provenance_all=[bool(flags&0x10) for _,code,flags in tokens(raw) if code not in (13,32,0x81) and not (flags&12==12 and 48<=code<=57)]
        original_all=[bool(style&1) for word,styles in source_styles[0] for style in styles]
        assert provenance_all==original_all, '0x10 mirrors original italic on all source text, even when disabled'
        if not check.get('italics',True):
            source_styles=([(word, tuple(style & ~1 if style & 4 else style for style in styles)) for word,styles in source_styles[0]], source_styles[1])
        assert semantic(raw)==source_styles, ('source styles/text',check['name'])
        pointers=struct.unpack_from('>3I',editor,78)
        assert len(set(pointers))==((3 if check.get('italics',True) else 2) if rich else 1), 'local italic slot aliases normal when disabled'
        profiles=[captured_font(out,index,p)for p in ['font','boldfont','italicfont']]
        profiles.append(private_font(out,index,profiles,check,rich))
        viewport=struct.unpack_from('>I',editor,24)[0]
        viewport=viewport-(end-start)if viewport>=end else min(viewport,start)
        expected,lines,top,positions=render_native(raw,profiles,viewport)
        if 'first_line_contains' in check:
            assert check['first_line_contains'] in ''.join(chr(c)for o,x,c,f in lines[top]), 'hidden heading must hide its terminating line break'
        counter_path=out/f'counters-{index:02}.json'
        if counter_path.exists():counters[index]=json.loads(counter_path.read_text())
        canonical=bytearray(raw.replace(b'\x81',b' ').replace(b'\xad',b'-'))
        for offset,code,flags in tokens(raw):
            if flags&12==12: canonical[offset]=REGULAR_SLOTS.get(code,code)
        pos=0
        while pos<len(canonical):
            if canonical[pos]in (0xb1,0xb2):
                if canonical[pos+1]in (1,2):canonical[pos+1]=2
                pos+=3
            else:pos+=1
        retained_files[index]=bytes(canonical)
        if check.get('no_intermediate_draw'):
            trace=[r for r in json.loads((out/'timings.json').read_text())if r['check']==index and 501<=r['phase']<=505]
            assert [r['phase'] for r in trace]==[501,502,503,504,505], 'complete toggle phase trace'
            assert len({r['lcd_writes'] for r in trace})==1, 'temporary viewport must not be painted'
        if check.get('retained_from'):
            before=check['retained_from']
            assert retained_files[index]==retained_files[before], 'toggle must retain text and formatting records in place'
            assert counters[index]['chapter_decodes']==counters[before]['chapter_decodes'], 'toggle must not decompress the chapter again'
        if check.get('sidebar_unchanged_from'):
            before=check['sidebar_unchanged_from']
            assert counters[index]['sidebar_draws']==counters[before]['sidebar_draws'], 'paging must not repaint the sidebar'
        if 'page_number' in check:
            wanted=check['page_number']*(6 if profiles[0]['height']==11 else 65//profiles[0]['height'])
            assert top==wanted, ('exact page extent',top,wanted)
        cursor=json.loads((out/f'cursor-{index:02}.json').read_text())
        def logical(offset): return offset-(end-start)if offset>=end else min(offset,start)
        caret=logical(struct.unpack_from('>I',editor,36)[0])
        row,x=positions[caret]
        view_state=(''.join(chr(c) for o,x,c,f in lines[top]), [w for w,style in semantic(raw[:caret])[0]])
        if check.get('preserve_view'):
            previous=check['preserve_view']
            if check.get('allow_caret_reflow'):
                old_editor=(out/f'editor-{index-1:02}.bin').read_bytes()
                old_start,old_end=struct.unpack_from('>II',old_editor,40)
                old_view=struct.unpack_from('>I',old_editor,24)[0]
                old_view=old_view-(old_end-old_start) if old_view>=old_end else min(old_view,old_start)
                _,_,retained_top,_=render_native(raw,profiles,old_view)
                rows=6 if profiles[0]['height']==11 else 65//profiles[0]['height']
                minimum_top=max(retained_top,row-rows+1)
                assert top==minimum_top, ('reflow must scroll only enough to retain the caret',top,minimum_top)
                assert view_state[1]==view_states[previous][1], 'reflow must retain source caret position'
            else:
                assert view_state==view_states[previous], ('viewport/caret moved on toggle',check['name'],view_state,view_states[previous])
        view_states[index]=view_state
        assert cursor==dict(x=x,y=(row-top)*profiles[0]['height'],mode=check.get('cursor_mode',12)), ('source cursor',check['name'],cursor,(row,x,top,caret))
        state=struct.unpack_from('>H',editor,54)[0]
        if check.get('rich_selection'):
            assert state, 'selected search/verse result'
            anchor=logical(struct.unpack_from('>I',editor,56)[0])
            lo,hi=sorted([anchor,caret]); selected,_=semantic(raw[lo:hi])
            text=' '.join(w for w,styles in selected)
            want=book['chapters'][chapter-first][check['verse']-1] if check['rich_selection']=='verse' else check['rich_selection']
            assert text==want, ('selected text',text,want)
            ar,ax=positions[anchor];cr,cx=positions[caret]
            if (ar,ax)>(cr,cx):ar,ax,cr,cx=cr,cx,ar,ax
            for line in range(max(top,ar),min(top+(6 if profiles[0]['height']==11 else 65//profiles[0]['height']),cr+1)):
                left=ax if line==ar else 0;right=cx if line==cr else 252
                for y in range((line-top)*profiles[0]['height'],min(65,(line-top+1)*profiles[0]['height'])):
                    for px in range(left,right):expected.putpixel((px,y),1-expected.getpixel((px,y)))
        else: assert state==0, ('chapter lookup unselected',check['name'],state)
        if check.get('clipboard'):
            assert (out/f'clipboard-{index:02}.bin').read_bytes()==check['clipboard_text'].encode('cp1252'), 'plain cited clipboard'
            if check.get('clipboard_relocation'):
                writes,moves,initial,last,before,after,first_before,first_after = struct.unpack('>8I', (out/f'copy-relocation-{index:02}.bin').read_bytes())
                assert writes > 2 and moves > 0, 'native clipboard allocation must relocate the chapter'
                assert first_before != first_after, 'observed chapter relocation during an append'
                assert all(0x1000 <= pointer < 0x80000 for pointer in (initial,last,first_before,first_after)), 'valid chapter RAM pointers'
            if check.get('clipboard_reuse'):
                writes,moves,*_ = struct.unpack('>8I', (out/f'copy-relocation-{index:02}.bin').read_bytes())
                assert writes == 3 and moves == 0, 'native copy reuses the existing raw allocation'
        if check.get('clipboard') or check.get('notice_text'):
            # Copy/search notice uses the independently specified checker mask/rectangle.
            from bible_layout import system_font
            for y in range(65):
                for px in range(252):
                    if (px+y)%2==0:expected.putpixel((px,y),0)
            expected.paste(1,(70,22,182,42));label=check.get('notice_text','Copied');sx=(252-6*len(label))//2;glyphs=system_font()
            for j,c in enumerate(label):
                for y in range(16):
                    for px in range(6):
                        if glyphs[ord(c)*12+y//8*6+px]>>(y%8)&1:expected.putpixel((sx+j*6+px,24+y),0)
        bar=sidebar_reference(books,chapter,profiles[0]['height'],captured_font(out,index,'sidebarfont'))
        if check.get('search_notice'):
            metadata=json.loads((out/f'search-notice-{index:02}.json').read_text())
            assert metadata['notice']==check['search_notice']
            phase=metadata['dots'];center=phase-1 if phase<=5 else 9-phase
            bar=Image.new('1',(11,65),1)
            for dot in range(5):
                distance=abs(dot-center);radius=1 if distance<=1 else 0
                for dy in range(-radius,radius+1):
                    for dx in range(-radius,radius+1):
                        if distance==1 and dx and dy:continue
                        bar.putpixel((5+dx,8+dot*12+dy),0)
        expected.paste(bar,(253,0))
        if check.get('help'):
            font=captured_font(out,index,'sidebarfont');expected=Image.new('1',(264,65))
            def draw(x,y,text):
                for c in text:
                    w=font['widths'][ord(c)];g=font['glyphs'][ord(c)]
                    for dy in range(9):
                        for dx in range(w):
                            if g[dy//8*w+dx]>>(dy%8)&1:expected.putpixel((x+dx,y+dy),1)
                    x+=w
            def width(text):return sum(font['widths'][ord(c)]for c in text)
            columns=[(0,145,38,'Read / find',[('Page','Space / Shift Space'),('Chapter',', .  [ ]  < >'),('Find','Find'),('Next','Ctrl Find'),('Prev','Ctrl Shift Find'),('Copy','Ctrl C')]),
                (145,119,34,'Display / font',[('I','Toggle italics'),('H','Toggle headings'),('V','Verse numbers'),('F','Font'),('?','Help'),('Esc','Back')])]
            for left,size,colon,title,rows in columns:
                draw(left+(size-width(title))//2,0,title)
                for y in range(9):
                    for x in range(left,left+size):expected.putpixel((x,y),1-expected.getpixel((x,y)))
                for row,(label,keys)in enumerate(rows):
                    assert left+colon+font['widths'][58]+3+width(keys)<=left+size, 'help column bounds'
                    draw(left+colon-2-width(label),10+9*row,label);draw(left+colon,10+9*row,':');draw(left+colon+font['widths'][58]+3,10+9*row,keys)
            assert cursor==dict(x=0,y=0,mode=12), 'Help console cursor'

        reference=out/f'rich-reference-{index:02}.png'
        ImageChops.invert(expected.convert('L')).save(reference)
        capture=out/f'checkpoint-{index:02}.lcd.json'
        assert len(lcd_frames(capture,height=65))==3
        reports.append(compare([capture],reference,out/f'rich-comparison-{index:02}',screen_size=(264,65)))
    if any(check.get('family_picker') for check in checks):
        from picker_reference import response_report
        (out/'response-times.json').write_text(json.dumps(response_report(out),indent=2)+'\n')
    result=dict(status='passed',checkpoints=len(checks),translation=version,bitmap_comparisons=reports)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS rich source styles, font glyphs, cursor and exact LCD pixels:',len(checks),version)
