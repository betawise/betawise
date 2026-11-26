"""Independent raster geometry and strict cell-fit checks for vector review."""
import sys
import tempfile
import unittest
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'fonts'))
sys.path.insert(0,str(ROOT/'research/fonts'))
import vector_review as vector


class VectorReview(unittest.TestCase):
    def test_freetype_renders_known_outline_and_reports_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            builder = FontBuilder(1000,isTTF=True)
            builder.setupGlyphOrder(['.notdef','rectangle'])
            builder.setupCharacterMap({65:'rectangle'})
            empty = TTGlyphPen(None).glyph()
            pen = TTGlyphPen(None)
            pen.moveTo((0,0));pen.lineTo((500,0));pen.lineTo((500,700));pen.lineTo((0,700));pen.closePath()
            builder.setupGlyf({'.notdef':empty,'rectangle':pen.glyph()})
            builder.setupHorizontalMetrics({'.notdef':(600,0),'rectangle':(600,0)})
            builder.setupHorizontalHeader(ascent=800,descent=-200)
            builder.setupNameTable({'familyName':'Geometry Fixture','styleName':'Regular',
                'uniqueFontIdentifier':'GeometryFixture','fullName':'Geometry Fixture','psName':'GeometryFixture'})
            builder.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200)
            builder.setupPost();builder.setupMaxp()
            font = directory/'geometry.ttf';builder.save(font)
            rasterizer = vector.Rasterizer(vector.compile_rasterizer(directory/'build'))
            glyphs = rasterizer.render(font,10,'native',0,(65,66))
            self.assertIsNone(glyphs[66])
            glyph = glyphs[65]
            self.assertEqual((glyph['left'],glyph['top'],glyph['width'],glyph['height']), (0,7,5,7))
            self.assertEqual(glyph['rows'],['11111']*7)
            self.assertEqual(glyph['advance64'],6*64)
            image = vector.fit_glyph(glyph,5,10,8)
            self.assertEqual(sum(image.getdata()),35)
            self.assertEqual(image.getbbox(),(0,1,5,8))
            self.assertIsNone(vector.fit_glyph(glyph,4,10,8))
            self.assertIsNone(vector.fit_glyph(glyph,5,7,6))
            self.assertIsNone(vector.fit_glyph({**glyph,'left':-1},5,10,8))
            self.assertEqual(vector.fit_glyph({**glyph,'left':-1},5,10,8,1).tobytes(),image.tobytes())

    def test_topology_distinguishes_counter_and_separate_accent(self):
        image = Image.new('1',(7,7))
        for y in range(2,7):
            for x in range(1,6):
                if x in (1,5) or y in (2,6):image.putpixel((x,y),1)
        image.putpixel((3,0),1)
        self.assertEqual(vector.topology(image),dict(ink=17,parts=2,holes=1))
        packed = vector.review.pack(image)
        self.assertEqual(vector.unpack(packed,7).tobytes(),image.tobytes())


if __name__ == '__main__':unittest.main()
