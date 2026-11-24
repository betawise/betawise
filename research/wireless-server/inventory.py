#!/usr/bin/env python3
"""Catalog the privately supplied NEO Manager package without executing vendor code.

Extract first with unzip and msiextract as documented in README.md. Reports use
workspace-relative paths. --update adds applets/copies to existing ABI inventories;
it never guesses ROM execution bases or changes the ROMs selected by live tests.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
ABI = HERE.parent / 'abi-audit'
PACKAGE = WORKSPACE / 'Ghidra/NEOManager3_9_3USPC.zip'
EXTRACTED = WORKSPACE / 'Ghidra/NEOManager3_9_3USPC-extracted'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update', action='store_true')
    args = parser.parse_args()
    applets = json.loads((ABI / 'vendor-image-inventory.json').read_text())
    roms = json.loads((ABI / 'rom-inventory.json').read_text())
    known_applets = {r['sha256']: r for r in applets}
    known_roms = {r['sha256']: r for r in roms}
    # Historical small boot images are not main-ROM syscall tables.
    historical = {}
    for folder in ['Alphasmart 3000', 'Alphasmart Neo']:
        for path in sorted((WORKSPACE / 'Ghidra' / folder / 'SmartApplets').iterdir()):
            if path.suffix.lower() in ('.os3kos', '.os3kapp'):
                historical.setdefault(digest(path), []).append(str(path.relative_to(WORKSPACE)))
    rows, evidence = [], []
    for path in sorted(EXTRACTED.rglob('*')):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in ('.os3kos', '.os3kapp', '.fud', '.exe', '.dll', '.msi', '.cab'):
            continue
        rel = str(path.relative_to(WORKSPACE))
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        row = dict(path=rel, size=len(data), sha256=sha)
        if ext == '.os3kapp':
            assert data[:4] == bytes.fromhex('c0ffeead'), rel
            assert int.from_bytes(data[4:8], 'big') == len(data), rel
            row.update(kind='applet', name=data[24:60].split(b'\0')[0].decode('ascii'),
                       version_raw=data[60:64].hex(), historical_matches=historical.get(sha, []))
            previous = known_applets.get(sha)
            if args.update:
                if previous is None:
                    previous = dict(path=rel, name=row['name'], sha256=sha, copies=[])
                    applets.append(previous)
                    known_applets[sha] = previous
                elif rel != previous['path'] and rel not in previous.setdefault('copies', []):
                    previous['copies'].append(rel)
        elif ext == '.os3kos':
            previous = known_roms.get(sha)
            row.update(kind='main-rom' if previous else 'supplemental-rom',
                       matches=historical.get(sha, []))
            if previous:
                row['inventory_name'] = previous['name']
                if args.update and rel not in previous.setdefault('copies', []):
                    previous['copies'].append(rel)
        elif ext == '.fud':
            header = data.split(b'\r\n\r\n', 1)[0].decode('ascii')
            assert header.startswith('SATURN FIRMWARE FILE/1.0\r\n'), rel
            row.update(kind='saturn-firmware-package', header=header.splitlines(),
                       header_fields=dict(line.split(': ', 1) for line in header.splitlines()[1:]))
        else:
            row['kind'] = 'windows-component'
        rows.append(row)
        # Preserve static evidence separately from conclusions. Offsets refer to
        # original file bytes; strings alone do not prove execution or wire format.
        if ext in ('.fud', '.os3kapp') or (ext == '.exe' and 'Wireless Server' in rel):
            for encoding, pattern in [('ascii', rb'[ -~]{5,}'),
                                      ('utf-16le', rb'(?:[ -~]\x00){5,}')]:
                for match in re.finditer(pattern, data):
                    evidence.append(dict(path=rel, offset=match.start(),
                                         encoding=encoding, text=match.group().decode(encoding)))
    assert rows, 'No extracted files found; follow README.md extraction instructions'
    save(HERE / 'package-inventory.json', dict(archive=dict(path=str(PACKAGE.relative_to(WORKSPACE)),
         size=PACKAGE.stat().st_size, sha256=digest(PACKAGE)), files=rows))
    save(EXTRACTED / 'static-strings.json', evidence)
    # Keep the full dump with private inputs; retain focused protocol evidence
    # in the research repository rather than megabytes of runtime/library names.
    relevant = re.compile(r'SDTP|SDML|<SRQ|<data|SATURN FIRMWARE|SaturnUplinkComm|'
                          r'HidD_|HidP_|mPANId|mEncryption|mDestAddr|mMSDUHandle|'
                          r'Message_(?:UL|Data|Associate|Disassociate|Beacon)|'
                          r'PAN Name|USBSend|DataIndication|BeaconNotify|MACTimer|'
                          r'/auth|/setua|/receivefile|/sendfile|cl:%|\{auth|\{nf|\{ua')
    save(HERE / 'protocol-strings.json', [r for r in evidence if relevant.search(r['text'])])
    if args.update:
        save(ABI / 'vendor-image-inventory.json', applets)
        save(ABI / 'rom-inventory.json', roms)
    print(f'Cataloged {len(rows)} components; preserved {len(evidence)} strings with byte offsets.')


if __name__ == '__main__':
    main()
