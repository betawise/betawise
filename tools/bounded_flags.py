"""Bounded emitted-assembly NZVC proofs for generated stack-push helpers.

Follow at most four local jumps and 32 lines; an ordinary C call or a known
full NZVC overwrite terminates a proof. X is preserved by MOVE and TST.
Unknown control flow, inline assembly and status-register uses retain TST.
"""
import re
import flag_cleanup
CALL=re.compile(r'^(?:jsr|bsr)(?:\.[bswl])?\s+')
JUMP=re.compile(r'^(?:jra|bra(?:\.[bswl])?|jmp)\s+([\w.$]+)$')
ADDRESS=re.compile(r'%(?:a[0-7]|sp|fp)$')


def prove(record, calls=False, cfg=False, arithmetic=False, limit=64, jumps=8):
    lines=record['assembly'].splitlines()
    tokens={s['token']:s for s in record['sites']}
    labels={line.strip()[:-1]:i for i,line in enumerate(lines) if re.fullmatch(r'[\w.$]+:',line.strip())}
    inline=set();inside=False
    for i,line in enumerate(lines):
        if line.strip()=='#APP':inside=True
        if inside:inline.add(i)
        if line.strip()=='#NO_APP':inside=False
    def walk(start):
        pos=start;visited=set();hops=0;steps=0
        while 0<=pos<len(lines):
            if steps>=limit:return False,'instruction-budget'
            if pos in visited:return False,'cycle'
            visited.add(pos);steps+=1
            if pos in inline:return False,'inline-asm'
            line=lines[pos].strip();site=tokens.get(line)
            if site:
                if site.get('kind','call')=='call':
                    return (True,'C-call') if calls else (False,'call')
                line='move.l __address,'+site['register']
            if calls and CALL.match(line):return True,'C-call'
            if cfg:
                match=JUMP.fullmatch(line)
                if match:
                    target=match[1]
                    if target not in labels:return False,'unresolved-jump'
                    if hops>=jumps:return False,'jump-budget'
                    # Crossing a function or section boundary is not allowed.
                    destination=labels[target]
                    lo,hi=sorted((pos,destination))
                    if any(re.match(r'\.(?:size|section|text|data|bss)\b',s.strip()) for s in lines[lo:hi+1]):
                        return False,'section-boundary'
                    pos=destination;hops+=1;continue
            if arithmetic:
                words=line.lower().split(None,1);op=words[0] if words else ''
                operands=words[1] if len(words)>1 else ''
                if re.fullmatch(r'(?:add|sub|addq|subq)\.[bwl]',op) and ',' in operands:
                    # Address-register aliases ADDA/SUBA preserve NZVC; data
                    # arithmetic overwrites all NZVC without reading old NZVC.
                    dest=operands.rsplit(',',1)[1].strip()
                    if set(flag_cleanup._REGISTERS.findall(operands))-flag_cleanup._ORDINARY:
                        return False,'special-register'
                    if not ADDRESS.fullmatch(dest):return True,'arithmetic-overwrite'
                    pos+=1;continue
            effect=flag_cleanup.effect(line)
            if effect=='write':return True,'overwrite'
            if effect=='barrier':return False,'barrier:'+line.split(None,1)[0]
            pos+=1
        return False,'end'
    result={}
    for i,line in enumerate(lines):
        site=tokens.get(line.strip())
        if site and site.get('kind')=='address' and site['register'].strip()=='-(%sp)':
            result[site['label']]=walk(i+1)
    return result
