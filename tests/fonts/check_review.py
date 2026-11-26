#!/usr/bin/env python3
"""Exercise the offline glyph picker in an isolated headless Chromium profile.

Uses DOM actions and exact canvas pixels, never screenshots or model inference.
"""
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST = r'''
(async () => {
  const output = document.createElement('pre');
  output.id = 'review-test-result';
  const assert = (condition, message) => { if (!condition) throw Error(message); };
  const change = (id, value) => {
    const input = document.getElementById(id); input.value = value;
    input.dispatchEvent(new Event('change'));
  };
  const click = slot => document.querySelector(`button.glyph[data-slot="${slot}"]`).click();
  const glyphs = () => BetaWiseReview.exportSelections().glyphs;
  const selected = (font, slot) => glyphs().some(g => g.font.includes(font) && g.slot === slot);
  try {
    assert(FONT_DATA.faces.length === 67, '67 source faces');
    assert(BetaWiseReview.exportSelections().mapping.find(m => m.slot === 4)?.state === 'confirmed', 'applied proposals migrate to confirmed');
    assert(FONT_DATA.characters[60].char === '<', 'JSON glyph characters survive HTML escaping');
    assert(document.querySelectorAll('button.glyph').length === 256, 'all byte slots visible');
    const face = FONT_DATA.faces.find(f => f.family === 'BetaWise Serif' && f.size === 'Small' && f.style === 'Regular');
    const canvas = document.querySelector('button.glyph[data-slot="99"] canvas');
    const rgba = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    let black = 0;
    for (let i = 0; i < rgba.length; i += 4) if (!rgba[i] && !rgba[i+1] && !rgba[i+2]) black++;
    const glyph = face.glyphs[99], bytes = Uint8Array.from(atob(glyph.bits), c => c.charCodeAt(0));
    let expected = 0;
    for (let y = 0; y < face.height; y++) for (let x = 0; x < glyph.width; x++)
      if (bytes[y * Math.ceil(glyph.width / 8) + (x >> 3)] & (0x80 >> (x & 7))) expected++;
    assert(black === expected * 25, 'integer source canvas pixels');
    click(99);
    assert(glyphs().length === 2 && selected('Serif', 99) && selected('Serif', 231), 'c selects ç in the same face');
    click(67);
    assert(selected('Serif', 199) && !selected('Serif', 65), 'C selects Ç, not A');
    click(65);
    for (const slot of [65,192,193,194,195,196,197]) assert(selected('Serif',slot), 'A accent group ' + slot);
    click(78);
    assert(selected('Serif',4) && selected('Serif',209), 'N includes both Neo Ń and Ñ');
    assert(glyphs().find(g => g.slot === 4).implemented === true, 'newly mapped N acute artwork imported');
    assert(face.glyphs[6] === null && FONT_DATA.characters[6] !== null, 'known mapping separate from unavailable artwork');
    click(231);
    assert(!selected('Serif',231) && selected('Serif',99), 'accent can be individually unflagged');
    document.getElementById('undo').click();
    assert(selected('Serif',231), 'undo restores a grouped flag');
    change('family','BetaWise Terminal'); change('size','Medium');
    click(78);
    assert(selected('Terminal',4) && selected('Terminal',209), 'Terminal shares the Neo mapping');
    click(0x60);
    assert(selected('Terminal',0x90), 'grave aliases group together');
    click(0x0d);
    assert(selected('Terminal',0x16), 'return aliases group together');
    assert(glyphs().every(g => g.style === 'Regular'), 'no other styles changed');
    const saved = BetaWiseReview.exportSelections();
    BetaWiseReview.importSelections({format:'betawise-font-fixes-v1',glyphs:[],mapping:[]});
    assert(!glyphs().length, 'import replaces flags');
    const transfer = new DataTransfer();
    transfer.items.add(new File([JSON.stringify(saved)],'fixes.json',{type:'application/json'}));
    document.getElementById('import').files = transfer.files;
    await document.getElementById('import').onchange({target:document.getElementById('import')});
    assert(glyphs().length === saved.glyphs.length, 'file-input import round trip');
    let rejected = false;
    try { BetaWiseReview.importSelections({format:'betawise-font-fixes-v1',glyphs:[{font:face.id,slot:256}]}); } catch { rejected=true; }
    assert(rejected && glyphs().length === saved.glyphs.length, 'invalid import is atomic');
    change('mode','mapping');
    assert(document.querySelectorAll('.mapping-card').length === 38, 'only beyond-printable-1252 slots');
    assert(!document.querySelector('.mapping-card[data-slot="65"]'), 'ordinary ASCII mapping omitted');
    const card = document.querySelector('.mapping-card[data-slot="4"]');
    assert(card.querySelector('h2').textContent.includes('Ń'), 'Neo alias label');
    assert(card.querySelectorAll('canvas').length === 2, 'system and Terminal references');
    card.querySelector('[data-mapping-state="confirmed"]').click();
    const sigma = document.querySelector('.mapping-card[data-slot="31"] input');
    sigma.value='Σ'; sigma.dispatchEvent(new Event('change'));
    let report = BetaWiseReview.exportSelections();
    assert(report.mapping.find(m => m.slot === 4).currentUnicode === 323, 'mapping export carries original identity');
    assert(report.mapping.find(m => m.slot === 31).unicode === 931, 'Unicode mapping proposal');
    assert(JSON.parse(localStorage.getItem('betawise-glyph-fixes-v1')).flags.length === glyphs().length, 'saved selections');
    let download;
    const oldCreate = URL.createObjectURL, oldClick = HTMLAnchorElement.prototype.click;
    URL.createObjectURL = blob => { download=blob; return 'blob:review-test'; };
    HTMLAnchorElement.prototype.click = function() {};
    document.getElementById('export').click();
    assert(JSON.parse(await download.text()).mapping.length === 2, 'JSON download');
    URL.createObjectURL=oldCreate; HTMLAnchorElement.prototype.click=oldClick;
    change('mode','glyphs'); document.getElementById('all').click();
    assert(document.querySelectorAll('details[data-face]').length === 67, 'all faces accessible');
    output.textContent=JSON.stringify({passed:true,faces:67,sourceGlyphs:FONT_DATA.faces.reduce((n,f)=>n+f.glyphs.filter(Boolean).length,0),mappingSlots:38,checks:20});
  } catch(error) {
    output.textContent=JSON.stringify({passed:false,error:error.message,stack:error.stack});
  }
  document.body.append(output);
})();
'''


def main():
    chromium = shutil.which('chromium')
    if not chromium:
        raise SystemExit('Chromium is required for the review-page interaction check.')
    with tempfile.TemporaryDirectory(prefix='betawise-review-check-') as directory:
        directory = Path(directory)
        page = directory / 'review.html'
        subprocess.run(['python3', str(ROOT / 'research/fonts/review.py'), '--output', str(page)], check=True)
        seed = "<script>localStorage.setItem('betawise-glyph-fixes-v1', JSON.stringify({flags:[],mappings:{4:{state:'change',unicode:323}}}));</script>"
        content = page.read_text().replace("<script>'use strict';", seed + "<script>'use strict';")
        page.write_text(content.replace('</html>', '<script>' + TEST + '</script></html>'))
        result = subprocess.run([
            chromium, '--headless', '--no-sandbox', '--disable-dev-shm-usage',
            '--disable-gpu', '--no-first-run', '--no-default-browser-check',
            '--user-data-dir=' + str(directory / 'profile'), '--virtual-time-budget=2500',
            '--dump-dom', page.as_uri(),
        ], capture_output=True, text=True, timeout=45)
        match = re.search(r'<pre id="review-test-result">(.*?)</pre>', result.stdout, re.S)
        if not match:
            raise SystemExit('Browser test did not finish:\n' + result.stderr[-3000:])
        report = json.loads(html.unescape(match[1]))
        if not report['passed']:
            raise SystemExit(json.dumps(report, indent=2))
        print('PASS glyph clicks, accent groups, Neo aliases, per-face scope, exact canvas pixels, '
              'undo, storage, import/export, mapping proposals and all 67 faces')


if __name__ == '__main__':
    main()
