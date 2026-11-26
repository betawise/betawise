"""Recognize immutable research snapshots without ignoring active sources."""
import hashlib
import json


def recorded_snapshot(path, root):
    if path.relative_to(root).parts[0] != 'research':
        return False
    catalog = root / 'tests/historical-sources.json'
    if catalog.is_file():
        expected = json.loads(catalog.read_text()).get(str(path.relative_to(root)))
        if expected == hashlib.sha256(path.read_bytes()).hexdigest():
            return True
    for directory in path.parents:
        if directory == root:
            break
        for name in ('archive.json', 'manifest.json'):
            manifest = directory / name
            if not manifest.is_file():
                continue
            record = json.loads(manifest.read_text())
            if not isinstance(record, dict):
                continue
            sources = record.get('sources', record)
            if not isinstance(sources, dict):
                continue
            expected = sources.get(str(path.relative_to(directory)))
            if isinstance(expected, str) and expected == hashlib.sha256(path.read_bytes()).hexdigest():
                return True
    return False
