"""Independent source-token and subset-DP search oracle (not the reader algorithm)."""

import re

WORD = re.compile(r"[a-z]+(?:'[a-z]+)*")

def covering(events, n):
    reach = {0}
    for _, _, _, mask in events:
        reach |= {bits | 1 << i for bits in list(reach) for i in range(n) if mask & 1 << i and (not bits & 1 << i)}
    return (1 << n) - 1 in reach

def unordered(events, n, mode, nearby_words=20, include_end=False):
    pending = []
    out = []
    last_verse = 0
    suppressed = False
    last_start = None
    for pos, v, w, mask in events:
        if mode == 0 and v != last_verse:
            pending = []
            suppressed = False
        last_verse = v
        if suppressed:
            continue
        if mode == 2:
            pending = [e for e in pending if pos - e[0] < nearby_words]
        if mask:
            pending.append((pos, v, w, mask))
        if mask and covering(pending, n):
            while len(pending) > 1 and covering(pending[1:], n):
                pending.pop(0)
            if mode == 2 and pending[0][0] == last_start:
                continue
            last_start = pending[0][0]
            out.append((pending[0][1], pending[0][2], v, w) if include_end else (pending[0][1], pending[0][2]))
            if mode != 2:
                pending = []
            suppressed = mode == 0
    return out

def oracle(chapters, query, mode, nearby_words=20, include_end=False):
    query = query.replace("’", "'")
    qs = [(m.group().lower(), query[m.end():m.end() + 1] == '*') for m in re.finditer("[A-Za-z]+(?:'[A-Za-z]+)*", query)]
    out = []
    for ci, ch in enumerate(chapters):
        events = []
        pos = 0
        for vi, v in enumerate(ch, 1):
            words = WORD.findall(v.replace("’", "'").lower())
            if mode == 1:
                out.extend((((ci, vi, j, vi, j+len(qs)-1) if include_end else (ci, vi, j)) for j in range(len(words) - len(qs) + 1) if all((words[j + k].startswith(q) if star else words[j + k] == q for k, (q, star) in enumerate(qs)))))
            else:
                for wi, w in enumerate(words):
                    mask = sum((1 << k for k, (q, star) in enumerate(qs) if (w.startswith(q) if star else w == q)))
                    events.append((pos, vi, wi, mask))
                    pos += 1
        if mode != 1:
            out.extend((ci, *hit) for hit in unordered(events, len(qs), mode, nearby_words, include_end))
    return out
