'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const faces = FONT_DATA.faces;
  const byId = new Map(faces.map(face => [face.id, face]));
  const storageKey = 'betawise-glyph-fixes-v1';
  let flags = new Set();
  let mappings = {};
  let history = [];
  let openFaces = new Set();
  let storageAvailable = true;
  const hex = slot => slot.toString(16).toUpperCase().padStart(2, '0');
  const key = (face, slot) => face.id + '#' + hex(slot);
  const character = slot => FONT_DATA.characters[slot];

  function snapshot() {
    return {flags: [...flags], mappings: JSON.parse(JSON.stringify(mappings))};
  }
  function save() {
    try { localStorage.setItem(storageKey, JSON.stringify(snapshot())); }
    catch { storageAvailable = false; }
    $('undo').disabled = !history.length;
  }
  function remember() {
    history.push(snapshot());
    if (history.length > 50) history.shift();
  }
  function validKey(value) {
    if (typeof value !== 'string') return false;
    const split = value.lastIndexOf('#');
    return byId.has(value.slice(0, split)) && /^[0-9A-F]{2}$/.test(value.slice(split + 1));
  }
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) || '{}');
    flags = new Set((stored.flags || []).filter(validKey));
    mappings = stored.mappings || {};
    // A saved proposal that is now in the shared map has been applied.
    for (const [slot, review] of Object.entries(mappings)) {
      const current = FONT_DATA.characters[slot]?.char.codePointAt(0) ?? null;
      if (review.state === 'change' && Number.isInteger(review.unicode) && review.unicode === current) {
        mappings[slot] = {state: 'confirmed'};
      }
    }
  } catch { storageAvailable = false; }

  function options(element, items, selected) {
    element.replaceChildren();
    for (const [value, label] of items) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      element.append(option);
    }
    element.value = items.some(([value]) => value === selected) ? selected : items[0][0];
  }
  options($('family'), [['all', 'All families'], ...[...new Set(faces.map(f => f.family))].map(v => [v, v])], 'BetaWise Serif');
  function updateFilters() {
    const matching = faces.filter(f => $('family').value === 'all' || f.family === $('family').value);
    const sizes = ['Large', 'Medium', 'Small', 'Tiny'].filter(s => matching.some(f => f.size === s));
    options($('size'), [['all', 'All sizes'], ...sizes.map(s => [s, s])], $('size').value || 'Small');
    const styles = ['Regular', 'Bold', 'Italic', 'BoldItalic'].filter(s => matching.some(f => f.style === s));
    options($('style'), [['all', 'All faces'], ...styles.map(s => [s, s === 'BoldItalic' ? 'Bold italic' : s])], $('style').value || 'Regular');
  }
  updateFilters();

  function status(message = '') {
    const selectedFonts = new Set([...flags].map(k => k.slice(0, k.lastIndexOf('#'))));
    const reviewed = Object.values(mappings).filter(m => m.state === 'confirmed').length;
    const changed = Object.values(mappings).filter(m => m.state === 'change').length;
    $('status').textContent = `${faces.length} faces · ${flags.size} glyph slots flagged in ${selectedFonts.size} faces · mapping: ${reviewed} confirmed, ${changed} need changes.`;
    if (!storageAvailable) $('status').textContent += ' Browser storage unavailable—export JSON to save.';
    if (message) $('action').textContent = message;
    $('undo').disabled = !history.length;
  }

  function draw(glyph, height, baseline = null) {
    const zoom = Number($('scale').value);
    const canvas = document.createElement('canvas');
    canvas.width = glyph.width * zoom;
    canvas.height = height * zoom;
    canvas.setAttribute('aria-hidden', 'true');
    const context = canvas.getContext('2d');
    context.fillStyle = '#fff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    if ($('baseline').checked && baseline !== null) {
      context.fillStyle = '#b9d9ec';
      context.fillRect(0, baseline * zoom, canvas.width, 1);
    }
    const bytes = Uint8Array.from(atob(glyph.bits), c => c.charCodeAt(0));
    const stride = Math.ceil(glyph.width / 8);
    context.fillStyle = '#000';
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < glyph.width; x++) {
        if (bytes[y * stride + (x >> 3)] & (0x80 >> (x & 7))) context.fillRect(x * zoom, y * zoom, zoom, zoom);
      }
    }
    return canvas;
  }

  function refreshMarks() {
    document.querySelectorAll('button.glyph').forEach(button => {
      const marked = flags.has(button.dataset.key);
      button.setAttribute('aria-pressed', String(marked));
      button.querySelector('.tag').textContent = marked ? '✓ Fix' : button.dataset.label;
    });
    document.querySelectorAll('details[data-face]').forEach(section => {
      const face = byId.get(section.dataset.face);
      const count = [...flags].filter(k => k.startsWith(face.id + '#')).length;
      section.querySelector('.count').textContent = count ? ` · ${count} flagged` : '';
    });
    status();
  }

  function toggleGlyph(face, slot, single) {
    remember();
    const char = character(slot)?.char;
    let targets = [slot];
    if (!single && $('accents').checked && char) {
      targets = targets.concat(FONT_DATA.characters.flatMap((info, code) =>
        code !== slot && info && (info.char === char ||
          (/^[A-Za-z]$/.test(char) && info.base === char)) ? [code] : []));
    }
    const add = !flags.has(key(face, slot));
    for (const code of targets) {
      if (add) flags.add(key(face, code));
      else flags.delete(key(face, code));
    }
    save();
    if ($('flagged').checked) render();
    else refreshMarks();
    status(`${add ? 'Flagged' : 'Unflagged'} ${targets.map(c => character(c)?.char || '0x' + hex(c)).join(' ')} in ${face.family} ${face.sizeLabel} ${face.style}.`);
  }

  function matches(slot) {
    const query = $('search').value.trim();
    if (!query) return true;
    const info = character(slot);
    if ([...query].length === 1) return query === info?.char;
    if (/^(?:0x)?[0-9a-f]{2}$/i.test(query) && parseInt(query.replace(/^0x/i, ''), 16) === slot) return true;
    return !!info?.name.toLowerCase().includes(query.toLowerCase());
  }

  function glyphGrid(face) {
    const grid = document.createElement('div');
    grid.className = 'grid';
    grid.style.setProperty('--cell-width', Math.max(75, face.maxWidth * Number($('scale').value) + 14) + 'px');
    for (let slot = 0; slot < 256; slot++) {
      if (!matches(slot) || ($('flagged').checked && !flags.has(key(face, slot)))) continue;
      const glyph = face.glyphs[slot];
      const info = character(slot);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'glyph' + (glyph ? '' : ' missing');
      button.dataset.key = key(face, slot);
      button.dataset.slot = String(slot);
      button.dataset.label = glyph ? (info?.char === ' ' ? 'Space' : info?.char === '\u00a0' ? 'NBSP' : info?.char || 'Native byte') : 'Missing';
      button.setAttribute('aria-pressed', String(flags.has(button.dataset.key)));
      button.setAttribute('aria-label', `0x${hex(slot)} ${info?.name || 'native glyph, identity unresolved'}${glyph ? '' : ', missing artwork'}`);
      button.title = button.getAttribute('aria-label');
      const code = document.createElement('span');
      code.className = 'code';
      code.textContent = '0x' + hex(slot);
      button.append(code);
      if (glyph) button.append(draw(glyph, face.height, face.baseline));
      else {
        const placeholder = document.createElement('span');
        placeholder.textContent = '—';
        placeholder.style.padding = (face.height * Number($('scale').value) / 3) + 'px 0';
        button.append(placeholder);
      }
      const tag = document.createElement('span');
      tag.className = 'tag';
      tag.textContent = flags.has(button.dataset.key) ? '✓ Fix' : button.dataset.label;
      button.append(tag);
      button.onclick = event => toggleGlyph(face, slot, event.shiftKey);
      grid.append(button);
    }
    return grid;
  }

  function proposal(value) {
    const text = value.trim();
    if (!text) return null;
    const match = /^(?:U\+|0x)([0-9a-f]{1,6})$/i.exec(text);
    const code = [...text].length === 1 ? text.codePointAt(0) : match ? parseInt(match[1], 16) : -1;
    if (code < 0 || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) throw Error('Use one character or a Unicode value such as U+00D1.');
    return code;
  }

  function mappingView() {
    const grid = document.createElement('div');
    grid.className = 'mapping-grid';
    const terminal = faces.find(f => f.family === 'BetaWise Terminal' && f.size === 'Medium');
    for (const slot of FONT_DATA.extraSlots) {
      if (!matches(slot)) continue;
      const entry = mappings[slot] || {};
      const info = character(slot);
      const card = document.createElement('section');
      card.className = 'mapping-card';
      card.dataset.slot = String(slot);
      card.dataset.state = entry.state || '';
      const title = document.createElement('h2');
      title.textContent = `0x${hex(slot)} · ${info ? info.char + ' · U+' + info.char.codePointAt(0).toString(16).toUpperCase().padStart(4, '0') : 'Unmapped'}`;
      card.append(title);
      const description = document.createElement('div');
      description.className = 'help';
      description.textContent = info?.name || 'Native glyph; Unicode identity remains to be identified.';
      card.append(description);
      const pictures = document.createElement('div');
      pictures.className = 'mapping-pictures';
      for (const [label, glyph, height] of [
        ['Neo system font', FONT_DATA.references[slot], FONT_DATA.references[slot]?.height],
        ['Terminal Medium', terminal.glyphs[slot], terminal.height]
      ]) {
        const holder = document.createElement('label');
        holder.append(document.createTextNode(label));
        if (glyph) holder.append(draw(glyph, height));
        pictures.append(holder);
      }
      card.append(pictures);
      const input = document.createElement('input');
      input.placeholder = 'Suggested character or U+ code';
      input.setAttribute('aria-label', 'Suggested Unicode identity for byte 0x' + hex(slot));
      input.value = entry.suggestion || '';
      input.onchange = () => {
        try {
          const code = proposal(input.value);
          remember();
          mappings[slot] = {state: 'change', suggestion: input.value, unicode: code};
          card.dataset.state = 'change';
          $('error').textContent = '';
          save();
          status('Recorded mapping proposal for 0x' + hex(slot) + '.');
        } catch (error) { $('error').textContent = error.message; }
      };
      card.append(input);
      const actions = document.createElement('div');
      actions.className = 'mapping-actions';
      for (const [state, label] of [['confirmed', info ? 'Confirm mapping' : 'Keep unmapped'], ['change', 'Needs change']]) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = label;
        button.dataset.mappingState = state;
        button.onclick = () => {
          remember();
          mappings[slot] = state === 'confirmed' ? {state} : {...(mappings[slot] || {}), state};
          if (state === 'confirmed') input.value = '';
          card.dataset.state = state;
          save();
          status(`0x${hex(slot)}: ${label.toLowerCase()}.`);
        };
        actions.append(button);
      }
      card.append(actions);
      grid.append(card);
    }
    const explanation = document.createElement('p');
    explanation.className = 'help';
    explanation.textContent = 'This glyph mapping is shared by every family. Only additions and unresolved native slots beyond printable CP1252 are shown. Firmware text-editor control roles are separate.';
    $('faces').append(explanation, grid);
  }

  function render() {
    for (const section of document.querySelectorAll('details[data-face]')) {
      if (section.open) openFaces.add(section.dataset.face);
      else openFaces.delete(section.dataset.face);
    }
    $('faces').replaceChildren();
    const mappingMode = $('mode').value === 'mapping';
    for (const id of ['family', 'size', 'style', 'accents', 'flagged', 'baseline', 'all']) $(id).disabled = mappingMode;
    if (mappingMode) {
      mappingView();
      status('Only Neo-specific additions and unresolved native slots are shown; ordinary printable CP1252 positions are omitted.');
      return;
    }
    const visible = faces.filter(face =>
      ($('family').value === 'all' || face.family === $('family').value) &&
      ($('size').value === 'all' || face.size === $('size').value) &&
      ($('style').value === 'all' || face.style === $('style').value) &&
      (!$('flagged').checked || [...flags].some(k => k.startsWith(face.id + '#'))));
    for (const [index, face] of visible.entries()) {
      const section = document.createElement('details');
      section.dataset.face = face.id;
      const summary = document.createElement('summary');
      summary.textContent = `${face.family} ${face.sizeLabel} · ${face.style} · ${face.lines} lines · ${face.height}px cell`;
      const count = document.createElement('small');
      count.className = 'count';
      summary.append(count);
      section.append(summary);
      let drawn = false;
      function populate() {
        if (section.open && !drawn) { section.append(glyphGrid(face)); drawn = true; }
      }
      section.ontoggle = populate;
      section.open = visible.length === 1 || openFaces.has(face.id) || (index === 0 && !openFaces.size);
      $('faces').append(section);
      populate();
    }
    if (!visible.length) $('faces').textContent = 'No flagged glyphs match these filters.';
    refreshMarks();
  }

  function exportSelections() {
    const glyphs = [...flags].sort().map(value => {
      const split = value.lastIndexOf('#');
      const face = byId.get(value.slice(0, split));
      const slot = parseInt(value.slice(split + 1), 16);
      return {font: face.id, slot, hex: '0x' + hex(slot), character: character(slot)?.char || null,
              family: face.family, size: face.sizeLabel, style: face.style, implemented: !!face.glyphs[slot]};
    });
    const mapping = Object.entries(mappings).map(([slot, value]) => ({slot: +slot, hex: '0x' + hex(+slot), currentUnicode: character(+slot)?.char.codePointAt(0) ?? null, currentCharacter: character(+slot)?.char || null, ...value}));
    return {format: 'betawise-font-fixes-v1', glyphs, mapping};
  }
  function importSelections(document) {
    if (document.format !== 'betawise-font-fixes-v1' || !Array.isArray(document.glyphs)) throw Error('Not a BetaWise font-fixes export.');
    const next = new Set();
    for (const entry of document.glyphs) {
      if (!byId.has(entry.font) || !Number.isInteger(entry.slot) || entry.slot < 0 || entry.slot > 255) throw Error('Export refers to an unknown font or slot.');
      next.add(entry.font + '#' + hex(entry.slot));
    }
    const nextMappings = {};
    for (const entry of document.mapping || []) {
      if (!FONT_DATA.extraSlots.includes(entry.slot) || !['confirmed', 'change'].includes(entry.state)) throw Error('Invalid mapping review entry.');
      if (entry.unicode !== undefined && entry.unicode !== null &&
          (!Number.isInteger(entry.unicode) || entry.unicode < 0 || entry.unicode > 0x10ffff || (entry.unicode >= 0xd800 && entry.unicode <= 0xdfff))) throw Error('Invalid Unicode proposal.');
      nextMappings[entry.slot] = {state: entry.state, suggestion: entry.suggestion || '', unicode: entry.unicode ?? null};
    }
    remember();
    flags = next;
    mappings = nextMappings;
    save();
    render();
    status('Imported glyph flags and mapping review.');
  }

  $('family').onchange = () => { updateFilters(); render(); };
  for (const id of ['mode', 'size', 'style', 'scale', 'flagged', 'baseline']) $(id).onchange = render;
  $('search').oninput = render;
  $('all').onclick = () => {
    $('family').value = 'all'; updateFilters(); $('size').value = 'all'; $('style').value = 'all'; render();
  };
  $('undo').onclick = () => {
    const previous = history.pop();
    if (!previous) return;
    flags = new Set(previous.flags); mappings = previous.mappings; save(); render(); status('Undid the last selection change.');
  };
  $('vector-review').onclick = () => { location.href = 'vector-review.html'; };
  $('clear').onclick = () => {
    if (!confirm('Clear all glyph flags and mapping reviews?')) return;
    remember(); flags.clear(); mappings = {}; save(); render(); status('Cleared all flags and mapping reviews.');
  };
  $('export').onclick = () => {
    const blob = new Blob([JSON.stringify(exportSelections(), null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'betawise-font-fixes.json'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  $('import').onchange = async event => {
    try {
      if (!event.target.files.length) return;
      importSelections(JSON.parse(await event.target.files[0].text()));
      $('error').textContent = '';
    } catch (error) { $('error').textContent = 'Import failed: ' + error.message; }
    event.target.value = '';
  };
  globalThis.BetaWiseReview = Object.freeze({exportSelections, importSelections});
  if (location.hash === '#mapping') $('mode').value = 'mapping';
  window.addEventListener('hashchange', () => {
    $('mode').value = location.hash === '#mapping' ? 'mapping' : 'glyphs';
    render();
  });
  render();
})();
