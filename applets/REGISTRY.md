# SmartApplet ID block registry

Betawise maintains the canonical list of SmartApplet ID block assignments. See
[HISTORICAL.md](HISTORICAL.md) for historical IDs.

| Inclusive range | Owner |
| --- | --- |
| `0x7100`–`0x717F` | [Community NEO fonts](HISTORICAL.md#community-neo-fonts) |
| `0x9000`–`0x900F` | [CoWriter resources](HISTORICAL.md#cowriter-resources) |
| `0xA000`–`0xA11F` | [AlphaSmart legacy applets](HISTORICAL.md#alphasmart-legacy-applets) |
| `0xA120`–`0xA13F` | [Jakub Kolcar / ioma8](https://github.com/ioma8/neo-re) |
| `0xA1A0`–`0xA1FF` | [Alpaxo / Betawise](APPLETS.md) |
| `0xAF00`–`0xAFEF` | [Legacy NEO fonts](HISTORICAL.md#legacy-neo-fonts) |
| `0xAFF0`–`0xAFFF` | [BetaWise reading fonts](APPLETS.md#reading-fonts) |
| `0xFF00`–`0xFFFE` | Private use: tests, examples, fixtures and local experiments |

The final 16 IDs of the former `0xAF00`–`0xAFFF` legacy font block are
allocated to BetaWise reading fonts. The historical vendor font IDs remain
unchanged. Individual font assignments are listed in [APPLETS.md](APPLETS.md#reading-fonts).

## Private use

`0xFF00`–`0xFFFE` is reserved for private use. No block request, public
registration or global owner assignment is required. Use `0xFF00`–`0xFFFE`
for applets; leave `0xFFFF` unassigned because it is an invalid/empty-ID
sentinel in existing tooling and firmware tables. This leaves 255 usable IDs.
Private IDs are not globally unique: coordinate IDs among applets installed
together. Tests, examples and fixtures should use distinct local private IDs
rather than consume a project's registered public block. Bundled public applets
such as Hello World keep their registered IDs. Betawise records its
local choices in [PRIVATE_IDS.md](PRIVATE_IDS.md); this is not a public registry.
Tests may intentionally impersonate an existing ID when exercising a vendor
lookup or compatibility contract. Document the impersonation in the fixture;
it does not allocate or claim that ID.

## Request a public block

For public applets outside private use, open a pull request to this file before using a new block. Add a row with the
requested range, maintainer, and project link. Request one or more 16-ID blocks.
Start on a 16-ID boundary and check the table and historical index for overlap.

Each maintainer manages the applet IDs within their own block. We encourage
maintainers to publish and link an index using the [APPLETS.md format](APPLETS.md).
