#!/usr/bin/env python3
"""Exercise the production reference functions against independent input cases."""
import argparse
import json
from pathlib import Path
import subprocess

APP = Path(__file__).resolve().parents[2] / 'applets/BibleWise'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = (APP / 'BibleWise.c').read_text()
    functions = source[source.index('static const char g_book_aliases'):
        source.index('static unsigned FindWordAtOffset')]
    data = APP / 'build/data/kjv'
    verses = ','.join(map(str, (data / 'verses.bin').read_bytes()))
    driver = args.output / 'references.c'
    driver.write_text('#include <stdio.h>\n#include <string.h>\n#include <stdbool.h>\n#include "BibleFormat.h"\n'
        '#include "Navigation.h"\nconst uint8_t BibleVerseCounts[]={' + verses + '};\n' + functions +
        '\nint main(int argc,char**argv){unsigned c=9999,v=9999;'
        'int r=ParseReference(argv[1],&c,&v);printf("%d %u %u\\n",r,c,v);return argc<2;}\n')
    executable = args.output / 'references'
    subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-I' + str(APP), '-I' + str(data),
        str(driver), '-o', str(executable)], check=True)
    books = json.loads((data / 'source.json').read_text())
    cases = []
    chapter = 0
    for book in books:
        cases.append((book['name'] + ' 1:1', (1, chapter, 1)))
        chapter += len(book['chapters'])
    def offset(book, chapter):
        return sum(len(item['chapters']) for item in books[:book - 1]) + chapter - 1
    for text, book, chapter, verse in [
        ('John3:16', 43, 3, 16), ('john 3 16', 43, 3, 16), (' Jn 3:16 ', 43, 3, 16),
        ('1Cor 13:4', 46, 13, 4), ('1 Co 13 4', 46, 13, 4), ('1Co13:4', 46, 13, 4),
        ('1 Cor. 13:4', 46, 13, 4), ('Jdg 1:1', 7, 1, 1), ('Jud 1:3', 65, 1, 3),
        ('Ps 119:176', 19, 119, 176), ('Psalm 23', 19, 23, 0), ('Sos 2:1', 22, 2, 1),
        ('Jas 1:2', 59, 1, 2), ('Phlm 1:3', 57, 1, 3), ('Phil 1:3', 50, 1, 3),
        ('1 3 15', 1, 3, 15), ('66 22 21', 66, 22, 21),
    ]:
        cases.append((text, (1, offset(book, chapter), verse)))
    for text in ['John', 'faith works', 'kingdom of God', 'be* bel*', 'unknown 3', '']:
        cases.append((text, (0,)))
    for text in ['Ph 1', 'John 0', 'John 22', 'John 3:99', 'John 3:0', 'John 3:',
        'John 3:xyz', 'Ps 119:0', 'Ps 119 0', '19 119 0', 'John 9999999999999999', '1Cor 13:4 extra', '67 1 1']:
        cases.append((text, (-1,)))
    for text, expected in cases:
        actual = tuple(map(int, subprocess.check_output([str(executable), text], text=True).split()))
        assert actual[:len(expected)] == expected, (text, actual, expected)
    report = {'status': 'passed', 'cases': len(cases)}
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
