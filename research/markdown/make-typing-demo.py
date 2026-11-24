#!/usr/bin/env python3
"""Animation of validated LCD checkpoints; diagnostic artifact, never an oracle."""
import argparse,json
from pathlib import Path
from PIL import Image
ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--last-checkpoint',type=int);a=ap.parse_args()
results=json.loads((a.run/'results.json').read_text());frames=[]
for i,r in enumerate(results,1):
 if a.last_checkpoint and i>a.last_checkpoint:break
 if 'bitmap' not in r:continue
 assert results[i-1]['bitmap']['differing_pixels']==0
 im=Image.open(a.run/f'comparison-{i:02d}.actual.png').convert('RGB')
 frames.append(im.resize((1056,256),Image.Resampling.NEAREST))
a.output.parent.mkdir(parents=True,exist_ok=True)
frames[0].save(a.output,save_all=True,append_images=frames[1:],duration=[900]*(len(frames)-1)+[1800],loop=0)
print(a.output)
