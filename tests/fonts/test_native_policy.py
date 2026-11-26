"""Policy decisions against independently specified synthetic bitmap geometry."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'fonts'))
sys.path.insert(0,str(ROOT/'research/fonts'))
import native


class NativePolicy(unittest.TestCase):
    def select(self, rare_count, priority=()):
        common=list(range(65,70));rare=list(range(70,70+rare_count));slots=common+rare
        mapping={c:c for c in slots};mapping[200]=1000
        face={c:dict(advance=5,points={(0,-5),(0,-3),(0,0)})for c in common}
        face.update({c:dict(advance=5,points={(0,-6),(0,-3),(0,0)})for c in rare})
        face[1000]=dict(advance=5,points={(0,-9),(0,0)})
        option=dict(points=6,dpi=75,pixels=6,paths=[Path(str(i))for i in range(4)])
        with patch.object(native,'CP',slots),patch.object(native,'strike_options',return_value=[option]),patch.object(native,'read_source',return_value=face):
            return native.choose('Serif',10,mapping,set(priority))

    def test_four_distinct_slots_across_styles_not_four_cells(self):
        faces,meta=self.select(4)
        self.assertTrue(meta['available'])
        self.assertEqual(meta['allowed_cp1252_slots'],['46','47','48','49'])
        self.assertEqual(len(meta['clipping']),16)
        self.assertEqual(meta['baseline'],5)
        self.assertTrue(all(200 not in f for f in faces),'oversized Neo-only glyph must stay absent')
        for face in faces:
            self.assertEqual(sum(face[70].getdata()),2)

    def test_five_distinct_slots_fails_without_relaxing_policy(self):
        faces,meta=self.select(5)
        self.assertIsNone(faces)
        self.assertFalse(meta['available'])
        self.assertEqual(len(meta['closest']['slots']),5)

    def test_only_mono_italic_gets_unlimited_horizontal_clipping(self):
        mapping={65:65};upright={65:dict(advance=5,points={(0,-5),(4,0)})}
        slanted={65:dict(advance=5,points={(x,-3)for x in range(-3,10)})}
        option=dict(points=6,dpi=75,pixels=6,paths=[Path(str(i))for i in range(4)])
        with patch.object(native,'CP',[65]),patch.object(native,'strike_options',return_value=[option]),patch.object(native,'read_source',side_effect=[upright,upright,slanted,slanted]):
            faces,meta=native.choose('Mono',10,mapping,{65})
        self.assertTrue(meta['available'])
        self.assertEqual(meta['mono_width'],6)
        self.assertEqual(len(meta['clipping']),2)
        self.assertTrue(all(c['style']in['Italic','BoldItalic']for c in meta['clipping']))
        self.assertEqual(sum(faces[2][65].getdata()),6)


if __name__=='__main__':unittest.main()
