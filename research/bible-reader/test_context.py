#!/usr/bin/env python3
"""Local arithmetic/backend tests; no firmware, network or model inference."""
import json
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import unittest
from context_models import model_bytes, sequences_bytes


class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='bible-context-')
        cls.root = Path(cls.tmp.name)
        cls.binary = cls.root / 'codec'
        subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', str(Path(__file__).with_name('context_codec.cpp')), '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def roundtrip(self, sequences, counts, candidates=(), order=0, wide=False, exclusion=False):
        model, _, _ = model_bytes(counts, candidates, len(counts), order, 1000000, wide, exclusion)
        raw = sequences_bytes(sequences)
        paths = [self.root / name for name in ['input', 'model', 'archive', 'decoded']]
        paths[0].write_bytes(raw)
        paths[1].write_bytes(model)
        result = subprocess.run([str(self.binary), *map(str, paths)], check=True, capture_output=True, text=True)
        self.assertEqual(paths[3].read_bytes(), raw)
        # Standalone decoding receives no source symbols or training tables.
        subprocess.run([str(self.binary), '--decode', str(paths[2]), str(paths[3])], check=True)
        self.assertEqual(paths[3].read_bytes(), raw)
        return json.loads(result.stdout), paths[2]

    def test_uniform_binary_has_expected_bit_cost(self):
        rng = random.Random(42)
        stats, archive = self.roundtrip([[rng.randrange(2) for _ in range(1000)]], [1, 1])
        # Exactly one bit/symbol, two termination bits and byte padding.
        self.assertEqual(stats['payload_bytes'], 126)
        data = bytearray(archive.read_bytes())
        size = struct.unpack_from('>I', data, 8)[0]
        data[16 + size + 16 + 10] ^= 0x80
        archive.write_bytes(data)
        result = subprocess.run([str(self.binary), '--decode', str(archive), str(self.root / 'corrupt')], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_zero_frequencies_and_single_symbol(self):
        self.roundtrip([[1, 3] * 1000, [], [3], [1] * 3000], [0, 1, 0, 2])
        stats, _ = self.roundtrip([[0] * 10000], [1])
        self.assertEqual(stats['payload_bytes'], 1)

    def test_sparse_escape_with_and_without_exclusion(self):
        rng = random.Random(49)
        sequences = [[rng.choices(range(4), weights=[80, 10, 6, 4])[0] for _ in range(n)] for n in [1, 31, 10000]]
        # For previous symbol zero, explicitly model zero and escape the rest.
        candidate = [(10, 100, 6, 20, [(0, 80), (4, 20)])]
        for exclusion in [False, True]:
            for wide in [False, True]:
                self.roundtrip(sequences, [800000, 100000, 60000, 40000], candidate, 1, wide, exclusion)

    def test_large_alphabet_and_multilevel_backoff(self):
        self.roundtrip([[0, 65533, 9, 65532] * 40], [1] * 65534)
        # Highest-order escape must back off to the shorter context, then base.
        rng = random.Random(9)
        sequences = [[rng.randrange(3) for _ in range(5000)], [2, 2, 1, 0]]
        # alphabet=3, key([0])=5, key([0,0])=21.
        candidates = [(10, 100, 5, 20, [(1, 3), (3, 8)]), (9, 90, 21, 20, [(0, 6), (3, 7)])]
        self.roundtrip(sequences, [1, 2, 3], candidates, 2)

    def test_large_exclusion_set(self):
        entries = [(s, 1) for s in range(512)] + [(1024, 512)]
        candidates = [(10, 10000, 1026, 12 + 4 * len(entries), entries)]
        self.roundtrip([[0, s] for s in range(1024)], [1] * 1024, candidates, 1, exclusion=True)


if __name__ == '__main__':
    unittest.main()
