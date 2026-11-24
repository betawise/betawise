from pathlib import Path
import sys,json,hashlib
from PIL import Image,ImageDraw,ImageFont
root=Path('/home/kirk/Projects/Alphasmart/betawise')
sys.path.insert(0,str(root/'tests/mame/asneo'))
from neo_reader import lcd_frames
out=root/'research/syscalls/dialog/screenshots'
layouts=[5,6,7,8,9,11,12,13,14,15,16,17,18,19,20,21]
labels={5:'Five regions / two inputs',6:'Three regions / two inputs',7:'Title, input and body',8:'Line selection',9:'Shared geometry with 8',11:'Title / 40:60 columns',12:'Choice input',13:'Title and body',14:'Underlined input',15:'Editable input',16:'Main / two lower regions',17:'Three regions / choice input',18:'Variant of layout 8',19:'Title / equal columns',20:'Title / titled columns',21:'Title / body and input columns'}
sheet=Image.new('RGB',(1640,8*240+20),'#e8e8e8');draw=ImageDraw.Draw(sheet)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
manifest=[]
for i,n in enumerate(layouts):
 p=out/f'layout-{n}.lcd.json';frames=lcd_frames(p)
 im=Image.new('RGB',(264,64));im.putdata([(0,0,0) if x else (255,255,255) for x in frames[0]])
 im.save(out/f'layout-{n}.png')
 big=im.resize((792,192),Image.Resampling.NEAREST);big.save(out/f'layout-{n}@3x.png')
 x=16+(i%2)*820;y=12+(i//2)*240
 draw.text((x,y),f'{n}: {labels[n]}',fill='black',font=font)
 sheet.paste(big,(x,y+30))
 manifest.append({'layout':n,'lcd_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'stable_samples':len(frames),'black_pixels':sum(frames[0]),'description':labels[n]})
sheet.save(out/'font-dialogs.png')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Rendered all 16 layouts from stable raw LCD records. Contact sheet:',out/'font-dialogs.png')
