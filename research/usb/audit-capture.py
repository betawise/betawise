#!/usr/bin/env python3
"""Offline Linux usbmon/pcapng updater transcript and checksum audit.

Deliberately restricted to LINKTYPE_USB_LINUX_MMAPPED (220), little-endian
pcapng, bulk endpoints 01/82. No USB access, device writes, or text decoding.
Select a bus/device explicitly: captures can contain unrelated USB devices.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def transfers(raw, bus, device):
    offset = 0
    interfaces = []
    frame = 0
    while offset < len(raw):
        assert offset + 12 <= len(raw), 'truncated pcapng block'
        kind, size = struct.unpack_from('<II', raw, offset)
        assert size >= 12 and size % 4 == 0 and offset + size <= len(raw)
        assert struct.unpack_from('<I', raw, offset + size - 4)[0] == size
        block = raw[offset + 8:offset + size - 4]
        offset += size
        if kind == 0x0a0d0d0a:
            assert block[:4] == b'\x4d\x3c\x2b\x1a', 'unsupported endianness'
            interfaces = []
        elif kind == 1:
            interfaces.append(struct.unpack_from('<H', block)[0])
        elif kind == 6:
            frame += 1
            interface, _, _, captured, original = struct.unpack_from('<IIIII', block)
            assert interfaces[interface] == 220, 'unsupported capture linktype'
            data = block[20:20 + captured]
            assert len(data) == captured and captured == original, 'incomplete packet'
            assert len(data) >= 64, 'incomplete usbmon header'
            event, transfer, endpoint, address = data[8:12]
            packet_bus = struct.unpack_from('<H', data, 12)[0]
            if (packet_bus, address) != (bus, device) or transfer != 3:
                continue
            length = struct.unpack_from('<I', data, 36)[0]
            if not length or (endpoint, event) not in ((1, ord('S')), (0x82, ord('C'))):
                continue
            assert len(data) == 64 + length, 'incomplete USB payload'
            if event == ord('C'):
                assert struct.unpack_from('<i', data, 28)[0] == 0, 'USB completion error'
            yield frame, 'in' if endpoint & 128 else 'out', data[64:]


def audit(raw, bus, device):
    buffers = {'in': bytearray(), 'out': bytearray()}
    pending = {'in': None, 'out': None}
    rows = []
    for frame, direction, payload in transfers(raw, bus, device):
        buf = buffers[direction]
        buf.extend(payload)
        while buf:
            if pending[direction] is not None:
                length, checksum = pending[direction]
                if len(buf) < length:
                    break
                body = bytes(buf[:length])
                del buf[:length]
                assert sum(body) & 0xffff == checksum, f'frame {frame}: payload checksum'
                rows.append(dict(frame=frame, direction=direction, kind='payload',
                                 length=length, sum16=checksum,
                                 hex=body.hex(),
                                 sha256=hashlib.sha256(body).hexdigest()))
                pending[direction] = None
                continue
            if len(buf) < 8:
                break
            header = bytes(buf[:8])
            del buf[:8]
            if header == b'?\xff\0reset' or header.startswith(b'?Swtch') or header in (
                    b'Switched', b'NoSwitch', b'NoApplet'):
                rows.append(dict(frame=frame, direction=direction, kind='bootstrap',
                                 hex=header.hex()))
                continue
            assert sum(header[:7]) & 255 == header[7], f'frame {frame}: header checksum {header.hex()}'
            code = header[0]
            argument = int.from_bytes(header[1:5], 'big')
            trailing = int.from_bytes(header[5:7], 'big')
            rows.append(dict(frame=frame, direction=direction, kind='header',
                             code=code, argument=argument, trailing=trailing, hex=header.hex()))
            if (direction == 'out' and code == 2) or (
                    direction == 'in' and code in (0x40, 0x44, 0x4b, 0x4d, 0x5a)):
                if argument:
                    pending[direction] = argument, trailing
    assert not any(buffers.values()) and not any(pending.values()), 'incomplete protocol capture'
    assert rows, 'no selected transfers'
    return dict(capture_sha256=hashlib.sha256(raw).hexdigest(), bus=bus,
                device=device, records=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--bus', type=int, required=True)
    parser.add_argument('--device', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.capture.read_bytes(), args.bus, args.device), indent=2))
