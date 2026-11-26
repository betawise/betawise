"""Private six-line letters retain accepted native uppercase cells exactly."""
from pathlib import Path
import sys
import json
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'fonts'))
sys.path.insert(0,str(ROOT/'os3k'))
import fontgen
from charsets import load
from charsets.smallcaps import load as load_smallcaps


def setUpModule():
    from font_inputs import ensure_fonts
    ensure_fonts()


class PrivateFaces(unittest.TestCase):
    def test_all_sizes_use_native_sources_without_rescaling(self):
        records=json.loads((ROOT/'fonts/build/bdf/generation-report.json').read_text())['private_faces']
        self.assertEqual(len(records),16)
        charset=load_smallcaps()
        neo=load(ROOT/'os3k/charsets/neo-us.txt')
        codes=tuple(sorted(set(neo.values())-{None}))
        for record in records:
            if record['lines']==6:continue
            actual=fontgen.load(ROOT/'fonts/build/bdf'/record['file'],'iso8859-1','blank')
            size={3:'Large',4:'Medium',5:'Small'}[record['lines']]
            for index,style in enumerate(charset['styles']):
                body=fontgen.load(ROOT/f'fonts/build/bdf/BetaWise{record["family"]}/BetaWise{record["family"]}-{size}-{style.title()}.bdf','iso8859-1',63)
                target=body[ord('x')].getbbox()
                _,face=fontgen.read_unicode_source(ROOT / record['source']['paths'][index],codes)
                points=face[72]['points']
                capheight=max(y for x,y in points)-min(y for x,y in points)+1
                self.assertIn(capheight,(target[3]-target[1],target[3]-target[1]+1))
                offset=target[3]-max(y for x,y in points)-1
                for letter in charset['letters']:
                    expected=set();width=0
                    for c in letter['text']:
                        glyph=face[ord(c)];points=glyph['points']
                        shift=max(0,-min((x for x,y in points),default=0))
                        w=max(glyph['advance']+shift,max((x+1+shift for x,y in points),default=1),1)
                        expected.update((width+x+shift,y+offset) for x,y in points);width+=w
                    image=actual[int(letter[style],16)]
                    found={(x,y) for y in range(image.height) for x in range(image.width) if image.getpixel((x,y))}
                    self.assertEqual(image.width,width)
                    self.assertEqual(found,expected,(record['family'],size,style,letter['text']))

    def test_all_letters_and_digit_bounds(self):
        charset=load_smallcaps()
        inverse={code:slot for slot,code in load(ROOT/'os3k/charsets/neo-us.txt').items() if code is not None}
        for family in ('Serif','Sans','Book','Mono'):
            folder=ROOT/'fonts/build/bdf'/('BetaWise'+family)
            path=folder/'private'/f'BetaWise{family}-Tiny-SmallCaps.bdf'
            raw,ascent,descent=fontgen.load_bdf(path)
            actual=fontgen.load(path,'iso8859-1','blank')
            self.assertEqual(sum(g is not None for g in raw),196)
            self.assertEqual(ascent+descent,11)
            for style in charset['styles']:
                body=fontgen.load(folder/f'BetaWise{family}-Tiny-{style.title()}.bdf','iso8859-1',63)
                for letter in charset['letters']:
                    components=[body[inverse[ord(c)]] for c in letter['text']]
                    expected=Image.new('1',(sum(g.width for g in components),11));x=0
                    for component in components:expected.paste(component,(x,0));x+=component.width
                    glyph=actual[int(letter[style],16)]
                    self.assertEqual((glyph.size,glyph.tobytes()),(expected.size,expected.tobytes()),(family,style,letter['text']))
            regular=fontgen.load(folder/f'BetaWise{family}-Tiny-Regular.bdf','iso8859-1',63)
            top=regular[72].getbbox()[1]
            for digit in range(10):
                glyph=actual[int(charset['superscript_digits'][digit],16)]
                self.assertEqual(glyph.height,11)
                box=glyph.getbbox()
                self.assertEqual((box[1],box[3]),(top,top+5))
            for slot in charset['reserved']:
                self.assertIsNone(raw[int(slot,16)])




class SuperscriptSources(unittest.TestCase):
    def test_shared_ti_digit_envelope(self):
        data=json.loads((ROOT/'research/fonts/superscript-3x5.json').read_text())
        self.assertEqual(data['source']['pdf_page'],181)
        self.assertEqual((data['height'],data['advance']),(5,4))
        self.assertEqual(len(data['columns']),10)
        self.assertEqual(len(set(map(tuple,data['columns']))),10)
        for columns in data['columns']:
            self.assertEqual(len(columns),4)
            self.assertEqual(columns[3],0)
            self.assertTrue(all(0<=column<32 for column in columns))
            rows=[y for y in range(5)if any(c>>y&1 for c in columns)]
            self.assertEqual((min(rows),max(rows)),(0,4))

    def test_accepted_choices_preserve_native_digit_pixels(self):
        report=json.loads((ROOT/'fonts/build/bdf/generation-report.json').read_text())
        charset=load_smallcaps()
        patterns=json.loads((ROOT/'research/fonts/superscript-3x5.json').read_text())
        heights={'Serif':[7,5,5,5],'Sans':[8,6,6,5],
                 'Book':[8,6,6,5],'Mono':[7,6,5,5]}
        originals={('Sans',6),('Book',6),('Mono',5),('Mono',6)}
        for record in report['private_faces']:
            family,lines=record['family'],record['lines']
            policy=record['digit_policy'];self.assertEqual(policy['ink_height'],heights[family][lines-3])
            self.assertEqual(policy['kind']=='3x5',(family,lines)in originals)
            actual=fontgen.load(ROOT/'fonts/build/bdf'/record['file'],'iso8859-1','blank')
            if policy['kind']=='native':
                _,source=fontgen.read_unicode_source(ROOT/policy['source'],tuple(range(48,58)))
                first=min(y for code in range(48,58)for x,y in source[code]['points'])
            for digit in range(10):
                glyph=actual[int(charset['superscript_digits'][digit],16)]
                found={(x,y)for y in range(glyph.height)for x in range(glyph.width)if glyph.getpixel((x,y))}
                if policy['kind']=='native':
                    g=source[48+digit];shift=max(0,-min(x for x,y in g['points']))
                    expected={(x+shift,y-first+policy['top'])for x,y in g['points']}
                    width=max(g['advance']+shift,max(x for x,y in expected)+1)
                else:
                    expected={(x,y+policy['top'])for x,column in enumerate(patterns['columns'][digit])for y in range(5)if column>>y&1}
                    width=4
                self.assertEqual(found,expected,(family,lines,digit))
                self.assertEqual(glyph.width,width,(family,lines,digit))

class SuperscriptPolicy(unittest.TestCase):
    def test_equal_height_and_native_3x5_preference(self):
        sys.path.insert(0,str(ROOT/'research/fonts'))
        from build_superscripts import select
        class Recipe:
            def __init__(self,ink):self.ink=ink
            def strikes(self,*args):return [dict(pixels=8,dpi=75,paths=['native.bdf'])]
            def source(self,*args):return {},{c:dict(advance=4,points={(x,y)for x in range(3)for y in range(self.ink)})for c in range(48,58)}
            def horizontal(self,g,*args):return g['advance'],g['points'],0
            def source_name(self,p):return str(p)
        for cap,ink,kind in [(5,5,'native'),(6,6,'3x5'),(7,7,'3x5'),(8,8,'native'),(5,6,'3x5'),(6,5,'native')]:
            h=Image.new('1',(4,16))
            for y in range(1,cap+1):h.putpixel((0,y),1)
            _,policy=select(Recipe(ink),'Serif',{72:h},12,ROOT)
            self.assertEqual(policy['kind'],kind,(cap,ink))


if __name__=='__main__':unittest.main()
