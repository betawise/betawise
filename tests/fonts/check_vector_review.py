#!/usr/bin/env python3
"""Offline DOM interaction and exact canvas checks, isolated browser storage."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TEST = r'''
(() => {
 const result=document.createElement('pre');result.id='vector-test-result';
 const assert=(c,m)=>{if(!c)throw Error(m);};
 const set=(id,value)=>{const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('change'));};
 const show=value=>{document.getElementById('glyph').value=value;document.getElementById('go').click();};
 const api=BetaWiseVectorReview;
 try {
  assert(VECTOR_DATA.faces.length===67,'all 67 BDF faces');
  assert(document.querySelectorAll('#context article').length===4,'C/G/O/Q shown together');
  assert([...document.querySelectorAll('#group-nav button')].map(b=>b.textContent).join('')==='CGOQ','round-capital group');
  const f=VECTOR_DATA.faces.find(f=>f.family==='BetaWise Mono'&&f.size==='Small'&&f.style==='Regular');
  assert(f&&f.alternatives[67].length>0,'fitting Mono C alternatives');
  document.querySelector('#candidates .candidate:not([data-id=current])').click();
  let data=api.exportSelections(),choice=data.choices[0];
  assert(choice.slot===67&&choice.candidate.width===f.glyphs[67].width&&choice.height===f.height&&choice.baseline===f.baseline,'spacing and baseline preserved');
  assert(choice.source.path&&choice.source.license&&choice.source.provenance,'source provenance retained');
  assert(JSON.stringify(choice.original)===JSON.stringify(f.glyphs[67]),'original bitmap retained for conflict detection');
  const selected=document.querySelector('#candidates .candidate[aria-pressed=true] canvas');
  assert(selected.width===choice.candidate.width*6&&selected.height===f.height*6,'integer glyph enlargement');
  const rgba=selected.getContext('2d').getImageData(0,0,selected.width,selected.height).data;
  let black=0;for(let i=0;i<rgba.length;i+=4)if(rgba[i]===0&&rgba[i+1]===0&&rgba[i+2]===0)black++;
  assert(black===choice.candidate.checks.ink*36,'baseline guide preserves every ink pixel');
  const bytes=Uint8Array.from(atob(choice.candidate.bits),c=>c.charCodeAt(0));
  for(let y=0;y<f.height;y++)for(let x=0;x<choice.candidate.width;x++){
   if(y===f.baseline)continue;
   const expected=!!(bytes[y*Math.ceil(choice.candidate.width/8)+(x>>3)]&(128>>(x&7)));
   const offset=((y*6+2)*selected.width+x*6+2)*4;
   assert((rgba[offset]===0&&rgba[offset+1]===0&&rgba[offset+2]===0)===expected,'exact source canvas pixels');
  }
  const a=document.getElementById('sample-current'),b=document.getElementById('sample-chosen');
  assert(a.width===528&&a.height===130&&b.width===a.width,'264x65 specimen geometry');
  const aa=a.getContext('2d').getImageData(0,0,a.width,a.height).data,bb=b.getContext('2d').getImageData(0,0,b.width,b.height).data;
  assert(aa.some((v,i)=>v!==bb[i]),'selected candidate appears in contextual text');
  document.getElementById('note').value='Keep G bar clear of the left stem';document.getElementById('note').dispatchEvent(new Event('input'));
  show('O');document.querySelector('#candidates [data-id=current]').click();
  assert(api.exportSelections().choices.length===2,'keep-current decision recorded independently');
  set('style','Bold');assert(document.querySelectorAll('#styles article').length===4,'all four styles accessible');
  assert(!api.exportSelections().choices.some(c=>c.font.includes('-Bold.bdf')),'no automatic cross-style edit');
  set('style','Italic');show('C');
  if([...document.getElementById('source').options].some(o=>o.value==='Courier New')) {
   set('source','Courier New');
   assert(document.querySelectorAll('#candidates .candidate').length>1,'Courier New has its own candidate allowance');
   assert([...document.querySelectorAll('#candidates .candidate:not([data-id=current]) .title')].every(e=>e.textContent==='Courier New'),'source filter isolates Courier New');
  }
  set('style','Regular');assert(![...document.getElementById('source').options].some(o=>o.value==='Courier New'),'missing Courier Regular not synthesized');
  assert(document.getElementById('source-availability').textContent.includes('Courier New'),'partial family explained');
  set('family','BetaWise Sans');set('size','Small');set('style','Regular');show('C');
  for(const name of ['Liberation Sans','Arial','Verdana']){
   if([...document.getElementById('source').options].some(o=>o.value===name)) {
    set('source',name);assert(document.querySelectorAll('#candidates .candidate').length>1,'candidates retained for '+name);
   }else assert(document.getElementById('source-availability').textContent.includes(name),'optional missing source explained');
  }
  api.importSelections({format:'betawise-font-fixes-v1',glyphs:[{font:f.id,slot:67},{font:f.id,slot:71}]});
  document.getElementById('next').click();assert(document.getElementById('heading').textContent.includes('0x47'),'next flagged glyph');
  document.getElementById('previous').click();assert(document.getElementById('heading').textContent.includes('0x43'),'previous flagged glyph');
  data=api.exportSelections();const saved=JSON.stringify(data);
  const bad=JSON.parse(saved);bad.choices[0].candidate.bits='AAAA';let rejected=false;
  try{api.importSelections(bad);}catch{rejected=true;}assert(rejected&&JSON.stringify(api.exportSelections())===saved,'invalid candidate import atomic');
  const stale=JSON.parse(saved);stale.choices[0].original.bits='AAAA';rejected=false;
  try{api.importSelections(stale);}catch{rejected=true;}assert(rejected,'stale original bitmap rejected');
  api.importSelections({format:'betawise-vector-choices-v1',choices:[]});assert(!api.exportSelections().choices.length,'empty import');
  api.importSelections(data);assert(JSON.stringify(api.exportSelections())===saved,'export/import round trip includes review notes');
  assert(JSON.parse(localStorage.getItem('betawise-vector-choices-v1')).data.choices.length===2,'browser persistence');
  document.getElementById('unreview').click();assert(api.exportSelections().choices.length===1,'unreview decision');
  result.textContent=JSON.stringify({passed:true,faces:67,checks:'glyph selection, canvas, geometry, styles, groups, flags, provenance, storage and atomic import'});
 }catch(error){result.textContent=JSON.stringify({passed:false,error:error.message,stack:error.stack});}
 document.body.append(result);
})();
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page',type=Path,default=ROOT/'research/fonts/build/vector-review.html')
    args=parser.parse_args()
    if not args.page.exists():
        subprocess.run(['make', '-C', str(ROOT/'research/fonts'), 'vector-review'], check=True)
    browser=shutil.which('chromium')
    if not browser:raise SystemExit('Chromium required')
    with tempfile.TemporaryDirectory(prefix='betawise-vector-check-')as directory:
        directory=Path(directory);page=directory/'review.html'
        page.write_text(args.page.read_text().replace('</html>','<script>'+TEST+'</script></html>'))
        result=subprocess.run([browser,'--headless','--no-sandbox','--disable-dev-shm-usage',
            '--disable-gpu','--no-first-run','--no-default-browser-check',
            '--user-data-dir='+str(directory/'profile'),'--virtual-time-budget=5000',
            '--dump-dom',page.as_uri()],capture_output=True,text=True,timeout=60)
        match=re.search(r'<pre id="vector-test-result">(.*?)</pre>',result.stdout,re.S)
        if not match:raise SystemExit('Browser check did not finish:\n'+result.stderr[-2000:])
        report=json.loads(html.unescape(match[1]))
        if not report['passed']:raise SystemExit(json.dumps(report,indent=2))
        print('PASS',report)


if __name__=='__main__':main()
