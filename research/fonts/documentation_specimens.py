#!/usr/bin/env python3
"""Publish compact README specimens from the actual linked font applet bytes.

Executed descriptors locate glyph bytes in each OS3KApp; ELF load records verify its layout.
Every decoded glyph is checked against its source BDF before publication.
No screenshots, model inference, or reconstructed substitute glyphs are used.
"""
import argparse,hashlib,json,struct,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'fonts'))
import fontgen
SIZES=[('Large',3),('Medium',4),('Small',5),('Tiny',6)]
STYLES=[('Regular','GLYPH_FONT',''),('Bold','BOLD_GLYPH_FONT','-Bold'),
        ('Italic','ITALIC_GLYPH_FONT','-Italic'),('BoldItalic','BOLD_ITALIC_GLYPH_FONT','-BoldItalic')]
SAMPLE='AaBbCcDdEeFfGg 0123'
LCD_BACKGROUND=(192,201,170)
LCD_INK=(37,48,42)

class Applet:
    def __init__(self,stem):
        folder=ROOT/'fonts/build'/stem
        self.data=(folder/(stem+'.OS3KApp')).read_bytes()
        self.elf=(folder/(stem+'.elf')).read_bytes()
        assert self.elf[:6]==b'\x7fELF\x01\x02'
        header=struct.unpack_from('>16sHHIIIIIHHHHHH',self.elf)
        self.loads=[]
        for n in range(header[10]):
            kind,offset,virtual,physical,size,memory,flags,align=struct.unpack_from('>8I',self.elf,header[5]+n*header[9])
            if kind==1:
                assert self.data[physical:physical+size]==self.elf[offset:offset+size]
                self.loads.append((virtual,physical,size))
        results=ROOT/'tests/fonts/build/minimal'
        record=next(row for row in json.loads((results/'results.json').read_text())['applets'] if row['applet']==stem)
        assert record['passed'] and record['sha256']==hashlib.sha256(self.data).hexdigest()
        self.descriptors=(results/stem/'ram-210000.bin').read_bytes()
        assert len(self.descriptors)==int.from_bytes(self.data[8:12],'big')+8
        self.name=self.data[24:60].split(b'\0')[0].decode('ascii')

    def read(self,address,size):
        address-=0x210000  # ROM placement of the executed descriptor capture.
        for virtual,physical,length in self.loads:
            if virtual<=address and address+size<=virtual+length:
                start=physical+address-virtual
                return self.data[start:start+size]
        raise ValueError(f'Pointer outside linked applet ROM: {address:x}+{size}')

    def face(self,symbol,bdf,private=False):
        index=['GLYPH_FONT','BOLD_GLYPH_FONT','ITALIC_GLYPH_FONT','BOLD_ITALIC_GLYPH_FONT','PRIVATE_GLYPH_FONT'].index(symbol)
        h,mw,stride,pad,wp,op,bp=struct.unpack_from('>4BIII',self.descriptors,4+16*index)
        widths=list(self.read(wp,256))if wp else [mw]*256
        offsets=struct.unpack('>256H',self.read(op,512))if op else [c*stride for c in range(256)]
        expected=fontgen.load(bdf,'iso8859-1','blank'if private else 63)
        glyphs=[]
        for code,width in enumerate(widths):
            raw=self.read(bp+offsets[code],width*((h+7)//8))
            image=Image.new('1',(width,h))
            for y in range(h):
                for x in range(width):
                    if raw[y//8*width+x]>>(y%8)&1:image.putpixel((x,y),1)
            source=expected[code]
            assert image.size==source.size and image.tobytes()==source.tobytes(),(self.name,symbol,code)
            glyphs.append(image)
        return glyphs

def sample(glyphs,text=SAMPLE):
    image=Image.new('1',(264,glyphs[0].height));x=0
    for c in text:
        glyph=glyphs[ord(c)]
        assert x+glyph.width<=264,('Specimen text exceeds display width',text)
        image.paste(glyph,(x,0));x+=glyph.width
    return image

def publish(rows,path,title,scale=3):
    title_font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',24)
    label_font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    heights=[36+scale*glyphs[0].height for label,glyphs in rows]
    canvas=Image.new('RGB',(816,58+sum(heights)),'white');draw=ImageDraw.Draw(canvas)
    draw.text((12,8),title,font=title_font,fill='black')
    draw.text((12,36),'Actual applet glyphs · emulator LCD colors · 3× native pixels',font=label_font,fill='#555555')
    y=58
    for (label,glyphs),height in zip(rows,heights):
        draw.text((12,y+5),label,font=label_font,fill='#333333')
        image=sample(glyphs).resize((792,scale*glyphs[0].height),Image.Resampling.NEAREST)
        canvas.paste(LCD_BACKGROUND,(12,y+30,804,y+30+image.height))
        canvas.paste(LCD_INK,(12,y+30,804,y+30+image.height),image)
        y+=height
    canvas.save(path,optimize=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'fonts/specimens')
    parser.add_argument('--no-build',action='store_true')
    args=parser.parse_args()
    if not args.no_build:subprocess.run(['make','-s','-C',str(ROOT/'fonts'),'-j4'],check=True)
    subprocess.run([sys.executable,str(ROOT/'tests/fonts/check_minimal_fonts.py')],check=True)
    args.output.mkdir(parents=True,exist_ok=True);report=[]
    for family in ['Serif','Sans','Book','Mono']:
        regular=[];styled=[]
        for size,lines in SIZES:
            stem=f'BetaWise{family}-{size}';applet=Applet(stem)
            folder=ROOT/'fonts/build/bdf'/('BetaWise'+family)
            for style,symbol,suffix in STYLES:
                glyphs=applet.face(symbol,folder/(stem+'-'+style+'.bdf'))
                styled.append((f'{size} ({lines} lines) · {style.replace("BoldItalic", "Bold Italic")}',glyphs))
                if style=='Regular':regular.append((f'{size} · {lines} lines per screen',glyphs))
            applet.face('PRIVATE_GLYPH_FONT',folder/'private'/(stem+'-SmallCaps.bdf'),True)
            report.append(dict(applet=applet.name,faces_checked=5,glyphs_checked=1280))
        publish(regular,args.output/(family.lower()+'.png'),'BetaWise '+family)
        publish(styled,args.output/(family.lower()+'-styles.png'),'BetaWise '+family+' — all four styles')
    terminal=[]
    for size,columns,lines,source in [('Medium',44,8,'glyphs.bdf'),('Small',52,9,'glyphs-5x7.bdf'),('Tiny',66,10,'glyphs-4x6.bdf')]:
        stem='BetaWiseTerminal-'+size;applet=Applet(stem)
        bdf=ROOT/'fonts/BetaWiseTerminalMedium.bdf'if size=='Medium'else ROOT/'fonts/build/bdf/BetaWiseTerminal'/source
        glyphs=applet.face('GLYPH_FONT',bdf)
        terminal.append((f'{size} · {columns} columns × {lines} lines',glyphs))
        report.append(dict(applet=applet.name,faces_checked=1,glyphs_checked=256))
    publish(terminal,args.output/'terminal.png','BetaWise Terminal')
    out=ROOT/'research/fonts/build/documentation-specimens';out.mkdir(parents=True,exist_ok=True)
    (out/'verification.json').write_text(json.dumps(dict(status='passed',fonts=report,total_glyphs=sum(r['glyphs_checked']for r in report)),indent=2)+'\n')
    print('Verified',sum(r['glyphs_checked']for r in report),'glyphs from',len(report),'built applets')
    print(args.output)
if __name__=='__main__':main()
