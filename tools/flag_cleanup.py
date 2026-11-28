"""Conservative NZVC liveness for the adapter's generated stack-push TSTs.

Only instructions known to overwrite all four affected flags prove them dead.
Ordinary C calls also kill incoming NZVC. Bounded local jumps may be followed;
conditional flag uses, status/control accesses and unknown operations stop it. X need not be killed: neither MOVE nor TST
changes it. Original instructions are never removed.
"""
from functools import lru_cache
import os
import re

_ADDRESS = re.compile(r'%(?:a[0-7]|sp|fp)$')
_REGISTERS = re.compile(r'%([a-z][a-z0-9]*)')
_ORDINARY = {*(f'a{i}' for i in range(8)), *(f'd{i}' for i in range(8)), 'sp', 'fp', 'pc'}
_PRESERVE = {'lea', 'pea', 'movea.w', 'movea.l', 'movem.w', 'movem.l',
             'adda.w', 'adda.l', 'suba.w', 'suba.l', 'nop', 'link.w', 'unlk'}
_WRITE = {'moveq', 'tst.b', 'tst.w', 'tst.l', 'clr.b', 'clr.w', 'clr.l',
          'cmp.b', 'cmp.w', 'cmp.l', 'cmpi.b', 'cmpi.w', 'cmpi.l', 'cmpa.w', 'cmpa.l'}


def enabled():
    return (os.environ.get('OS3K_CLEANUP', '1') == '1'
            and os.environ.get('OS3K_TST_CLEANUP', '1') == '1')


def effect(line):
    """Return write/preserve/barrier for the four flags, or skip for metadata."""
    line = line.strip()
    if not line:
        return 'preserve'
    if line in {'#APP', '#NO_APP'}:
        return 'barrier'
    if line.startswith(('#', '|')):
        return 'preserve'
    # Inline comments are harmless; multi-line comments and multiple asm
    # statements are deliberately outside this small instruction recognizer.
    line = re.sub(r'/\*[^\n]*?\*/', '', line).strip()
    if '/*' in line or '*/' in line or ';' in line:
        return 'barrier'
    line = line.split('|', 1)[0].strip()
    if not line or re.fullmatch(r'[\w.$]+:', line):
        return 'preserve'
    if re.match(r'\.(?:globl|global|hidden)\s', line):
        return 'preserve'
    words = line.lower().split(None, 1)
    op, operands = words[0], words[1] if len(words) == 2 else ''
    if set(_REGISTERS.findall(operands)) - _ORDINARY:
        return 'barrier'
    if op in {'move.b', 'move.w', 'move.l'}:
        if ',' not in operands:
            return 'barrier'
        destination = operands.rsplit(',', 1)[1].strip()
        if destination.startswith('#'):
            return 'barrier'
        return 'preserve' if _ADDRESS.fullmatch(destination) else 'write'
    if op in _WRITE:
        return 'write'
    if op in _PRESERVE:
        return 'preserve'
    return 'barrier'


@lru_cache(maxsize=1024)
def _removable(assembly, specifications):
    import bounded_flags
    record={'assembly':assembly,'sites':[{'token':token,'label':label,'kind':kind,'register':register}
                                        for token,label,kind,register in specifications]}
    return frozenset(label for label,(ok,_) in bounded_flags.prove(
        record,calls=True,cfg=True,arithmetic=True,limit=32,jumps=4).items() if ok)


def removable_sites(record):
    if not enabled():
        return frozenset()
    specifications = tuple((s['token'], s['label'], s.get('kind', 'call'), s['register'])
                           for s in record['sites'])
    return _removable(record['assembly'], specifications)


def site_delta(site, removable):
    if site.get('kind', 'call') == 'call':
        return -2
    if re.fullmatch(r'%(?:a[0-7]|sp)', site['register'].strip()):
        return 0
    if site['register'].strip() == '-(%sp)' and site['label'] in removable:
        return 0
    return 2
