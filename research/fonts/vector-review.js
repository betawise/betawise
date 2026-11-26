'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const faces = VECTOR_DATA.faces;
  const byId = new Map(faces.map(f => [f.id,f]));
  const storage = 'betawise-vector-choices-v1';
  const hex = n => n.toString(16).toUpperCase().padStart(2,'0');
  const key = (f,s) => f.id+'#'+hex(s);
  let choices = new Map(), notes = new Map(), flags = VECTOR_DATA.flags.slice();
  let slot = 67, preview = null;
  const char = s => VECTOR_DATA.characters[s]?.char || '?';
  const face = () => faces.find(f => f.family === $('family').value && f.size === $('size').value && f.style === $('style').value);
  function options(element,items,value) {
    element.replaceChildren();
    for (const [v,label] of items) { const o=document.createElement('option');o.value=v;o.textContent=label;element.append(o); }
    element.value=items.some(([v])=>v===value)?value:items[0]?.[0];
  }
  options($('family'),[...new Set(faces.map(f=>f.family))].map(f=>[f,f]),'BetaWise Mono');
  function filters() {
    const available=faces.filter(f=>f.family===$('family').value);
    const sizes=['Large','Medium','Small','Tiny'].filter(s=>available.some(f=>f.size===s));
    options($('size'),sizes.map(s=>[s,s]),$('size').value||'Small');
    const styles=['Regular','Bold','Italic','BoldItalic'].filter(s=>available.some(f=>f.size===$('size').value&&f.style===s));
    options($('style'),styles.map(s=>[s,s==='BoldItalic'?'Bold italic':s]),$('style').value||'Regular');
  }
  filters();
  options($('group'),VECTOR_DATA.groups.map(g=>[g,g]),'CGOQ');
  function validChoice(item) {
    const f=byId.get(item?.font),s=item?.slot;
    if (!f||!Number.isInteger(s)||s<0||s>255||item.height!==f.height||item.baseline!==f.baseline) throw Error('Choice references an unknown or changed font cell.');
    const original=f.glyphs[s];
    if (JSON.stringify(item.original)!==JSON.stringify(original)) throw Error('The original glyph changed; review this choice again.');
    if(item.unicode!==char(s).codePointAt(0))throw Error('Choice character mapping changed.');
    if(item.candidate!==null) {
      const expected=f.alternatives[s].find(c=>c.id===item.candidate?.id);
      if(!expected||Object.keys(expected).some(k=>JSON.stringify(expected[k])!==JSON.stringify(item.candidate[k]))||JSON.stringify(item.source)!==JSON.stringify(f.sources[expected.source]))throw Error('Candidate or source is absent or changed; review it again.');
    }else if(item.source!==null)throw Error('Keep-current choice cannot have a vector source.');
    return key(f,s);
  }
  function importData(data) {
    if (data?.format==='betawise-font-fixes-v1') {
      const next=[];
      for (const g of data.glyphs||[]) {
        if (!byId.has(g.font)||!Number.isInteger(g.slot)||g.slot<0||g.slot>255) throw Error('Invalid flagged font/glyph.');
        next.push({font:g.font,slot:g.slot});
      }
      flags=next; save(); if(flags.length) navigate(flags[0]); render(); return;
    }
    if(data?.format!=='betawise-vector-choices-v1'||!Array.isArray(data.choices)) throw Error('Expected glyph flags or vector choices JSON.');
    const next=new Map();
    for(const item of data.choices) { const k=validChoice(item);if(next.has(k))throw Error('Duplicate choice.');next.set(k,item); }
    const nextNotes=new Map(data.choices.filter(c=>c.note).map(c=>[key(byId.get(c.font),c.slot),c.note]));
    for(const n of data.notes||[]) {if(!byId.has(n.font)||!Number.isInteger(n.slot)||n.slot<0||n.slot>255||typeof n.note!=='string')throw Error('Invalid review note.');nextNotes.set(key(byId.get(n.font),n.slot),n.note);}
    choices=next;notes=nextNotes;save();render();
  }
  function exportData() { return {format:'betawise-vector-choices-v1',freetype:VECTOR_DATA.freetype,notes:[...notes].map(([k,note])=>({font:k.slice(0,k.lastIndexOf('#')),slot:parseInt(k.slice(k.lastIndexOf('#')+1),16),note})),choices:[...choices.values()].map(c=>({...c,note:notes.get(key(byId.get(c.font),c.slot))||''}))}; }
  function save() {
    try { localStorage.setItem(storage,JSON.stringify({data:exportData(),flags})); }
    catch { $('action').textContent='Browser storage unavailable; export JSON to save your choices.'; }
  }
  try {
    const stored=JSON.parse(localStorage.getItem(storage)||'null');
    if(stored) {
      for(const item of stored.data.choices) { try { choices.set(validChoice(item),item);if(item.note)notes.set(key(byId.get(item.font),item.slot),item.note); }catch{} }
      for(const n of stored.data.notes||[])if(byId.has(n.font)&&Number.isInteger(n.slot)&&n.slot>=0&&n.slot<256&&typeof n.note==='string')notes.set(key(byId.get(n.font),n.slot),n.note);
      if(Array.isArray(stored.flags)&&stored.flags.every(g=>byId.has(g.font)&&Number.isInteger(g.slot)&&g.slot>=0&&g.slot<256))flags=stored.flags;
    }
  }catch{}
  function drawInto(canvas,g,height,zoom,baseline=null) {
    canvas.width=g.width*zoom;canvas.height=height*zoom;
    const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,canvas.width,canvas.height);
    const bytes=Uint8Array.from(atob(g.bits),c=>c.charCodeAt(0)),stride=Math.ceil(g.width/8);
    ctx.fillStyle='black';
    for(let y=0;y<height;y++)for(let x=0;x<g.width;x++)if(bytes[y*stride+(x>>3)]&(128>>(x&7)))ctx.fillRect(x*zoom,y*zoom,zoom,zoom);
    if(baseline!==null&&baseline<height){ctx.fillStyle='#277cac';for(let x=0;x<g.width;x++)if(!(bytes[baseline*stride+(x>>3)]&(128>>(x&7))))ctx.fillRect(x*zoom,baseline*zoom,zoom,1);}
  }
  function drawing(f,g,zoom=Number($('zoom').value)) {
    const canvas=document.createElement('canvas');
    if(g)drawInto(canvas,g,f.height,zoom,f.baseline);
    return canvas;
  }
  function currentOrChosen(f,s,useChoice) {
    if(useChoice&&preview&&preview.font===f.id&&preview.slot===s)return preview.candidate;
    const selected=useChoice?choices.get(key(f,s)):null;
    return selected?.candidate||f.glyphs[s]||f.glyphs[63];
  }
  function sample(canvas,f,useChoice,text,zoom=2,screen=true) {
    const codes=[...text].map(c=>c==='\n'?-1:VECTOR_DATA.characters.findIndex(info=>info?.char===c));
    const width=screen?264:Math.max(1,codes.reduce((n,s)=>n+(s<0?0:currentOrChosen(f,s,useChoice).width),0));
    canvas.width=width*zoom;canvas.height=(screen?65:f.height)*zoom;
    const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='black';
    let x=0,y=0;
    for(let s of codes) {
      if(s===-1){x=0;y+=f.height;continue;}
      if(s<0)s=63;
      const g=currentOrChosen(f,s,useChoice),stride=Math.ceil(g.width/8),bytes=Uint8Array.from(atob(g.bits),c=>c.charCodeAt(0));
      if(x+g.width>width){x=0;y+=f.height;}
      if(y+f.height>canvas.height/zoom)break;
      for(let yy=0;yy<f.height;yy++)for(let xx=0;xx<g.width;xx++)if(bytes[yy*stride+(xx>>3)]&(128>>(xx&7)))ctx.fillRect((x+xx)*zoom,(y+yy)*zoom,zoom,zoom);
      x+=g.width;
    }
  }
  function renderSamples() {
    const f=face();sample($('sample-current'),f,false,$('sample').value);sample($('sample-chosen'),f,true,$('sample').value);
  }
  function navigate(target) {
    const f=byId.get(target.font);$('family').value=f.family;filters();$('size').value=f.size;filters();$('style').value=f.style;slot=target.slot;$('glyph').value=char(slot);
  }
  function choose(candidate) {
    const f=face();preview=null;
    choices.set(key(f,slot),{font:f.id,slot,unicode:char(slot).codePointAt(0),height:f.height,baseline:f.baseline,
      original:f.glyphs[slot],candidate,source:candidate?f.sources[candidate.source]:null});
    save();render();
  }
  function render() {
    const f=face(),selected=choices.get(key(f,slot));preview=null;
    options($('source'),[['all','All outline sources'],...f.sources.map(s=>[s.name,s.name])],$('source').value);
    $('source-availability').textContent=(f.skippedSources||[]).map(s=>s.name+': '+s.reason).join(' · ');
    $('heading').textContent=`${f.family} ${f.sizeLabel} ${f.style} · 0x${hex(slot)} ${char(slot)} — ${VECTOR_DATA.characters[slot]?.name||''}`;
    const changed=[...choices.values()].filter(c=>c.candidate).length;
    $('status').textContent=`${faces.length} bitmap faces · ${flags.length} flagged cells · ${choices.size} reviewed (${changed} replacements selected). Choices preserve spacing and baseline.`;
    $('dimensions').textContent=`Cell: ${(f.glyphs[slot]||f.glyphs[63]).width} × ${f.height}px; baseline ${f.baseline}; capital A ${f.targetCap}px, x-height ${f.targetX}px. Blue line marks the baseline.`;
    const nav=$('group-nav'),context=$('context');nav.replaceChildren();context.replaceChildren();
    for(const letter of $('group').value) {
      if(letter===' ')continue;
      const s=VECTOR_DATA.characters.findIndex(info=>info?.char===letter);if(s<0)continue;
      const b=document.createElement('button');b.textContent=letter;b.setAttribute('aria-current',String(s===slot));b.onclick=()=>{slot=s;$('glyph').value=letter;render();};nav.append(b);
      const article=document.createElement('article'),title=document.createElement('span');title.textContent=letter+' · current / selected';article.append(title);
      const pair=document.createElement('div');pair.className='pair';pair.append(drawing(f,currentOrChosen(f,s,false),3),drawing(f,currentOrChosen(f,s,true),3));article.append(pair);context.append(article);
    }
    const cards=$('candidates');cards.replaceChildren();
    function card(candidate) {
      const keep=candidate===null,g=keep?f.glyphs[slot]:candidate;
      const button=document.createElement('button');button.className='candidate';button.dataset.id=keep?'current':candidate.id;
      button.setAttribute('aria-pressed',String(!!selected&&(keep?selected.candidate===null:selected.candidate?.id===candidate.id)));
      const title=document.createElement('span');title.className='title';title.textContent=keep?'Keep current bitmap':f.sources[candidate.source].name;button.append(title);
      const draw=document.createElement('div');draw.className='drawing';
      if(g)draw.append(drawing(f,g));else {const missing=document.createElement('span');missing.textContent='Missing artwork';draw.append(missing);}
      button.append(draw);
      const metrics=document.createElement('span');metrics.className='metrics';
      if(keep)metrics.textContent=f.originalChecks[slot]?`${f.originalChecks[slot].ink} pixels · ${f.originalChecks[slot].parts} parts · ${f.originalChecks[slot].holes} counters`:'The applet currently uses its ? fallback.';
      else metrics.textContent=`${candidate.hint==='native'?'Native':'Auto'} hints · ${candidate.ppem}px em · phase ${candidate.phase? '½':'0'} · horizontal shift ${candidate.shift}\nCapital ${candidate.cap}px / x ${candidate.xheight}px · ink width ${candidate.inkWidth}px (${candidate.widthDelta>=0?'+':''}${candidate.widthDelta})\n${candidate.checks.ink} pixels · ${candidate.checks.parts} parts · ${candidate.checks.holes} counters\nReference advance ${candidate.sourceAdvance}px; kept advance ${candidate.width}px`;
      metrics.style.whiteSpace='pre-line';button.append(metrics);button.onclick=()=>choose(candidate);
      if(!keep){button.onmouseenter=button.onfocus=()=>{preview={font:f.id,slot,candidate};renderSamples();};button.onmouseleave=button.onblur=()=>{preview=null;renderSamples();};}
      cards.append(button);
    }
    card(null);
    const alternatives=f.alternatives[slot].filter(c=>($('hint').value==='all'||c.hint===$('hint').value)&&($('source').value==='all'||f.sources[c.source].name===$('source').value));
    alternatives.forEach(card);
    $('empty').hidden=alternatives.length>0;
    $('empty').textContent=`No distinct fitting alternatives for this filter. ${f.candidateStats[slot].overflow} placements exceeded the cell; missing source glyphs or identical renderings can also leave no alternatives. The existing glyph is kept.`;
    $('note').value=notes.get(key(f,slot))||'';
    $('sources').textContent=f.sources.map(s=>`${s.name}\n${s.path}\n${s.provenance}\n${s.license}${s.hinting?'\n'+s.hinting:''}`).join('\n\n')+`\n\nFreeType ${VECTOR_DATA.freetype}; native hints and auto-hinter, monochrome. No embedded bitmap strikes.`;
    $('styles').replaceChildren();
    for(const other of faces.filter(o=>o.family===f.family&&o.size===f.size)) {
      const article=document.createElement('article'),label=document.createElement('p');label.textContent=other.style+' · current / selected';article.append(label);
      for(const chosen of [false,true]) {const canvas=document.createElement('canvas');sample(canvas,other,chosen,$('group').value,3,false);article.append(canvas);}
      const go=document.createElement('button');go.textContent='Review '+other.style;go.onclick=()=>{$('style').value=other.style;render();};article.append(go);$('styles').append(article);
    }
    renderSamples();
  }
  $('family').onchange=()=>{filters();render();};$('size').onchange=()=>{filters();render();};
  for(const id of ['style','group','zoom','hint','source'])$(id).onchange=render;
  $('go').onclick=()=>{const value=$('glyph').value.trim();const s=/^0x[0-9a-f]{1,2}$/i.test(value)?parseInt(value.slice(2),16):VECTOR_DATA.characters.findIndex(info=>info?.char===value);if(s<0||s>255){$('error').textContent='Enter a mapped character or byte such as 0x43.';return;}slot=s;$('error').textContent='';render();};
  $('glyph').onkeydown=e=>{if(e.key==='Enter')$('go').click();};
  $('sample').oninput=renderSamples;
  $('note').oninput=()=>{notes.set(key(face(),slot),$('note').value);save();};
  $('unreview').onclick=()=>{choices.delete(key(face(),slot));notes.delete(key(face(),slot));save();render();};
  function nextFlag(direction) {if(!flags.length){$('action').textContent='Import a glyph-review JSON file to navigate flagged cells.';return;}const index=flags.findIndex(g=>g.font===face().id&&g.slot===slot);navigate(flags[index<0?(direction>0?0:flags.length-1):(index+direction+flags.length)%flags.length]);render();}
  $('previous').onclick=()=>nextFlag(-1);$('next').onclick=()=>nextFlag(1);
  $('import').onchange=async e=>{try{if(e.target.files.length)importData(JSON.parse(await e.target.files[0].text()));$('error').textContent='';}catch(error){$('error').textContent=error.message;}e.target.value='';};
  $('export').onclick=()=>{const blob=new Blob([JSON.stringify(exportData(),null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='betawise-vector-choices.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  globalThis.BetaWiseVectorReview=Object.freeze({exportSelections:exportData,importSelections:importData});
  render();
})();
