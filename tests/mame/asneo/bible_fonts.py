"""Shipping reader-font fixtures shared by the BibleWise acceptance scripts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
FONT_ROOT = ROOT/'betawise/fonts/build'
FONT_FILES = dict(schoolbook='BetaWiseBook-Tiny',helvetica='BetaWiseSans-Tiny',times='BetaWiseSerif-Tiny')
for family in ('Book','Sans','Serif','Mono'):
    for size,height in [('Tiny',11),('Small',13),('Medium',16),('Large',21)]:
        FONT_FILES[f'{family.lower()}_{size.lower()}']=f'BetaWise{family}-{size}'
FONT_HEIGHTS = dict(small=11,medium=13,large=16,vlarge=21,xlarge=32,tiny=6,terminal=8,terminal_small=7)
FONT_HEIGHTS.update({key:{'Tiny':11,'Small':13,'Medium':16,'Large':21}[stem.split('-')[1]] for key,stem in FONT_FILES.items()})
MENU_FONTS = ('schoolbook','helvetica','times')


def font_image(key):
    stem=FONT_FILES[key]
    return FONT_ROOT/stem/(stem+'.OS3KApp')


def private_bdf(key):
    stem=FONT_FILES[key]
    return FONT_ROOT/'bdf'/stem.split('-')[0]/'private'/(stem+'-SmallCaps.bdf')
