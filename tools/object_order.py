"""Section-placement helpers. Linker input and archive order stay unchanged."""
from pathlib import Path
from elf_reader import Image, R_68K_PC16, R_68K_GOT16O


def generate_script(groups, specification, template, output):
    requested = specification.get('order', [])
    by_id = {group['id']: group for group in groups}
    if len(requested) != len(set(requested)) or any(key not in by_id for key in requested):
        raise ValueError('Object-order specification contains duplicate or unknown groups')
    bulk = [group['id'] for group in groups if group['bulk']]
    order = [key for key in requested if key not in bulk]
    order.extend(group['id'] for group in groups if group['id'] not in order and not group['bulk'])
    order.extend(bulk)
    lines = []
    for key in order:
        group = by_id[key]
        selector = group['selector']
        lines.extend([
            '        HIDDEN(__bw_group_' + key + '_start = .);',
            '        ' + selector + '(.text .text.* .rodata .rodata.*)',
            '        HIDDEN(__bw_group_' + key + '_end = .);',
        ])
    start = template.index('        /* Keep C code')
    end = template.index('        . = ALIGN(2);', start)
    output.write_text(template[:start] + '\n'.join(lines) + '\n' + template[end:])
    return order


def read_symbols(image):
    return Image(image).values


def resolution_providers(map_file, groups):
    """The first file in each --cref row is the defining input."""
    files = {group['provider']: group['id'] for group in groups}
    text = map_file.read_text()
    if 'Cross Reference Table' not in text:
        raise ValueError('Linker cross-reference table is missing')
    text = text.split('Cross Reference Table', 1)[1]
    providers = {}
    pending = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('Symbol '):
            continue
        if line[0].isspace():
            if pending:
                filename = line.strip()
                if filename in files:
                    providers[pending] = files[filename]
                pending = None
            continue
        fields = line.split()
        name = fields[0]
        if name.startswith('__bw_group_'):
            continue
        if len(fields) == 1:
            pending = name
        elif fields[1] in files:
            providers[name] = files[fields[1]]
    return providers


def validate_code_alignment(image, values):
    for symbol in Image(image).symbols:
        if symbol.kind == 'STT_FUNC' and isinstance(symbol.section, int) and symbol.value & 1:
            raise ValueError('Odd function entry: ' + symbol.name)
    # SDK A-line stubs are NOTYPE; check their defined names as well.
    syscall = Path(__file__).resolve().parents[1] / 'os3k/build/syscall.o'
    if syscall.exists():
        for name in Image(syscall).values:
            if name in values and values[name] & 1:
                raise ValueError('Odd syscall entry: ' + name)


def describe(image, map_file, groups, records, order):
    image = Image(image)
    values = read_symbols(image)
    validate_code_alignment(image, values)
    intervals = []
    described = []
    for group in groups:
        start = values.get('__bw_group_' + group['id'] + '_start', 0)
        end = values.get('__bw_group_' + group['id'] + '_end', 0)
        described.append({**group, 'start': start, 'end': end, 'size': end - start})
        if end > start:
            intervals.append((start, end, group['id']))
    labels = {site['label'] for record, _, _ in records for site in record['sites']}
    sites = {value + 2 for name, value in values.items() if name in labels}

    def owner(address):
        return next((key for start, end, key in intervals if start <= address < end), None)

    edges = {}
    for rel in Image(image).relocations:
        if rel.kind not in {R_68K_PC16, R_68K_GOT16O} or rel.offset not in sites:
            continue
        place, target = rel.offset, rel.target
        source_group, target_group = owner(place), owner(target)
        if not source_group or not target_group or source_group == target_group:
            continue
        pair = tuple(sorted((source_group, target_group)))
        # Emphasize references currently using GOT, while retaining already-short edges.
        edges[pair] = edges.get(pair, 0) + (3 if rel.kind == R_68K_GOT16O else 1)
    return {
        'groups': described, 'order': order,
        'edges': [{'a': a, 'b': b, 'weight': weight} for (a, b), weight in sorted(edges.items())],
        'providers': resolution_providers(map_file, groups),
    }


def candidate_orders(state):
    """At most three alternatives to the input-order probe."""
    groups = [group for group in state['groups'] if group['size'] and not group['bulk']]
    keys = [group['id'] for group in groups]
    rank = {key: index for index, key in enumerate(keys)}
    size = {group['id']: group['size'] for group in groups}
    edges = {}
    for edge in state['edges']:
        edges[edge['a'], edge['b']] = edge['weight']
        edges[edge['b'], edge['a']] = edge['weight']
    degree = {key: sum(edges.get((key, other), 0) for other in keys) for key in keys}
    if not keys:
        return []

    def strongest(remaining, placed):
        return min(remaining, key=lambda key: (
            -sum(edges.get((key, other), 0) for other in placed), -degree[key], rank[key]))

    seed = min(keys, key=lambda key: (-degree[key], rank[key]))
    walk = [seed]
    remaining = set(keys) - {seed}
    while remaining:
        key = strongest(remaining, [walk[-1]])
        walk.append(key)
        remaining.remove(key)

    centered = [seed]
    remaining = set(keys) - {seed}
    while remaining:
        key = strongest(remaining, centered)
        centers = {}
        offset = 0
        for other in centered:
            centers[other] = offset + size[other] / 2
            offset += size[other]
        front = sum(edges.get((key, other), 0) * (centers[other] + size[key] / 2)
                    for other in centered)
        back = sum(edges.get((key, other), 0) * (offset + size[key] / 2 - centers[other])
                   for other in centered)
        if front < back:
            centered.insert(0, key)
        else:
            centered.append(key)
        remaining.remove(key)
    return [('reverse', list(reversed(keys))), ('graph-walk', walk), ('graph-center', centered)]
