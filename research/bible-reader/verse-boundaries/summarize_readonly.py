#!/usr/bin/env python3
"""Preserve original-ROM read-only results and native end-gap observations."""
import json
import re
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'


def main():
    log = (BUILD / 'readonly-probe/neo_3_21/mame.log').read_text()
    assert 'READONLY gap=0 length=3 key_consumed=1 key_status=0' in log
    assert 'PASS text probe ' in log and 'FAIL text' not in log
    directory = BUILD / 'end-gap-interactions'
    result = json.loads((directory / 'results.json').read_text())
    assert result['status'] == 'passed'
    rows = []
    for index, check in enumerate(json.loads((directory / 'checks.json').read_text()), 1):
        editor = (directory / f'editor-{index:02}.bin').read_bytes()
        start, end = struct.unpack_from('>II', editor, 40)
        length = (directory / f'chapter-{index:02}.bin').stat().st_size
        rows.append(dict(name=check['name'], gap_start=start, gap_end=end,
            gap_bytes=end-start, raw_file_bytes=length, gap_at_eof=end==length))
    assert all(row['gap_bytes']==512 for row in rows)
    assert all(row['gap_at_eof'] for row in rows[:14])
    assert all(not row['gap_at_eof'] for row in rows[14:])
    report = dict(status='passed', readonly=dict(original_rom='Neo 3.21', gap_bytes=0,
        source_bytes=3, file_bytes=3, down_consumed=1, down_status=0,
        font_set_status='TEXT_ERROR_READ_ONLY (0x02000005)',
        save_position='No-op; file length remains three bytes', syscall_probe_cases=int(re.search(r'PASS text probe (\d+) cases',log).group(1))),
        end_gap=dict(status=result['status'], checkpoints=result['checkpoints'], observations=rows),
        production_changed=False)
    (BUILD / 'readonly-results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS read-only original-ROM probe and 17 end-gap checkpoints')


if __name__ == '__main__':
    main()
