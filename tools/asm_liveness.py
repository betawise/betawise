"""Bounded assembly-only scratch-register proofs for PIC address transfers.

Borrow A0/A1 only after proving an unavoidable full overwrite before any
read on every inspected path. Calls, returns, opaque control flow and unknown
instructions stop the proof; no ABI argument/return liveness is assumed.
Never use a removable GOT-call target load as an overwrite: it may become BSR.
"""
import os
import re
from functools import lru_cache

REG = re.compile(r'%(?:[ad][0-7]|sp|fp)\b')
REPORTS = {}

LABEL = r'[A-Za-z_.$][\w.$]*'
BARE_REGISTER = re.compile(r'(?<![\w.%])(?:[ad][0-7]|sp|fp)(?![\w.])', re.I)
CONDITION = r'(?:hi|ls|cc|cs|hs|lo|ne|eq|vc|vs|pl|mi|ge|lt|gt|le|t|f)'
PLAIN = re.compile(r'(?:moveq|pea|nop|exg|link(?:\.w)?|unlk|'
                   r'(?:move|movea|lea|add|adda|addq|sub|suba|subq|cmp|cmpa|cmpi|cmpm|'
                   r'tst|clr|neg|not|and|or|eor|andi|ori|eori|muls|mulu|divs|divu|'
                   r'ext|swap|asl|asr|lsl|lsr|rol|ror|roxl|roxr|btst|bset|bclr|bchg|'
                   r'addx|subx|negx|abcd|sbcd|nbcd)(?:\.[bwl])?|s'+CONDITION+r')$')


def enabled():
    return (os.environ.get('OS3K_CLEANUP', '1') == '1'
            and os.environ.get('OS3K_ASM_LIVENESS', '1') == '1')


def operands(text):
    parts = []; depth = 0; start = 0
    for i, char in enumerate(text):
        if char in '([':
            depth += 1
        elif char in ')]':
            depth -= 1
        elif char == ',' and not depth:
            parts.append(text[start:i].strip()); start = i+1
    if depth:
        return None
    parts.append(text[start:].strip())
    return parts


def register_number(name):
    if name == '%sp': return 15
    if name == '%fp': return 14
    return int(name[2])+(8 if name[1] == 'a' else 0)


def register_list(text, reverse=False):
    if re.fullmatch(r'#(?:0x[0-9a-fA-F]+|\d+)', text):
        digits = text[1:]
        base = 16 if digits.startswith('0x') else 8 if len(digits)>1 and digits.startswith('0') else 10
        try: value = int(digits, base)
        except ValueError: return None
        if not 0 <= value <= 65535:
            return None
        return {15-i if reverse else i for i in range(16) if value & (1 << i)}
    result = set()
    for item in text.split('/'):
        if re.fullmatch(r'%(?:[ad][0-7]|sp|fp)', item):
            result.add(register_number(item)); continue
        match = re.fullmatch(r'(%[ad][0-7])-(%[ad][0-7])', item)
        if not match or match[1][1] != match[2][1]:
            return None
        lo, hi = register_number(match[1]), register_number(match[2])
        if lo > hi: return None
        result.update(range(lo, hi+1))
    return result


def effect(text, register):
    """Return kill/preserve/read/unknown for the old complete address value."""
    text = text.strip().split('|', 1)[0].strip()
    if not text or re.fullmatch(LABEL+':', text):
        return 'preserve'
    if ';' in text or '/*' in text or '*/' in text or text.startswith('#'):
        return 'unknown'
    if re.match(r'\.(?:globl|global|hidden|local)\s', text):
        return 'preserve'
    if re.fullmatch(r'\.reloc\s+\.-2,R_68K_(?:PC16|16),.+', text):
        return 'preserve'
    words = text.split(None, 1)
    op = words[0]; args = operands(words[1]) if len(words) == 2 else []
    if args is None: return 'unknown'
    if re.search(r'%[A-Z]',text) or BARE_REGISTER.search(' '.join(args)):
        return 'unknown'
    ordinary = {*(f'a{i}' for i in range(8)), *(f'd{i}' for i in range(8)), 'sp', 'fp', 'pc'}
    if set(re.findall(r'%([a-z][a-z0-9]*)', ' '.join(args)))-ordinary:
        return 'unknown'
    if op in {'movem.l', 'movem.w'}:
        if len(args) != 2: return 'unknown'
        store = register_list(args[0], reverse=args[1].startswith('-('))
        load = register_list(args[1])
        if (store is None) == (load is None): return 'unknown'
        memory = args[1] if store is not None else args[0]
        if register in REG.findall(memory): return 'read'
        number = register_number(register)
        if store is not None: return 'read' if number in store else 'preserve'
        return 'kill' if number in load else 'preserve'
    if not PLAIN.fullmatch(op): return 'unknown'
    # These address-register writes replace all 32 bits, including MOVEA.W's
    # sign extension. Source/destination EAs may still read the old register.
    if op in {'move.l', 'move.w', 'movea.l', 'movea.w', 'lea'} and len(args) == 2 and args[1] == register:
        return 'read' if register in REG.findall(args[0]) else 'kill'
    return 'read' if register in REG.findall(' '.join(args)) else 'preserve'


@lru_cache(maxsize=256)
def context(assembly):
    lines = assembly.splitlines(); inline = set(); inside = False
    for i, line in enumerate(lines):
        if line.strip() == '#APP': inside = True
        if inside: inline.add(i)
        if line.strip() in {'#NO_APP', '#NOAPP'}: inside = False
    scopes = {}; labels = {}
    for i, line in enumerate(lines):
        name = re.fullmatch(r'\s*('+LABEL+r'):\s*', line)
        if name: labels[name[1]] = i
        match = re.fullmatch(r'\s*\.type\s+('+LABEL+r'),\s*@function\s*', line)
        if not match: continue
        name = match[1]; end = i+1
        while end < len(lines) and not re.match(r'\s*\.size\s+'+re.escape(name)+r'\s*,', lines[end]):
            end += 1
        if end == len(lines): continue
        entry = next((j for j in range(i+1,end) if lines[j].strip() == name+':'), None)
        if entry is None: continue
        block = lines[entry+1:end]
        # CFI can describe register uses that are invisible to machine operands.
        if any(re.match(r'\s*\.(?:type|cfi\w*)\b', s) for s in block): continue
        for j in range(entry+1,end): scopes[j] = (entry+1,end)
    return lines, inline, scopes, labels


def prove(assembly, sites, start, register, cfg=True, limit=64, jumps=4):
    lines, inline, scopes, labels = context(assembly)
    scope = scopes.get(start)
    if scope is None: return False, 'missing-or-opaque-function'
    if start in inline: return False, 'inline-assembly'
    tokens = {s['token']:s for s in sites}
    def walk(pos, steps, hops, visiting):
        if steps >= limit: return False, 'line-budget'
        if not scope[0] <= pos < scope[1]: return False, 'function-boundary'
        if pos in visiting: return False, 'cycle'
        if pos in inline: return False, 'inline-assembly'
        raw = lines[pos].strip(); site = tokens.get(raw)
        if site:
            if site.get('kind','call') == 'call':
                return False, 'call-token'  # Its target load may be removed.
            raw = site['original'].strip()
        if any(c in raw for c in (';', '/*', '*/')): return False, 'compound-assembly'
        text = raw.split('|',1)[0].strip()
        if re.match(r'(?:jsr|jbsr|bsr)(?:\.[bswl])?\b', text): return False, 'call'
        if re.match(r'(?:rts|rte|rtr|rtd|rtm)\b', text): return False, 'return'
        jump = re.fullmatch(r'(?:jra|bra(?:\.[bswl])?|jmp)\s+('+LABEL+r')', text)
        conditional = re.fullmatch(r'(?:j|b)'+CONDITION+r'(?:\.[bswl])?\s+('+LABEL+r')', text)
        loop = re.fullmatch(r'db(?:ra|'+CONDITION+r')\s+%d[0-7],('+LABEL+r')', text)
        active = visiting | {pos}
        if jump or conditional or loop:
            if not cfg: return False, 'control-flow'
            if hops >= jumps: return False, 'jump-budget'
            target = labels.get((jump or conditional or loop)[1])
            if target is None or not scope[0] <= target < scope[1]: return False, 'unresolved-jump'
            lo,hi = sorted((pos,target))
            if any(re.match(r'\s*\.(?:size|type|section|text|data|bss)\b', s) for s in lines[lo:hi+1]):
                return False, 'section-boundary'
            result = walk(target,steps+1,hops+1,active)
            if not result[0] or jump: return result
            return walk(pos+1,steps+1,hops+1,active)
        operation = effect(text,register)
        if operation == 'kill': return True, 'full-overwrite'
        if operation != 'preserve': return False, operation+':'+(text.split()[0] if text else '')
        return walk(pos+1,steps+1,hops,active)
    return walk(start+1,0,0,set())


def transform(record, assembly, disabled):
    """Inspect the fixed-up code, then apply all independent proofs together.

    In particular, direct BSRs are barriers and retained GOT call loads remain
    visible as full overwrites. Added scratch definitions never justify another
    replacement, since every proof sees the same immutable input assembly.
    """
    if not enabled(): return assembly
    lines, _, _, labels = context(assembly)
    allowed = record.get('asm_allowed', [])
    cfg = os.environ.get('OS3K_ASM_CFG','1') == '1'
    edits = {}; details = []
    for site in record['sites']:
        destination = site['register'].strip()
        if (site['label'] in disabled or site.get('kind') != 'address'
            or destination == '-(%sp)' or re.fullmatch(r'%(?:a[0-7]|sp|fp)',destination)):
            continue
        label = labels.get(site['label'])
        if label is None or label+3 >= len(lines): continue
        pea = re.fullmatch(r'\s*pea\s+(.+)', lines[label+1])
        relocation = re.fullmatch(r'\s*\.reloc\s+\.-2,R_68K_(?:PC16|16),.+',lines[label+2])
        move = re.fullmatch(r'\s*move\.l\s+\(%sp\)\+,(.+)',lines[label+3])
        if not pea or not relocation or not move: continue
        destination = move[1].strip()
        row = {'label':site['label'],'scratch':None,'proof':{}}
        for register in ['%a0','%a1']:
            if re.search(r'%[A-Z]',destination) or BARE_REGISTER.search(destination):
                row['proof'][register] = 'unsupported-register-spelling'; continue
            if register not in allowed:
                row['proof'][register] = 'fixed-or-missing-metadata'; continue
            if register in REG.findall(destination):
                row['proof'][register] = 'destination-use'; continue
            ok, reason = prove(assembly,[],label+3,register,cfg=cfg)
            row['proof'][register] = reason
            if ok:
                edits[label+1] = '\tlea '+pea[1]+','+register
                edits[label+3] = '\tmove.l '+register+','+destination
                row['scratch'] = register
                break
        details.append(row)
    REPORTS[record['object']] = details
    return '\n'.join(edits.get(i,line) for i,line in enumerate(lines))+'\n'


def live_stats(records, disabled, image):
    if not enabled():
        return {'enabled':False,'CFG':os.environ.get('OS3K_ASM_CFG','1')=='1',
                'stack_pairs_replaced':0,'sites':[]}
    sites = {s['label']:s for r,_,_ in records for s in REPORTS.get(r['object'],[])
             if s['label'] in image.values and s['label'] not in disabled}
    return {'enabled':enabled(), 'CFG':os.environ.get('OS3K_ASM_CFG','1')=='1',
            'stack_pairs_replaced':sum(s['scratch'] is not None for s in sites.values()),
            'sites':list(sites.values())}
