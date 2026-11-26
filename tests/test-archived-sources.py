#!/usr/bin/env python3
"""Audit exclusions require both research location and an exact archive hash."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from archived_sources import recorded_snapshot


class ArchiveSources(unittest.TestCase):
    def test_recorded_and_modified_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for filename in ('archive.json', 'manifest.json'):
                directory = root / 'research' / filename
                directory.mkdir(parents=True)
                source = directory / 'Old.c'
                source.write_text('APPLET_ID(0xA1B1)\n')
                sources = {'Old.c': hashlib.sha256(source.read_bytes()).hexdigest()}
                record = {'sources': sources} if filename == 'archive.json' else sources
                (directory / filename).write_text(json.dumps(record))
                self.assertTrue(recorded_snapshot(source, root))
                source.write_text('APPLET_ID(0xA1B2)\n')
                self.assertFalse(recorded_snapshot(source, root))

    def test_legacy_catalog_and_nonarchive_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tests').mkdir()
            source = root / 'research/reference/Old.c'
            source.parent.mkdir(parents=True)
            source.write_text('APPLET_ID(0xA1B1)\n')
            catalog = {str(source.relative_to(root)): hashlib.sha256(source.read_bytes()).hexdigest()}
            (root / 'tests/historical-sources.json').write_text(json.dumps(catalog))
            self.assertTrue(recorded_snapshot(source, root))
            source.write_text('APPLET_ID(0xA1B2)\n')
            (source.parent / 'manifest.json').write_text('[]')
            self.assertFalse(recorded_snapshot(source, root))

    def test_active_sources_and_unlisted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for area in ('applets', 'research'):
                directory = root / area
                directory.mkdir()
                source = directory / 'Current.c'
                source.write_text('APPLET_ID(0xA1B1)\n')
                (directory / 'archive.json').write_text(json.dumps({'sources': {'Other.c': hashlib.sha256(source.read_bytes()).hexdigest()}}))
                self.assertFalse(recorded_snapshot(source, root))
                if area == 'applets':
                    (directory / 'archive.json').write_text(json.dumps({'sources': {'Current.c': hashlib.sha256(source.read_bytes()).hexdigest()}}))
                    self.assertFalse(recorded_snapshot(source, root))


if __name__ == '__main__':
    unittest.main()
