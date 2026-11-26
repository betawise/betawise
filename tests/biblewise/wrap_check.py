#!/usr/bin/env python3
"""Independent full-text checks for directional wrapping and Nearby distances."""
import argparse
import json
import subprocess
from pathlib import Path
from check import APP, compile_driver, HERE, read_matches
from oracle import oracle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    data = APP / 'build/data/kjv'
    chapters = [c for b in json.loads((data / 'source.json').read_text()) for c in b['chapters']]
    resource = out / 'summaries.c'
    resource.write_text('#include <stdint.h>\nconst uint8_t BibleGrammarSummary[]={' +
        ','.join(map(str, (data / 'pruning.bin').read_bytes())) + '};\n')
    driver = compile_driver(out, 'search-check',
        [HERE / 'search_check.c', APP / 'Search.c', APP / 'Decoder.c', resource])
    cases = 0
    for mode in range(3):
        for query in ['hypocrite', 'hypocrit*', 'beam plank', 'beam mote', 'God God', 'faith works']:
            for nearby in ([2, 10, 20, 99] if mode == 2 else [20]):
                expected = oracle(chapters, query, mode, nearby)
                for origin in [(0, 1, 0), (999, 16, 0), (1188, 22, 9999)]:
                    for direction in [-1, 1]:
                        for inclusive in [0, 1]:
                            if direction > 0:
                                first = [h for h in expected if h > origin or (inclusive and h == origin)]
                                wanted = first[:1] or expected[:1]
                            else:
                                first = [h for h in expected if h < origin or (inclusive and h == origin)]
                                wanted = first[-1:] or expected[-1:]
                            wrapped = int(not first)
                            wanted = [(*h, wrapped) for h in wanted]
                            command = [str(driver), str(data / 'container.bin'), str(data / 'search.bin'),
                                query, str(mode), *map(str, origin), str(direction), str(inclusive), '1', str(nearby)]
                            actual = read_matches(command)
                            assert actual == wanted, (query, mode, nearby, origin, direction, inclusive, actual, wanted)
                            cases += 1
    for nearby in [0, 1, 100]:
        command = [str(driver), str(data / 'container.bin'), str(data / 'search.bin'),
            'faith works', '2', '0', '1', '0', '1', '1', '1', str(nearby)]
        assert subprocess.run(command, stdout=subprocess.DEVNULL).returncode == 2
        cases += 1
    result = dict(status='passed', directional_distance_cases=cases)
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
