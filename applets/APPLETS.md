# Applet ID index (0xA1A0..0xA1FF)

| ID | Applet or resource |
| --- | --- |
| `0xA1A0` | Hello World |
| `0xA1BA` | EhBASIC |
| `0xA1C0` | MicroPython |
| `0xA1CB` | UCBLogo |
| `0xA1DE` | DebugTool |
| `0xA1F0` | BetaWise Terminal |
| `0xA1F1` | File Manager |

See the
[SmartApplet ID registry](https://github.com/isotherm/betawise/blob/HEAD/applets/REGISTRY.md)
to request an ID block.

Tests and research fixtures use [private IDs](PRIVATE_IDS.md). QEMU uses
`0xFF01`. Hello World is a bundled public applet and retains `0xA1A0`.
