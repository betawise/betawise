"""Defaults and opt-outs are independent of the frame proof cache."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import a5_cleanup

class A5Controls(unittest.TestCase):
    def test_defaults_and_overrides(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(a5_cleanup.enabled())
        for settings in [{'OS3K_CLEANUP':'0'}, {'OS3K_A5_CLEANUP':'0'}]:
            with patch.dict(os.environ, settings, clear=True):
                self.assertFalse(a5_cleanup.enabled())
        with patch.dict(os.environ, {'OS3K_CLEANUP':'0', 'OS3K_A5_CLEANUP':'1'}, clear=True):
            self.assertFalse(a5_cleanup.enabled())

if __name__ == '__main__':
    unittest.main()
