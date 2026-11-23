#!/usr/bin/env python3
"""Independently verify group-stream layout against native counts in six images."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
summary = json.loads((HERE / 'results-summary.json').read_text())
checked = 0
for run in summary['runs']:
    observation = next((s for s in run['observations'] if s.startswith('GROUPS ')), None)
    if observation is None:
        continue
    data = (ROOT / run['image']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == run['sha256']
    offset, expected_count = re.fullmatch(r'GROUPS offset=([0-9a-f]+) count=(\d+)', observation).groups()
    start = cursor = int(offset, 16)
    count = linked = members = 0
    classes = Counter()
    while True:
        assert cursor + 2 <= len(data)
        if int.from_bytes(data[cursor:cursor+2], 'big') == 0:
            break
        assert cursor + 6 <= len(data)
        additional = data[cursor+5]
        end = cursor + 6 + 2 * additional
        assert end <= len(data)
        classes[data[cursor+2]] += 1
        linked += int.from_bytes(data[cursor+3:cursor+5], 'big') != 0
        members += 1 + additional
        count += 1
        cursor = end
    assert count == int(expected_count), (run['image'], count, expected_count)
    print(json.dumps({'image': run['image'], 'groups': count, 'stream_bytes': cursor-start,
                      'group_memberships': members, 'linked_groups': linked,
                      'class_counts': dict(sorted(classes.items()))}))
    checked += 1
assert checked == 6
print('PASS six group streams match native enumeration counts')
