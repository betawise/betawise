#!/usr/bin/env python3
"""Compatibility entry point for the shipping-image font execution checks.

Descriptors now receive runtime addresses directly, without CRT relocations.
"""
from check_minimal_fonts import main

if __name__ == '__main__':
    main()
