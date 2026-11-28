"""Experimental layout predictor. A checked final link remains authoritative.

The discovery link resolves archives/GC and classifies address spaces. Python
models +/-2-byte site changes and iterates fallback decisions without tools.
A margin covers small unmodelled assembler/alignment changes; failed predictions
are never shipped and return control to the established iterative adapter.
"""
import bisect
import re
from elf_reader import Image, R_68K_GOT16O
import time
import flag_cleanup


def predict(elf, records, margin=128, rom_addresses=True):
    started = time.perf_counter()
    image = Image(elf)
    section_names = image.sections
    sites = {s['label']: s for record, _, _ in records for s in record['sites']}
    addresses = {s.name: s.value for s in image.symbols if s.name in sites}
    source_sections = {s.name: s.section for s in image.symbols if s.name in sites}
    places = {value + 2: label for label, value in addresses.items()}
    targets, target_sections = {}, {}
    for rel in image.relocations:
        if rel.kind == R_68K_GOT16O and rel.offset in places:
            label = places[rel.offset]
            target_sections[label] = rel.symbol.section
            targets[label] = rel.target & 0xffffffff
    ram_names = {'.ram', '.rom.ram', '.data', '.bss', '.got'}
    ram, rom = set(), set()
    for label, target in targets.items():
        site = sites[label]
        if section_names.get(target_sections[label]) in ram_names and site.get('kind') == 'address':
            # Code rewriting only shrinks the GOT, not ordinary RAM sections.
            # Keep out-of-range discovery addresses on the established path.
            if 0 <= target - 0x80000000 <= 32767: ram.add(label)
        elif target_sections[label] == source_sections[label] and str(target_sections[label]).isdigit():
            if site.get('kind', 'call') == 'call' or rom_addresses: rom.add(label)
    enabled = ram | rom
    ordered = sorted(addresses, key=addresses.get)
    positions = [addresses[label] for label in ordered]
    removable = set().union(*(flag_cleanup.removable_sites(record) for record, _, _ in records))
    deltas = {label: flag_cleanup.site_delta(sites[label], removable) for label in ordered}
    rounds = 0
    while True:
        rounds += 1
        prefix = [0]
        for label in ordered:
            prefix.append(prefix[-1] + (deltas[label] if label in enabled else 0))
        def moved(address):
            return address + prefix[bisect.bisect_left(positions, address)]
        bad = {label for label in enabled & rom
               if not -32768 + margin <= moved(targets[label]) - moved(addresses[label]) - 2 <= 32767 - margin}
        if not bad: break
        enabled -= bad
        if rounds > len(rom) + 1: raise RuntimeError('Nonmonotonic prediction')
    return set(sites) - enabled, rom & enabled, {
        'internal_iterations': rounds, 'margin': margin, 'live_sites': len(addresses),
        'predicted_direct': len(enabled), 'predicted_ram_direct': len(ram),
        'prediction_seconds': time.perf_counter() - started,
    }
