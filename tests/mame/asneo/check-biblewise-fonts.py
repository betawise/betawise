#!/usr/bin/env python3
"""Check source-backed small-cap geometry and LCD output across every demo font."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
from bible_layout import captured_font

HERE = Path(__file__).resolve().parent
from bible_fonts import FONT_FILES
FONTS = [key for key in FONT_FILES if '_' in key] + ['small','terminal','system']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    def run(font):
        output = args.output/font
        command = [sys.executable,str(HERE/'check-biblewise.py'),'--version','NKJV',
            '--case','formatting','--format-smoke','--output',str(output)]
        if font!='system': command += ['--vendor-font',font]
        with (args.output/(font+'.log')).open('w') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        profile = captured_font(output,2)
        metrics = {}
        for letter in 'Hx':
            width=profile['widths'][ord(letter)];glyph=profile['glyphs'][ord(letter)]
            rows=[y for y in range(profile['height'])for x in range(width)
                if glyph[y//8*width+x]>>(y%8)&1]
            metrics[letter]=[min(rows),max(rows)]
        result=dict(font=font,cell_height=profile['height'],ink_rows=metrics,
            checkpoints=2,report=str(output/'results.json'))
        print('PASS',font,metrics,flush=True)
        return result
    # Each emulator owns a separate disposable flash/RAM and build directory.
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,FONTS))
    # These share Terminal Medium's applet ID and BibleWise build directory.
    # Keep their builds outside the parallel pool to avoid linker races.
    results += [run(font) for font in ('terminal_small', 'tiny')]
    (args.output/'results.json').write_text(json.dumps(dict(status='passed',fonts=results),indent=2)+'\n')

if __name__ == '__main__': main()
