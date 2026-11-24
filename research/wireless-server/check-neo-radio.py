#!/usr/bin/env python3
"""Local bounded instruction checks for the reviewed Neo radio memory handlers.

This is deliberately NOT a radio/8051 emulator or a hardware acceptance test.
Unknown instructions fail. Execute only the straight-line MOVX handler bodies,
after their compiler prologue and before their reply construction.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]


def handler(code, start, end, xdata):
    regs = [0] * 8
    acc, dptr, pc = 0, 0, start
    stack = []
    steps = 0
    while pc < end:
        op = code[pc]
        pc += 1
        steps += 1
        if steps > 128:
            raise AssertionError('handler exceeded instruction bound')
        if op == 0x90:
            dptr = int.from_bytes(code[pc:pc+2], 'big')
            pc += 2
        elif op == 0xe0:
            acc = xdata[dptr]
        elif op == 0xf0:
            xdata[dptr] = acc
        elif op == 0xa3:
            dptr = (dptr + 1) & 65535
        elif op == 0xe4:
            acc = 0
        elif 0xf8 <= op <= 0xff:
            regs[op - 0xf8] = acc
        elif 0xe8 <= op <= 0xef:
            acc = regs[op - 0xe8]
        elif 0xc8 <= op <= 0xcf:
            acc, regs[op - 0xc8] = regs[op - 0xc8], acc
        elif op == 0xf5:
            direct = code[pc]
            pc += 1
            if direct == 0x82:
                dptr = (dptr & 0xff00) | acc
            elif direct == 0x83:
                dptr = (acc << 8) | (dptr & 255)
            else:
                raise AssertionError(f'unsupported direct write {direct:x}')
        elif 0x88 <= op <= 0x8f:
            direct = code[pc]
            pc += 1
            if direct != 0x82:
                raise AssertionError(f'unsupported register destination {direct:x}')
            dptr = (dptr & 0xff00) | regs[op - 0x88]
        elif op in (0xc0, 0xd0):
            if code[pc] != 0xe0:
                raise AssertionError('unsupported stack operand')
            pc += 1
            if op == 0xc0:
                stack.append(acc)
            else:
                acc = stack.pop()
        else:
            raise AssertionError(f'unsupported instruction {op:02x} at {pc-1:04x}')
    assert pc == end and not stack
    return steps


def main():
    spec = importlib.util.spec_from_file_location('modules', HERE/'decode-neo-modules.py')
    modules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modules)
    inventory = json.loads((HERE/'package-inventory.json').read_text())
    row = next(r for r in inventory['files'] if r['sha256'] == modules.EXPECTED)
    app = (WORKSPACE/row['path']).read_bytes()
    assert hashlib.sha256(app).hexdigest() == modules.EXPECTED
    code, _ = modules.decode_resource(app, 0xccf2, '02.00')
    checks = []
    # Independently exercise the actual straight-line instructions over varied
    # addresses/data, including a register-shaped address and byte boundaries.
    for address, value in [(0x6249, 0xa5), (0x6193, 0x40), (0x12ff, 0), (0x1300, 255)]:
        mem = bytearray(65536)
        mem[0x1b17:0x1b19] = (0x100).to_bytes(2, 'little')
        mem[0x1b15:0x1b17] = (0x200).to_bytes(2, 'little')
        mem[0x106:0x109] = address.to_bytes(2, 'big') + bytes([value])
        before = bytes(mem)
        steps = handler(code, 0x2dd1, 0x2e18, mem)
        assert mem[address] == value
        assert all(a == address or before[a] == mem[a] for a in range(65536))
        checks.append(dict(test='0800 write body', address=address, value=value, steps=steps, result='PASS'))
        mem[0x206] = value ^ 255
        steps = handler(code, 0x2e47, 0x2e89, mem)
        assert mem[0x206] == value
        checks.append(dict(test='0801 read body', address=address, value=value, steps=steps, result='PASS'))
    # High-byte dispatcher: 0d8f helper, zero ranges, twelve singleton cases.
    assert code[0x98a2:0x98a9] == bytes.fromhex('120d8f00000c00')
    cases = {int.from_bytes(code[p:p+2], 'little'): int.from_bytes(code[p+2:p+4], 'little')
             for p in range(0x98a9, 0x98a9+12*4, 4)}
    assert cases[0] == 0x98db and cases[0x200] == 0x9934 and cases[0x300] == 0x996d and cases[0x800] == 0x9986
    # Dispatcher calls / veneers are checked against original image bytes.
    for call, veneer, destination in [(0x99c4,0x1767,0x2dcc), (0x99db,0x1761,0x2e42),
                                      (0x9998,0x1845,0x1867), (0x99af,0x1839,0x19c1)]:
        assert code[call:call+3] == b'\x12'+veneer.to_bytes(2,'big')
        assert code[veneer:veneer+6] == bytes.fromhex('120e49')+destination.to_bytes(2,'little')+b'\0'
    report = dict(scope='Static dispatch checks and bounded straight-line instruction execution; no SPI/RF hardware',
                  source_sha256=modules.EXPECTED, checks=checks,
                  dispatcher_cases={hex(k):hex(v) for k,v in cases.items()})
    (HERE/'neo-radio-validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS {len(checks)} handler executions; dispatcher table and four call/veneer mappings')


if __name__ == '__main__':
    main()
