"""Flag-liveness proofs must stop before any possible observable CCR use."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import flag_cleanup
import relative_calls as adapter


class FlagCleanup(unittest.TestCase):
    def candidate(self, following):
        source = '\tmove.l target@GOT(%a5),-(%sp)\n'+following+'\n'
        record = adapter.make_record(source, ROOT/'tests/qemu/build/proof.o')
        with patch.dict(os.environ, OS3K_TST_CLEANUP='1'):
            return record, flag_cleanup.removable_sites(record)

    def test_definite_overwrites(self):
        for instruction in ['move.l %d0,%d1', 'move.w (%a0),12(%sp)',
                            'moveq #0,%d0', 'tst.l (%sp)', 'clr.w %d0',
                            'cmp.l %d0,%d1', 'cmpi.w #1,%d0', 'cmpa.l %a0,%a1']:
            with self.subTest(instruction=instruction):
                record, removable = self.candidate('\t'+instruction)
                self.assertEqual(removable, {record['sites'][0]['label']})

    def test_preservers_do_not_prove_dead_flags(self):
        for instruction in ['move.l %d0,%a0', 'movea.l %d0,%a0',
                            'move.w %d0,%fp', 'lea 4(%sp),%a0',
                            'pea (%a0)', 'movem.l (%sp)+,%d2-%d4',
                            'adda.w #4,%a0', 'suba.l #4,%a0', 'nop',
                            'link.w %a6,#0', 'unlk %a6']:
            with self.subTest(instruction=instruction):
                record, removable = self.candidate('\t'+instruction+'\n\tjne .Lused')
                self.assertFalse(removable)
                record, removable = self.candidate('\t'+instruction+'\n\tmoveq #0,%d0')
                self.assertEqual(removable, {record['sites'][0]['label']})

    def test_barriers(self):
        for instruction in ['jne .Lused', 'bra.w .Lnext', 'rts', 'addx.l %d0,%d1',
                            'seq %d0', 'dbne %d0,.Lnext', 'move.w %sr,%d0',
                            'move.w %ccr,%d0', 'move.l %a0,%usp',
                            'move.l %usp,%a0', 'unknown %d0',
                            '.align 4', '.set length,.-start', '.section .text.other',
                            '.if length > 4', '#APP', '#NO_APP',
                            'move.l %d0,%d1; jne .Lused']:
            with self.subTest(instruction=instruction):
                _, removable = self.candidate('\t'+instruction+'\n\tmoveq #0,%d0')
                self.assertFalse(removable)

    def test_other_generated_references_and_fallbacks(self):
        source = ('\tmove.l first@GOT(%a5),-(%sp)\n'
                  '\tmove.l second@GOT(%a5),-(%sp)\n'
                  '\tmoveq #0,%d0\n\trts\n')
        record = adapter.make_record(source, ROOT/'tests/qemu/build/chained.o')
        labels = {s['label'] for s in record['sites']}
        with patch.dict(os.environ, OS3K_TST_CLEANUP='1'):
            self.assertEqual(flag_cleanup.removable_sites(record), labels)
            for disabled in [set(), {record['sites'][1]['label']}, labels]:
                rendered = adapter.render(record, disabled, labels)
                self.assertNotIn('tst.l (%sp)', rendered)
        call = adapter.make_record(source.split('\tmoveq')[0]+
            '\tmove.l called@GOT(%a5),%a0\n\tjsr (%a0)\n\tmoveq #0,%d0\n',
            ROOT/'tests/qemu/build/call.o')
        with patch.dict(os.environ, OS3K_TST_CLEANUP='1'):
            omitted = flag_cleanup.removable_sites(call)
            pushes = [s for s in call['sites'] if s.get('kind') == 'address']
            self.assertIn(pushes[0]['label'], omitted)
            self.assertIn(pushes[1]['label'], omitted)

    def test_calls_jumps_and_arithmetic(self):
        for body in ['jsr (%a0)', 'bsr.w called', 'add.l #4,%d0',
                     'sub.w %d0,(%a0)',
                     'jra .Lkill\n.Lkill:\nmoveq #0,%d0']:
            with self.subTest(body=body):
                record, omitted = self.candidate(body)
                self.assertEqual(omitted, {record['sites'][0]['label']})
        for body in ['add.l #4,%a0\nrts',
                     '.Lloop:\njra .Lloop',
                     'jra .Lkill\n.size f,.-f\n.Lkill:\nmoveq #0,%d0',
                     'nop\n'*33+'moveq #0,%d0',
                     '#APP\njsr (%a0)\n#NO_APP']:
            with self.subTest(body=body):
                self.assertFalse(self.candidate(body)[1])

    def test_default_and_global_opt_out(self):
        record, _ = self.candidate('moveq #0,%d0')
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(flag_cleanup.enabled())
            self.assertTrue(flag_cleanup.removable_sites(record))
        with patch.dict(os.environ, {'OS3K_CLEANUP':'0','OS3K_TST_CLEANUP':'1'}, clear=True):
            self.assertFalse(flag_cleanup.enabled())
        with patch.dict(os.environ, {'OS3K_TST_CLEANUP':'0'}, clear=True):
            self.assertFalse(flag_cleanup.enabled())

    def test_original_tst_and_opt_out(self):
        record, _ = self.candidate('\ttst.l (%sp)\n\tmoveq #0,%d0')
        labels = {s['label'] for s in record['sites']}
        with patch.dict(os.environ, OS3K_TST_CLEANUP='1'):
            self.assertEqual(adapter.render(record, set(), labels).count('tst.l (%sp)'), 1)
        with patch.dict(os.environ, OS3K_TST_CLEANUP='0'):
            self.assertEqual(adapter.render(record, set(), labels).count('tst.l (%sp)'), 2)
        with patch.dict(os.environ, OS3K_TST_CLEANUP='1'):
            self.assertEqual(adapter.render(record, labels, labels).count('tst.l (%sp)'), 1)


if __name__ == '__main__':
    unittest.main()
