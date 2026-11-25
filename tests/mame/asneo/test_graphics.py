"""Check real graphics helpers against independently rounded line geometry."""
import ctypes
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 264, 65
SIZE = WIDTH * HEIGHT


def line_pixels(line):
    """Round each major-axis sample to its nearest minor-axis coordinate.

    Halfway samples advance toward the destination, matching the directional
    tie contract. This uses a closed-form ratio, not Bresenham's error loop.
    """
    x0, y0, x1, y1 = line
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx, sy = (1 if x1 >= x0 else -1), (1 if y1 >= y0 else -1)
    if dx == dy == 0:
        yield x0, y0
    elif dx >= dy:
        for step in range(dx + 1):
            yield x0 + sx * step, y0 + sy * ((step * dy + dx // 2) // dx)
    else:
        for step in range(dy + 1):
            yield x0 + sx * ((step * dx + dy // 2) // dy), y0 + sy * step


class GraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='neo-graphics-')
        root = Path(cls.temp.name)
        os3k = Path(__file__).resolve().parents[3] / 'os3k'
        subprocess.run(['make', '--no-print-directory', '-s', '-C',
                        str(os3k), 'version.h'], check=True)
        (root / 'raster.c').write_text('''#include "os3k.h"
#include <string.h>
unsigned char pixels[264*65];
unsigned calls, invalid;
uint16_t spans[264][4];
void reset(unsigned initial) {
 memset(pixels, initial, sizeof(pixels)); calls=invalid=0;
}
void RasterOp(uint16_t x,uint16_t y,uint16_t w,uint16_t h,uint8_t*b,RopCode_e op) {
 if (calls < 264) {
  spans[calls][0]=x; spans[calls][1]=y;
  spans[calls][2]=w; spans[calls][3]=h;
 }
 ++calls;
 if (calls>264 || !w || !h || (unsigned)x+w>264 || (unsigned)y+h>65 || b ||
     (op!=ROP_BLACKNESS && op!=ROP_WHITENESS)) { ++invalid; return; }
 for (unsigned yy=y;yy<(unsigned)y+h;++yy)
  for(unsigned xx=x;xx<(unsigned)x+w;++xx) pixels[264*yy+xx]=op==ROP_BLACKNESS;
}
''')
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra',
                        '-Werror', '-I' + str(os3k), str(os3k / 'os3k_display_gfx.c'),
                        str(root / 'raster.c'), '-o', str(root / 'graphics.so')], check=True)
        cls.lib = ctypes.CDLL(str(root / 'graphics.so'))
        cls.lib.DrawLine.argtypes = [ctypes.c_uint16] * 4 + [ctypes.c_bool]
        cls.lib.DrawLine.restype = None
        cls.lib.reset.argtypes = [ctypes.c_uint]
        cls.lib.reset.restype = None
        cls.buffer = (ctypes.c_ubyte * SIZE).in_dll(cls.lib, 'pixels')
        cls.spans = ((ctypes.c_uint16 * 4) * 264).in_dll(cls.lib, 'spans')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def check_line(self, line, black=True):
        self.lib.reset(0 if black else 1)
        self.lib.DrawLine(*line, black)
        self.assertEqual(ctypes.c_uint.in_dll(self.lib, 'invalid').value, 0, line)
        expected = bytearray([0 if black else 1]) * SIZE
        for x, y in line_pixels(line):
            expected[WIDTH * y + x] = black
        self.assertEqual(bytes(self.buffer), expected, line)
        dx, dy = abs(line[2] - line[0]), abs(line[3] - line[1])
        calls = ctypes.c_uint.in_dll(self.lib, 'calls').value
        # Every minor-axis coordinate needs exactly one maximal span.
        self.assertEqual(calls, min(dx, dy) + 1, line)
        for _, _, width, height in self.spans[:calls]:
            self.assertEqual(height if dx >= dy else width, 1, line)
        return calls

    def test_axis_lines_and_points(self):
        for line in [(0, 64, 263, 64), (263, 0, 263, 64), (200, 10, 10, 10),
                     (4, 62, 4, 2), (0, 0, 0, 0), (263, 64, 263, 64)]:
            for black in (True, False):
                self.assertEqual(self.check_line(line, black), 1)
            expected = Image.new('1', (WIDTH, HEIGHT))
            ImageDraw.Draw(expected).line(line, fill=1)
            points = set(line_pixels(line))
            self.assertEqual(bytes(map(int, expected.getdata())),
                             bytes(1 if (x, y) in points else 0
                                   for y in range(HEIGHT) for x in range(WIDTH)))

    def test_every_small_grid_endpoint_pair_and_direction(self):
        for y0 in range(9):
            for x0 in range(9):
                for y1 in range(9):
                    for x1 in range(9):
                        self.check_line((100 + x0, 20 + y0, 100 + x1, 20 + y1))

    def test_every_panel_slope_in_all_octants(self):
        for dx in range(WIDTH):
            for dy in range(HEIGHT):
                self.check_line((0, 0, dx, dy))
                self.check_line((263, 0, 263 - dx, dy))
                self.check_line((0, 64, dx, 64 - dy))
                self.check_line((263, 64, 263 - dx, 64 - dy))

    def test_erasing_arbitrary_lines_preserves_surrounding_pixels(self):
        rng = random.Random(0xB235)
        for _ in range(300):
            line = (rng.randrange(WIDTH), rng.randrange(HEIGHT),
                    rng.randrange(WIDTH), rng.randrange(HEIGHT))
            self.check_line(line, False)

    def test_span_call_reductions_and_diagonal_limit(self):
        self.assertEqual(self.check_line((0, 0, 263, 1)), 2)
        self.assertEqual(self.check_line((0, 0, 1, 64)), 2)
        self.assertEqual(self.check_line((0, 0, 263, 64)), 65)
        # Diagonal pixels are not adjacent along either axis, so merging them
        # into rectangles would paint pixels outside the original line.
        self.assertEqual(self.check_line((0, 0, 64, 64)), 65)


if __name__ == '__main__':
    unittest.main()
