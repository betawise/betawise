#!/usr/bin/env python3
"""Extract TI-83 Plus small numerals from TI's developer-guide pixel grids.

Usage: python3 import_ti_digits.py /path/to/sdk83pguide.pdf
Requires PyMuPDF only for this optional source-import step, not font builds.
"""
import argparse,io,json
from pathlib import Path
import fitz
from PIL import Image
URL='https://education.ti.com/-/media/672891A1E98349CAB91C11B4928C253C'

def extract(path):
    document=fitz.open(path);page=document[180]
    text=page.get_text()
    assert '30h' in text and '39h' in text and 'S0' in text and 'S9' in text
    info=page.get_image_info(xrefs=True)
    assert len(info)==32
    rendered=page.get_pixmap(matrix=fitz.Matrix(4,4),colorspace=fitz.csGRAY)
    columns=[]
    for digit,record in enumerate(info[16:26]):
        image=Image.open(io.BytesIO(document.extract_image(record['xref'])['image'])).convert('L')
        assert image.size==(34,58)
        a,b,c,d,e,f=record['transform'];assert a>0 and b==c==0 and d<0
        grid=[]
        for y in range(7):
            row=[]
            for x in range(4):
                values={image.getpixel((xx,yy)) for xx in range(3+x*8,7+x*8) for yy in range(3+y*8,7+y*8)}
                assert len(values)==1
                value=values.pop();assert value in (0,255)
                # Verify the extracted image orientation against the rendered PDF.
                px=int((a*(4+x*8)/image.width+e)*4)
                py=int((d*(4+y*8)/image.height+f)*4)
                assert rendered.pixel(px,py)[0]==value
                row.append(int(value==0))
            grid.append(row)
        grid.reverse() # PDF embeds these chart images upside-down.
        assert grid[0]==grid[-1]==[0]*4
        assert all(row[3]==0 for row in grid)
        columns.append([sum(grid[y+1][x]<<y for y in range(5))for x in range(4)])
    return dict(description='Shared BetaWise fallback numerals: TI-83/84 graph-screen small font, with three ink columns and a four-pixel advance.',
                height=5,advance=4,alignment='top of unaccented H in the regular body face',
                source=dict(name='TI-83 Plus Developer Guide, third release, Appendix B',url=URL,pdf_page=181,printed_page=164,codes='30h–39h'),columns=columns)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf',type=Path)
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('superscript-3x5.json'))
    args=parser.parse_args();data=extract(args.pdf)
    args.output.write_text(json.dumps(data,indent=2)+'\n')
    print(data['columns']);print(args.output)
if __name__=='__main__':main()
