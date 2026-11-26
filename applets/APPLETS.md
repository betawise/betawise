# Applet ID index

## Applets (`0xA1A0`–`0xA1FF`)

| ID | Applet or resource |
| --- | --- |
| `0xA1A0` | Hello World |
| `0xA1BA` | EhBASIC |
| `0xA1C0` | MicroPython |
| `0xA1CB` | UCBLogo |
| `0xA1DE` | DebugTool |
| `0xA1F0` | BetaWise Terminal |
| `0xA1F1` | File Manager |

BetaWise Terminal Medium, Small and Tiny share `0xA1F0`; install only one at a time.

<a id="reading-fonts"></a>

## Reading fonts (`0xAFF0`-`0xAFFF`)

| ID | Applet or resource | Lines |
| --- | --- | ---: |
| `0xAFF0` | BetaWise Serif Large | 3 |
| `0xAFF1` | BetaWise Serif Medium | 4 |
| `0xAFF2` | BetaWise Serif Small | 5 |
| `0xAFF3` | BetaWise Serif Tiny | 6 |
| `0xAFF4` | BetaWise Sans Large | 3 |
| `0xAFF5` | BetaWise Sans Medium | 4 |
| `0xAFF6` | BetaWise Sans Small | 5 |
| `0xAFF7` | BetaWise Sans Tiny | 6 |
| `0xAFF8` | BetaWise Book Large | 3 |
| `0xAFF9` | BetaWise Book Medium | 4 |
| `0xAFFA` | BetaWise Book Small | 5 |
| `0xAFFB` | BetaWise Book Tiny | 6 |
| `0xAFFC` | BetaWise Mono Large | 3 |
| `0xAFFD` | BetaWise Mono Medium | 4 |
| `0xAFFE` | BetaWise Mono Small | 5 |
| `0xAFFF` | BetaWise Mono Tiny | 6 |

See the
[SmartApplet ID registry](https://github.com/isotherm/betawise/blob/HEAD/applets/REGISTRY.md)
to request an ID block.

Tests and research fixtures use [private IDs](PRIVATE_IDS.md). QEMU uses
`0xFF01`. Hello World is a bundled public applet and retains `0xA1A0`.
