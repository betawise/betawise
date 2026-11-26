"""Independent whole-screen references for the shared proportional picker."""
import struct
from PIL import Image

FAMILIES = ['BetaWise Book', 'BetaWise Mono', 'BetaWise Sans', 'BetaWise Serif', 'BetaWise Terminal', 'Neo Font', 'System']
VENDOR = [('Extra Large', '(2 lines)'), ('Very Large', '(3 lines)'),
          ('Large', '(4 lines)'), ('Medium', '(5 lines)'), ('Small', '(6 lines)')]
READING = [('Large', '(3 lines)'), ('Medium', '(4 lines)'),
           ('Small', '(5 lines)'), ('Tiny', '(6 lines)')]

class PickerReference:
    def __init__(self):
        self.top = 0

    def render(self, check, rom):
        spec=check['family_picker']; selected=spec['family']; height=9
        if 'F' in check.get('keys',[]):
            self.top=max(0,selected-6+1)
        first=10
        rows=6
        if selected<self.top:self.top=selected
        if selected>=self.top+rows:self.top=selected-rows+1
        address=0x44d592
        base=0x410000
        h,max_width,stride,_,widths,offsets,bitmap=struct.unpack_from('>4BIII',rom,address-base)
        assert h==height
        ink=Image.new('L',(264,65))
        def text(x,y,limit,value):
            for c in value:
                code=ord(c);width=rom[widths-base+code] if widths else max_width
                offset=struct.unpack_from('>H',rom,offsets-base+2*code)[0] if offsets else code*stride
                if x+width>limit:break
                for dy in range(height):
                    for dx in range(width):
                        if rom[bitmap-base+offset+dy//8*width+dx]>>(dy%8)&1:ink.putpixel((x+dx,y+dy),255)
                x+=width
        def invert(top):
            for y in range(top,top+height):
                for x in range(264):ink.putpixel((x,y),255-ink.getpixel((x,y)))
        text(6,0,258,'Select a font, then press Enter.');invert(0)
        for family in range(self.top,min(7,self.top+rows)):
            y=first+(family-self.top)*height
            text(6,y,108 if family==selected else 258,FAMILIES[family])
            if family==selected:
                variants = ([('Medium (44x8)',8)] if family==4 else
                    [('Extra Large (2 lines)',2),('Very Large (3 lines)',3),('Large (4 lines)',4),('Medium (5 lines)',5),('Small (6 lines)',6)] if family==5 else
                    [('4 lines',4),('7 lines',7)] if family==6 else
                    [('Large (3 lines)',3),('Medium (4 lines)',4),('Small (5 lines)',5),('Tiny (6 lines)',6)])
                size=min(range(len(variants)),key=lambda i:(abs(variants[i][1]-spec['target']),variants[i][1]))
                text(120,y,246,variants[size][0])
                for left,enabled in [(True,size>0),(False,size+1<len(variants))]:
                    if enabled:
                        for column in range(4):
                            radius=column if left else 3-column
                            x=(112 if left else 250)+column
                            center=y+(height-7)//2+3
                            for dy in range(-radius,radius+1):ink.putpixel((x,center+dy),255)
            if family==selected:invert(y)
        return ink.point(lambda p:0 if p else 255)


def response_report(out):
    """Guest-time input latency, including firmware dispatch, searches and paint."""
    import json
    checks=json.loads((out/'checks.json').read_text())
    timings=json.loads((out/'timings.json').read_text())
    records=[]
    for index,check in enumerate(checks,1):
        if not check.get('family_picker'):continue
        phases={row['phase']:row['time'] for row in timings if row['check']==index}
        assert all(phase in phases for phase in (600,601,602)), ('missing picker timing',index)
        total=1000*(phases[602]-phases[600])
        search=1000*(phases.get(603,phases[601])-phases[601])
        paint=1000*(phases[602]-phases.get(603,phases[601]))
        # Explicit regression ceiling for this pinned, 22-provider/two-builtins fixture.
        # Includes full six-row redraws and End's backward viewport search.
        assert 0<=total<=300, ('picker input latency exceeds 300 ms',index,total)
        records.append(dict(check=index,name=check['name'],total_ms=total,
                            search_ms=search,paint_ms=paint))
    return dict(clock='MAME emulated guest time',ceiling_ms=300,records=records)
