"""Bounded object-order evaluation from one resolved discovery ELF.

This is an approximate placement model, not a replacement for GNU ld. Actual
ranges, selected symbol providers and relocation-table size must be checked.
"""
import bisect
import json
import re
from elf_reader import Image, GOT_OFFSETS
import time
from pathlib import Path
import object_order


def read_model(elf, records):
    image = Image(elf)
    names = image.sections
    sites = {s['label']: s for record, _, _ in records for s in record['sites']}
    values = image.values
    addresses = {s.name: s.value for s in image.symbols if s.name in sites}
    sources = {s.name: s.section for s in image.symbols if s.name in sites}
    places = {a+2: key for key, a in addresses.items()}
    targets, sections, slots = {}, {}, {}
    for rel in image.relocations:
        if rel.kind not in GOT_OFFSETS: continue
        slots.setdefault((rel.symbol.key, rel.addend), []).append(places.get(rel.offset))
        if rel.offset in places:
            label = places[rel.offset]
            targets[label] = rel.target & 0xffffffff
            sections[label] = rel.symbol.section
    ram, rom = set(), set()
    for label, target in targets.items():
        s = sites[label]
        if names.get(sections[label]) in {'.ram','.rom.ram','.data','.bss','.got'}:
            if s.get('kind') == 'address' and 0 <= target-0x80000000 <= 32767: ram.add(label)
        elif sections[label] == sources[label] and str(sections[label]).isdigit(): rom.add(label)
    deltas = {key: -2 if sites[key].get('kind','call') == 'call' else
              0 if re.fullmatch(r'%(?:a[0-7]|sp)',sites[key]['register'].strip()) else 2
              for key in addresses}
    return dict(sites=sites, addresses=addresses, targets=targets, ram=ram,
                rom=rom, deltas=deltas, slots=slots, values=values)


def evaluate(model, state, order, margin=128, rom_addresses=True):
    groups = [g for g in state['groups'] if g['size']]
    by_id = {g['id']:g for g in groups}
    bulk = [g['id'] for g in groups if g['bulk']]
    order = [k for k in order if k in by_id and k not in bulk]
    order += [g['id'] for g in groups if g['id'] not in order and not g['bulk']]
    order += bulk
    intervals = sorted((g['start'],g['end'],g['id']) for g in groups)
    starts = [g[0] for g in intervals]
    def owner(address):
        i = bisect.bisect_right(starts,address)-1
        return intervals[i][2] if i>=0 and address<intervals[i][1] else None
    lo,hi = min(starts),max(g[1] for g in intervals)
    events = {k:[] for k in by_id}
    for label, address in model['addresses'].items():
        key=owner(address)
        if key:events[key].append((address,label))
    for key in events:events[key].sort()
    positions={k:[a for a,_ in events[k]] for k in events}
    rom={k for k in model['rom'] if rom_addresses or model['sites'][k].get('kind','call')=='call'}
    enabled=model['ram']|rom
    rounds=0
    while True:
        rounds+=1;prefix={};bases={};cursor=lo
        for key in order:
            p=[0]
            for _,label in events[key]:p.append(p[-1]+(model['deltas'][label] if label in enabled else 0))
            prefix[key]=p;bases[key]=cursor;cursor+=by_id[key]['size']+p[-1]
        def moved(address):
            key=owner(address)
            if key:return bases[key]+address-by_id[key]['start']+prefix[key][bisect.bisect_left(positions[key],address)]
            if address>=hi:return address+cursor-hi
            return address
        bad={k for k in enabled&rom if not -32768+margin <= moved(model['targets'][k])-moved(model['addresses'][k])-2 <=32767-margin}
        if not bad:break
        enabled-=bad
        if rounds>len(rom)+1:raise RuntimeError('Nonmonotonic order evaluation')
    slots=sum(any(label is None or label not in enabled for label in users) for users in model['slots'].values())
    oldgot=model['values']['__os3k_got_size']
    # Account for GOT entries without a visible GOT relocation. Do not assume
    # a smaller count if the discovery ELF does not support our slot model.
    residual=max(0,oldgot//4-3-len(model['slots'])) if oldgot else 0
    got=4*(3+slots+residual) if slots+residual else 0
    ram=model['values']['__os3k_ram_size']-oldgot+got
    rom_size=model['values']['__os3k_rom_size']-oldgot+got+cursor-hi
    return dict(order=order,disabled=set(model['sites'])-enabled,rom_labels=enabled&rom,
                sizes={'ram':ram,'rom':rom_size,'got':got},iterations=rounds,
                direct=len(enabled))


def choose(elf, records, state, seed=None, margin=128, rom_addresses=True):
    start=time.perf_counter()
    if not any(group['size'] for group in state['groups']):
        import fast_layout
        disabled, rom, report = fast_layout.predict(elf, records, margin, rom_addresses)
        report.update(selected_order='fixed-entry', internal_order_candidates=[])
        return disabled, rom, state['order'], report
    model=read_model(elf,records)
    candidates=[('discovery',state['order']),('input',[])]
    if seed is not None:candidates.append(('saved-seed',seed))
    candidates+=object_order.candidate_orders(state)
    evaluated=[];seen=set()
    for name,order in candidates:
        r=evaluate(model,state,order,margin,rom_addresses)
        signature=tuple(r['order'])
        if signature in seen:continue
        seen.add(signature);r['name']=name;evaluated.append(r)
    winner=min(enumerate(evaluated),key=lambda p:(p[1]['sizes']['ram'],p[1]['sizes']['rom'],p[0]))[1]
    report={'internal_order_candidates':[{'name':r['name'],'order':r['order'],'sizes':r['sizes'],'iterations':r['iterations']} for r in evaluated],
            'selected_order':winner['name'],'prediction_seconds':time.perf_counter()-start,
            'predicted_sizes':winner['sizes'],'internal_iterations':winner['iterations'],
            'margin':margin,'predicted_direct':winner['direct'],'live_sites':len(model['addresses'])}
    return winner['disabled'],winner['rom_labels'],winner['order'],report
