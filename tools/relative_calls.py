#!/usr/bin/env python3
"""Experimental compiler/linker adapters for GOT calls and RAM addresses."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import importlib.util
import struct
from elf_reader import Image, R_68K_16, R_68K_PC16, R_68K_GOT16O
import flag_cleanup
import a5_cleanup
import asm_liveness

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / '.relative-calls'
ADDRESS_PATTERN = re.compile(r'\tmove\.l ([\w.$]+)@GOT\(%a5\),([^\n]+)(?=\n)')
PATTERN = re.compile(r'\tmove\.l ([\w.$]+)@GOT\(%a5\),(%a[01])\n\tjsr \(\2\)')
PREFIX = os.environ.get('CROSS_COMPILE', 'm68k-linux-gnu-')
CC = PREFIX + 'gcc'
LD = PREFIX + 'ld'
AR = PREFIX + 'ar'
ASSEMBLER_ID = None


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], **kwargs)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def render(record, disabled, rom_labels=()):
    text = record['assembly']
    removable = flag_cleanup.removable_sites(record) if any(
        s.get('kind') == 'address' and s['register'].strip() == '-(%sp)'
        and s['label'] not in disabled for s in record['sites']) else frozenset()
    for site in record['sites']:
        if site['label'] in disabled:
            replacement = site['original']
        elif site.get('kind', 'call') == 'call':
            replacement = '\tbsr.w ' + site['target']
        else:
            destination = site['register'].strip()
            rom = site['label'] in rom_labels
            base = '%pc' if rom else '%a5'
            relocation = 'R_68K_PC16' if rom else 'R_68K_16'
            target = site['target'] if rom else site['target'] + '-0x80000000'
            address_register = re.fullmatch(r'%(?:a[0-7]|sp)', destination)
            if address_register:
                instruction = '\tlea (0:w,' + base + '),' + destination
                finish = ''
            else:
                instruction = '\tpea (0:w,' + base + ')'
                # MOVE evaluates its source postincrement before its destination
                # EA, restoring SP before stack-relative destinations are formed.
                # The final MOVE also reproduces NZVC while preserving X.
                if destination == '-(%sp)':
                    finish = '' if site['label'] in removable else '\n\ttst.l (%sp)'
                else:
                    finish = '\n\tmove.l (%sp)+,' + destination
            replacement = (instruction + '\n\t.reloc .-2,' + relocation + ',' + target + finish)
        text = text.replace(site['token'], '.globl ' + site['label'] + '\n.hidden ' +
                            site['label'] + '\n' + site['label'] + ':\n' + replacement)
    if a5_cleanup.enabled() and 'input_sha256' in record:
        text = a5_cleanup.transform(text, record['object'])
    return asm_liveness.transform(record, text, disabled)


def compile_record(record, output, disabled, rom_labels=()):
    asm = Path(str(output) + '.s')
    text = render(record, disabled, rom_labels)
    asm.write_text(text)
    cache = os.environ.get('ORDER_ASM_CACHE')
    cache_file = None
    if cache:
        global ASSEMBLER_ID
        if ASSEMBLER_ID is None:
            ASSEMBLER_ID = subprocess.check_output([CC, '--version'], text=True)
        key = digest((ASSEMBLER_ID + str(Path.cwd()) + record.get('input_sha256', '') + text).encode())
        cache_file = Path(cache) / (key + '.o')
        if cache_file.exists():
            output.write_bytes(cache_file.read_bytes())
            return subprocess.CompletedProcess([], 0, '', '')
    result = run([CC, '-m68000', '-c', asm, '-o', output], capture_output=True, text=True)
    if cache_file and result.returncode == 0:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_file.with_suffix('.' + str(os.getpid()) + '.tmp')
        temporary.write_bytes(output.read_bytes())
        temporary.replace(cache_file)
    return result


def make_record(assembly, output):
    record = {'assembly': assembly, 'sites': [], 'object': str(output.resolve())}
    prefix = digest(str(output.resolve()).encode())[:16]
    def replace(match, kind):
        index = len(record['sites'])
        token = '__BW_TOKEN_' + str(index) + '__'
        record['sites'].append(dict(token=token, label='__bw_call_' + prefix + '_' + str(index),
                                    kind=kind, register=match[2],
                                    target=match[1], original=match[0]))
        return token
    record['assembly'] = PATTERN.sub(lambda m: replace(m, 'call'), record['assembly'])
    record['assembly'] = ADDRESS_PATTERN.sub(lambda m: replace(m, 'address'), record['assembly'])
    return record


def compiler(args):
    sources = [a for a in args if a.endswith('.c')]
    if '-c' not in args or '-o' not in args or len(sources) != 1 or '-msep-data' not in args:
        return run([CC, *args]).returncode
    output = Path(args[args.index('-o') + 1])
    asm = Path(str(output) + '.original.s')
    command = args.copy()
    command[command.index('-c')] = '-S'
    command[command.index('-o') + 1] = str(asm)
    result = run([CC, *command])
    if result.returncode:
        return result.returncode
    allowed = ['%'+name for name in ['a0', 'a1']
               if '-ffixed-'+name not in args and '-fcall-saved-'+name not in args]
    # Registry keys are object hashes. Keep availability in the nonloaded
    # comment section so identical code with different register restrictions
    # cannot overwrite each other's metadata. This adds no packaged bytes.
    source = asm.read_text() + '\n.ident "OS3K scratch registers: ' + ','.join(allowed) + '"\n'
    record = make_record(source, output)
    record['asm_allowed'] = allowed
    if not record['sites']:
        return run([CC, *args]).returncode
    # Compile with original GOT references. Each final link gets its own optimized
    # objects, so different applets sharing an archive can make different choices.
    disabled = {s['label'] for s in record['sites']}
    result = compile_record(record, output, disabled)
    if result.returncode:
        sys.stderr.write(result.stderr)
        return result.returncode
    REGISTRY.mkdir(exist_ok=True)
    path = REGISTRY / (digest(output.read_bytes()) + '.json')
    path.write_text(json.dumps(record))
    return 0


def overflow_sites(elf, labels, eligible_data=None, eligible_rom=None):
    image = Image(elf)
    sections = {s.name: s.section for s in image.symbols}
    addresses = {s.value + 2: s.name for s in image.symbols if s.name in labels}
    bad = set()
    for rel in image.relocations:
        place = rel.offset
        if rel.kind not in {R_68K_16, R_68K_PC16, R_68K_GOT16O} or place not in addresses:
            continue
        value = rel.target
        target_section = rel.symbol.section
        ram_target = image.sections.get(target_section) in {'.ram', '.rom.ram', '.data', '.bss', '.got'}
        source_section = sections.get(addresses[place])
        if rel.kind == R_68K_GOT16O:
            if eligible_data is not None and ram_target:
                eligible_data.add(addresses[place])
            if (eligible_rom is not None and isinstance(source_section, int)
                    and source_section == target_section):
                eligible_rom.add(addresses[place])
        elif rel.kind == R_68K_16:
            if not ram_target or not -32768 <= value <= 32767:
                bad.add(addresses[place])
        elif (not isinstance(source_section, int) or source_section != target_section
              or not -32768 <= value - place <= 32767):
            bad.add(addresses[place])
    return bad


def linker(args):
    if '-o' not in args or not any(a.endswith('.o') or a.endswith('.a') for a in args):
        return run([LD, *args]).returncode
    records = []
    groups = []
    internal_requested = os.environ.get('OS3K_INTERNAL_ORDERS') == '1'
    script_path = Path(args[args.index('-T')+1]).resolve() if '-T' in args else None
    supported_scripts = {(ROOT/'os3k/os3k.lds').resolve(), (ROOT/'os3k/os3k-grouped.lds').resolve()}
    # Automatic placement must not replace an application's custom script.
    internal_orders = internal_requested and script_path in supported_scripts
    ordering = os.environ.get('OBJECT_ORDER') or ('input' if internal_orders else None)
    with tempfile.TemporaryDirectory(prefix='bw-relative-') as temporary:
        work = Path(temporary)
        command = args.copy()
        for index, name in enumerate(args):
            if not name.endswith(('.o', '.a')) or not Path(name).is_file():
                continue
            source = Path(name)
            target = work / (str(index) + '-' + source.name)
            if source.suffix == '.o':
                data = source.read_bytes()
                target.write_bytes(data)
                key = REGISTRY / (digest(data) + '.json')
                if key.exists():
                    record = json.loads(key.read_text())
                    record['input_sha256'] = key.stem
                    records.append((record, target, None))
                command[index] = str(target)
                groups.append({'id': 'g' + str(index), 'origin': name,
                               'selector': '*/' + target.name, 'provider': str(target),
                               'sha256': digest(data), 'bulk': source.name == 'Resources.o'})
            else:
                members = subprocess.check_output([AR, 't', str(source)], text=True).splitlines()
                archive_dir = work / str(index)
                archive_dir.mkdir()
                archive = target
                for ordinal, member in enumerate(members):
                    if not re.fullmatch(r'[\w.+-]+', member):
                        raise ValueError('Unsupported archive member name: ' + member)
                    data = subprocess.check_output([AR, 'p', str(source), member])
                    member_file = archive_dir / member
                    member_file.write_bytes(data)
                    key = REGISTRY / (digest(data) + '.json')
                    if key.exists():
                        record = json.loads(key.read_text())
                        record['input_sha256'] = key.stem
                        records.append((record, member_file, archive))
                    groups.append({'id': 'g' + str(index) + 'm' + str(ordinal),
                                   'origin': name + '(' + member + ')',
                                   'selector': '*/' + archive.name + ':' + member,
                                   'provider': str(archive) + '(' + member + ')',
                                   'sha256': digest(data), 'bulk': member == 'Resources.o'})
                command[index] = str(archive)
                run([AR, 'rcs', archive, *[archive_dir / m for m in members]], check=True)
        order = []
        if ordering:
            import object_order
            specification = {} if ordering == 'input' else json.loads(Path(ordering).read_text())
            script = work / 'ordered.lds'
            order = object_order.generate_script(groups, specification,
                        (ROOT / 'os3k/os3k-grouped.lds').read_text(), script)
            command[command.index('-T') + 1] = str(script)
        if not records:
            return run([LD, *args]).returncode
        if a5_cleanup.enabled():
            # Discovery and final link must see identical frame changes and
            # zero-byte provenance labels; original input objects stay usable.
            archives = set()
            for record, target, archive in records:
                assembled = compile_record(record, target, {s['label'] for s in record['sites']})
                if assembled.returncode:
                    sys.stderr.write(assembled.stderr)
                    return assembled.returncode
                if archive:
                    archives.add(archive)
            for archive in archives:
                members = [target for _, target, owner in records if owner == archive]
                run([AR, 'r', archive, *members], check=True, stdout=subprocess.DEVNULL)
        labels = {s['label'] for record, _, _ in records for s in record['sites']}
        data_labels = {s['label'] for record, _, _ in records for s in record['sites']
                       if s.get('kind') == 'address'}
        fast_attempt = None
        if os.environ.get('OS3K_LAYOUT_SOLVER') == '1' or internal_orders:
            import fast_layout
            started = time.perf_counter()
            output = Path(args[args.index('-o') + 1])
            discovery = output.with_name(output.name + '.discovery')
            discovery_command = command.copy()
            discovery_command[discovery_command.index('-o') + 1] = str(discovery)
            discovery_map = Path(str(discovery)+'.map')
            import object_order
            found = run([LD, *discovery_command, '--cref', '-Map', discovery_map], capture_output=True, text=True)
            fast_attempt = {'link_calls': 1, 'accepted': False}
            if found.returncode == 0:
                discovery_metadata = Image(discovery)
                discovery_providers = object_order.resolution_providers(discovery_map, groups)
                discovery_providers.pop('_GLOBAL_OFFSET_TABLE_', None)
                if internal_orders:
                    import order_solver
                    discovery_state = object_order.describe(discovery_metadata, discovery_map, groups, records, order)
                    seed_file = os.environ.get('OS3K_ORDER_SEED')
                    seed = json.loads(Path(seed_file).read_text())['order'] if seed_file else None
                    predicted_disabled, predicted_rom, order, prediction = order_solver.choose(
                        discovery_metadata, records, discovery_state, seed,
                        int(os.environ.get('OS3K_LAYOUT_MARGIN') or '128'),
                        os.environ.get('ROM_REFERENCES', '1') == '1')
                    script = work/'selected-order.lds'
                    order = object_order.generate_script(groups, {'order': order},
                        (ROOT/'os3k/os3k-grouped.lds').read_text(), script)
                    command[command.index('-T')+1] = str(script)
                else:
                    predicted_disabled, predicted_rom, prediction = fast_layout.predict(
                        discovery_metadata, records,
                        int(os.environ.get('OS3K_LAYOUT_MARGIN') or '128'),
                        os.environ.get('ROM_REFERENCES', '1') == '1')
                original_reloc_definition = None
                relocation_count = None
                if os.environ.get('OS3K_SINGLE_STAGE') == '1':
                    relocation_count = len(fixup_module().fixups(discovery_metadata))
                    index = next(i for i,a in enumerate(command) if a.startswith('__os3k_reloc_size='))
                    original_reloc_definition = (index, command[index])
                    command[index] = '__os3k_reloc_size='+str(relocation_count)
                    prediction['predicted_relocation_count'] = relocation_count
                    previous_count = int(original_reloc_definition[1].split('=',1)[1],0)
                    table_growth = 4*(relocation_count-previous_count)
                    if 'predicted_sizes' in prediction:
                        prediction['predicted_sizes'] = dict(prediction['predicted_sizes'])
                        prediction['predicted_sizes']['rom'] += table_growth
                        for candidate in prediction['internal_order_candidates']:
                            candidate['sizes']['rom'] += table_growth
                fast_attempt.update(prediction)
                good = True
                archives = set()
                for record, target, archive in records:
                    assembled = compile_record(record, target, predicted_disabled, predicted_rom)
                    if assembled.returncode:
                        good = False
                        fast_attempt['rejected'] = 'assembly'
                        break
                    if archive: archives.add(archive)
                if good:
                    for archive in archives:
                        members = [target for _, target, owner in records if owner == archive]
                        run([AR, 'r', archive, *members], check=True, stdout=subprocess.DEVNULL)
                    map_file = Path(str(output) + '.map')
                    final = run([LD, *command, '--cref', '-Map', map_file],
                                capture_output=True, text=True)
                    fast_attempt['link_calls'] += 1
                    final_bad = overflow_sites(output, labels) if final.returncode == 0 else set()
                    final_providers = (object_order.resolution_providers(map_file, groups)
                                       if final.returncode == 0 else {})
                    final_providers.pop('_GLOBAL_OFFSET_TABLE_', None)
                    providers_match = final.returncode == 0 and final_providers == discovery_providers
                    fast_attempt['symbol_providers_preserved'] = providers_match
                    relocations_match = True
                    if final.returncode == 0 and relocation_count is not None:
                        try:
                            actual_count = len(fixup_module().fixups(output))
                            relocations_match = actual_count == relocation_count
                            fast_attempt['final_relocation_count'] = actual_count
                        except (ValueError, KeyError) as error:
                            relocations_match = False
                            fast_attempt['relocation_error'] = str(error)
                    if final.returncode == 0 and not final_bad and providers_match and relocations_match:
                        import object_order
                        state = object_order.describe(output, map_file, groups, records, order)
                        # Resolution is preserved by retaining command/archive order.
                        # The final checked link and displacement check are mandatory.
                        fast_attempt['accepted'] = True
                        fast_attempt['total_seconds'] = time.perf_counter() - started
                        report = {'candidates': len(labels),
                                  'fallback': len(predicted_disabled),
                                  'direct': len(labels - predicted_disabled),
                                  'relaxation_passes': 1, 'total_link_passes': 2,
                                  'safety_fallback': False,
                                  'rom_references': os.environ.get('ROM_REFERENCES', '1'),
                                  'pass_history': [{'pass': 1, 'phase': 'discovery'},
                                                   {'pass': 2, 'phase': 'checked-final'}],
                                  'fast_layout': fast_attempt, 'invocation': args,
                                  'cwd': str(Path.cwd()), 'object_order': ordering or 'incumbent'}
                        report['tst_cleanup'] = cleanup_stats(records, predicted_disabled, output)
                        Path(str(output)+'.order.json').write_text(json.dumps(state)+'\n')
                        Path(str(output)+'.calls.json').write_text(json.dumps(report)+'\n')
                        with Path(str(output)+'.passes.jsonl').open('a') as log:
                            log.write(json.dumps(report)+'\n')
                        discovery.unlink(missing_ok=True)
                        sys.stderr.write(final.stderr)
                        return 0
                    fast_attempt['rejected'] = 'final-link-or-displacement'
                    fast_attempt['bad_sites'] = sorted(final_bad)[:20]
                    if final.returncode == 0:
                        shutil.copy2(output, str(output)+'.fast-rejected')
                        shutil.copy2(discovery, str(output)+'.fast-discovery')
                    fast_attempt['diagnostic'] = final.stderr[-3000:]
                    fast_attempt['final_returncode'] = final.returncode
            else:
                fast_attempt['rejected'] = 'discovery-link'
            if found.returncode == 0 and original_reloc_definition is not None:
                command[original_reloc_definition[0]] = original_reloc_definition[1]
            discovery.unlink(missing_ok=True)
        disabled = set(data_labels)
        classified_data = False
        rom_labels = set()
        history = []
        safety_fallback = False
        max_passes = max(1, int(os.environ.get('MAX_RELAX_PASSES', '8')))
        output = Path(args[args.index('-o') + 1])
        while True:
            if len(history) >= max_passes:
                disabled = set(labels)
                safety_fallback = True
            archives = set()
            for record, target, archive in records:
                result = compile_record(record, target, disabled, rom_labels)
                if result.returncode:
                    # An assembler-resolved same-section call may overflow before ld.
                    local = {s['label'] for s in record['sites']}
                    if local <= disabled:
                        sys.stderr.write(result.stderr)
                        return result.returncode
                    disabled.update(local)
                    result = compile_record(record, target, disabled, rom_labels)
                    if result.returncode:
                        sys.stderr.write(result.stderr)
                        return result.returncode
                if archive:
                    archives.add(archive)
            for archive in archives:
                objects = [target for _, target, a in records if a == archive]
                run([AR, 'r', archive, *objects], check=True, stdout=subprocess.DEVNULL)
            result = run([LD, *command, '--noinhibit-exec'], capture_output=True, text=True)
            history.append({'pass': len(history) + 1, 'disabled_candidates': len(disabled),
                            'phase': 'classification' if not classified_data else 'range-check'})
            if not output.exists():
                sys.stderr.write(result.stderr)
                return result.returncode or 1
            if not classified_data:
                eligible = set()
                eligible_rom = set()
                overflow_sites(output, labels, eligible, eligible_rom)
                if os.environ.get('ROM_REFERENCES', '1') == '1':
                    rom_labels = eligible_rom & data_labels
                enabled = (eligible & data_labels) | rom_labels
                if not safety_fallback:
                    disabled -= enabled
                classified_data = True
                history[-1]['ram_candidates'] = len(eligible & data_labels)
                history[-1]['rom_candidates'] = len(rom_labels)
                if enabled and not safety_fallback:
                    continue
            bad = overflow_sites(output, labels) - disabled
            if not bad and result.returncode == 0 and 'relocation truncated to fit' not in result.stderr:
                sys.stderr.write(result.stderr)
                break
            if not bad:
                sys.stderr.write(result.stderr)
                return result.returncode or 1
            history[-1]['new_range_fallbacks'] = len(bad)
            disabled.update(bad)
        # Re-link normally, so unrelated failures always fail the build.
        map_file = Path(str(output) + '.map')
        result = run([LD, *command, '--cref', '-Map', map_file])
        if result.returncode == 0:
            report = {'candidates': len(labels), 'fallback': len(disabled),
                      'direct': len(labels - disabled),
                      'relaxation_passes': len(history),
                      'total_link_passes': len(history) + 1,
                      'safety_fallback': safety_fallback,
                      'rom_references': os.environ.get('ROM_REFERENCES', '1'),
                      'pass_history': history,
                      'invocation': args,
                      'cwd': str(Path.cwd())}
            import object_order
            state = object_order.describe(output, map_file, groups, records, order)
            Path(str(output) + '.order.json').write_text(json.dumps(state, indent=2) + '\n')
            if fast_attempt:
                report['fast_layout'] = fast_attempt
                report['total_link_passes'] += fast_attempt['link_calls']
            report['tst_cleanup'] = cleanup_stats(records, disabled, output)
            report['object_order'] = ordering or 'incumbent'
            Path(str(output) + '.calls.json').write_text(json.dumps(report, indent=2) + '\n')
            with Path(str(output) + '.passes.jsonl').open('a') as log:
                log.write(json.dumps(report) + '\n')
        return result.returncode



def cleanup_stats(records, disabled, output):
    removable = set().union(*(flag_cleanup.removable_sites(record) for record, _, _ in records))
    candidates = removable - disabled
    live = candidates & Image(output).values.keys() if candidates else set()
    return {'enabled': flag_cleanup.enabled(), 'removed_live_tst': len(live),
            'instruction_bytes_removed': 2*len(live),
            'a5_cleanup': a5_cleanup.live_stats(records, Image(output)),
            'asm_liveness': asm_liveness.live_stats(records, disabled, Image(output))}


def fixup_module():
    spec = importlib.util.spec_from_file_location('os3k_fixups', ROOT/'os3k/fixups.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package(args):
    """Produce a checked ELF and image, reusing discovery for table sizing."""
    output = Path(args[args.index('-o')+1])
    Path(str(output)+'.calls.json').unlink(missing_ok=True)
    old_single = os.environ.get('OS3K_SINGLE_STAGE')
    os.environ['OS3K_SINGLE_STAGE'] = '1'
    try:
        result = linker(args)
    finally:
        if old_single is None: os.environ.pop('OS3K_SINGLE_STAGE', None)
        else: os.environ['OS3K_SINGLE_STAGE'] = old_single
    if result: return result
    module = fixup_module()
    metadata = Image(output)
    offsets = module.fixups(metadata)
    values = metadata.values
    report_path = Path(str(output)+'.calls.json')
    first_report = json.loads(report_path.read_text()) if report_path.exists() else {'total_link_passes':1}
    calls = first_report['total_link_passes']
    resized = values['__os3k_reloc_size'] != len(offsets)
    if resized:
        retry=args.copy()
        index=next(i for i,a in enumerate(retry) if a.startswith('__os3k_reloc_size='))
        retry[index]='__os3k_reloc_size='+str(len(offsets))
        result=linker(retry)
        if result:return result
        final_offsets=module.fixups(output)
        if len(final_offsets)!=len(offsets):raise RuntimeError('Relocation count changed during fallback sizing')
        offsets=final_offsets
        retry_report = Path(str(output)+'.calls.json')
        calls += json.loads(retry_report.read_text())['total_link_passes'] if retry_report.exists() else 1
    table=Path(str(output)+'.reloc')
    table.write_bytes(b''.join(struct.pack('>I',offset) for offset in [*offsets,0]))
    run([PREFIX+'objcopy','--update-section','.data.reloc='+str(table),output],check=True)
    run([PREFIX+'objcopy','-O','binary',output,output.with_suffix('.OS3KApp')],check=True)
    Path(str(output)+'.package.json').write_text(json.dumps({'total_link_calls':calls,
        'relocation_count':len(offsets),'sizing_retry':resized})+'\n')
    table.unlink()
    return 0

if __name__ == '__main__':
    mode, *arguments = sys.argv[1:]
    sys.exit(compiler(arguments) if mode == 'cc' else package(arguments) if mode == 'package' else linker(arguments))
