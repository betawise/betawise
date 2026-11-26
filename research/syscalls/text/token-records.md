# Neo 3.21 text record framing

Investigation of the native text engine, 2026-11-24. These are engine behaviours,
not recovered names for the original record types.

The classification table at `0x44C7E0`, forward scanner `0x42C120`, reverse
scanner `0x42C2A4`, renderer `0x42A0F8`, and record validator `0x42B4F8`
agree on the following:

| Bytes | Native treatment |
| --- | --- |
| B3, B4, B7 | Three-byte opaque records: `marker payload marker`. No glyph advance or style change. |
| B5, B6, BC, BD | Ordinary one-byte glyphs. |
| B8, B9, BA, BB, BE, BF | Variable-length opaque records: `marker length payload… length marker`. No glyph advance or style change. |

The variable record length is an unsigned byte counting the **entire record**,
including both markers and both length bytes. Minimum length is four; maximum
is 255. Example: `B8 07 41 42 43 07 B8` contains three payload bytes and occupies
seven bytes. The reverse scanner reads the trailing length. The validator
requires matching markers and length bytes. Fixed three-byte records likewise
require matching markers.

`TextScanRead` (`0x4291BE`, syscall 179) preserves these records in raw mode and
omits them in plain-text mode. B5/B6/BC/BD survive plain-text conversion as glyphs.
This does not imply every insertion path accepts their raw values: the plain
insertion helper broadly escapes A1–BF (and 8F) using B0 literal records.

No per-type payload interpretation was established for these opaque records.
In particular, the engine behaviour alone does not establish that B9–BF are
linked-file or form records. The independently traced inline form envelope is
`A8 <FORM>…</FORM> 9D`; the text reader's form-expansion path handles that class
separately. AlphaWord's byte comparisons must also be interpreted in context:
its input/output protocol callbacks contain BB comparisons, which are not by
themselves evidence of an editor-record payload meaning.

## Low byte glyph slots

All 01–1F classify as ordinary glyphs except 09 (tab) and 0D (carriage return).
0A is an ordinary glyph to this native scanner, but avoiding it in a custom
mapping remains prudent because external text transports interpret LF.
00 is unsuitable for a general mapping because of NUL-terminated interfaces.

01–19 contains 25 positions, including tab and CR; it cannot hold 26 italic
letters directly. A 26-slot mapping avoiding tab, CR, LF and space is:
`01–08`, `0B–0C`, `0E–1D`. These are glyph indices for our renderer, not an
interchange encoding for ordinary text files.

## Local verification

The disposable MAME CPU probe in `.research-work/neo-token-audit/` (workspace
root) executed 95 assertions: all 31 low bytes through the native forward
scanner, B0–BF through the scanner, each token through raw/plain TextScanRead,
and each token through the validator. `run.py`, generated `probe.lua`,
`results.json`, `mame.log`, `summary.log`, and `ghidra.log` preserve the probe
and evidence. All assertions passed. This verifies CPU/RAM behaviour; no
screenshot interpretation was used.

## Region flags and output consumers

The [consumer audit](token-semantics.md) traces high B1/B2 bits, vendor matches,
USB/PS2/IrDA output, clipboard conversion and native printing. Bits 10/20/40/80
are preserved but have no identified semantic consumer in the inspected Neo
3.21 paths. All opaque record types are omitted by plain export and the tested
native printer callback; raw reads retain them.
