# Region flags and opaque records: consumer audit

Investigated against original Neo 3.21 ROM and the 56-image applet inventory
on 2026-11-25. Eleven `NeoFonts/` entries are community fonts and were excluded
from vendor-use conclusions; 45 entries are vendor images, including duplicate
releases and font providers. This is not a claim about every applet ever released.

## B1/B2 flags

`B1 mask B1` ORs mask into the byte of region state; `B2 mask B2` clears it.
Reverse traversal applies the inverse operations. All eight bits are retained.

| Mask | Confirmed consumer |
|---|---|
| 01 | Hidden: renderer skips content; scanner freezes x/y; plain export can omit the region |
| 02 | Protected: edit/delete guards and optional scan filtering |
| 04 | Font selection bit 0: Bold descriptor |
| 08 | Font selection bit 1: Italic descriptor; 0C selects BoldItalic |
| 10 | Carried/preserved, no semantic consumer identified |
| 20 | Carried/preserved, no semantic consumer identified |
| 40 | Carried/preserved, no semantic consumer identified |
| 80 | Carried/preserved, no semantic consumer identified |

There is no high-bit rendering mode, negative advance, underline, superscript,
strikethrough or invisible-measured-text mode in the traced native painter,
layout, scanner or output converter. This is a bounded negative result, not an
assertion that a third-party applet cannot interpret its own flag bits.

Evidence:

* Forward/reverse scanners `42C120`/`42C2A4` carry the full byte. Only bit 01
  suppresses coordinate writes. Font selector `42E62E` uses `(flags & 0C) >> 2`.
* Repaint `42A0F8` uses bit 01 and the selected descriptor, not the high bits.
* Reflow `42B5D0` preserves and normalizes generic masks, merges redundant
  set/clear records, and handles hidden content; it does not interpret high bits.
* Clipboard copy `42D7FE`, cut `42D9A6` and paste `42DD3E` transfer/reconcile
  whole flag bytes. This explains generic high-bit preservation without assigning
  meanings to them. Protected guards test bit 02.
* Plain TextScanRead `4291BE` filters only requested hidden/protected bits,
  and drops the flag records themselves. Block converter `42E81E` strips records
  and suppresses hidden content, with no high-bit special case.

### Private-font copying

Native Copy (`42D7FE`) transfers stored text bytes and the necessary flag
boundaries, not the glyphs selected by the font provider. Neither this path nor
plain conversion (`42E81E`) calls a font-specific decode callback. A private
font's mapping therefore cannot itself change copied text.

For our viewer, retain original lowercase Neo-US text and apply small-cap
encoding only while drawing. Copy then retains meaningful underlying text.
If private glyph bytes are stored instead, an owning app can handle Copy before
`TextEditorHandleMessage`, or replace the clipboard afterward with
`ClipboardSet`. Decode only private spans while walking editor tokens: body
bytes and opaque record payloads share byte values with the private charset.
AlphaWord requires an additional interception mechanism to do the same; merely
installing a font provider cannot alter its Copy behaviour.

Do not confuse region flags in editor+1C/scan+0C with editor configuration flags
at +0C/+0D. Those separate fields do have consumers of bit 10 and other bits.
Keyboard modifier words and transport flags are separate again.

## B3 through BF

| Byte(s) | Engine meaning | Additional payload interpretation found? |
|---|---|---|
| B3, B4, B7 | `marker payload marker`, total 3 bytes | No |
| B5, B6, BC, BD | Ordinary glyph bytes | Not opaque records |
| B8 | `marker length payload… length marker` | No |
| B9, BA, BB, BE, BF | Same variable framing | No |

B8 has its own classification (13), while B9/BA/BB/BE/BF share classification
14. The inspected consumers treat both classes identically: forward length
from byte 1, reverse length from the penultimate byte. The length is the whole
record, 4–255 bytes. A separate class is not proof of a distinct known payload.

These records are not comments that the ROM parses for layout or external
links. The validator checks framing. Scanners skip the payload as one unit;
repaint and layout give it no ink or advance; statistics skip its contents;
plain export discards it. Raw reads retain the record, so an application can
transport or preserve metadata without the engine understanding its payload.
No inspected producer assigned B3/B4/B7 or the variable records a payload schema.
The separate A8…9D form envelope is interpreted by the form machinery.

## USB, printing and other output

| Path | Trace/result |
|---|---|
| USB keyboard Send | AlphaWord forwards 30007/30008 to native transfer handler `4285CE`; it calls `429F14`, then TextScanRead with plain=1, skip_hidden=1, skip_protected=0 |
| Native printing | 6000D dispatches at `4286A6`, then `4287CE` calls `429F14`; phase 7 uses the same plain scan and reply 4 with the output chunk |
| AlphaWord USB direct file output | Applet callback `8844`, 40006 branch, calls A2CC with plain=1 and skip_hidden=1; subsequent character conversion does not receive opaque records |
| AlphaWord PS/2 file output | Callback `8210` uses the same plain scan before its character map |
| AlphaWord IrDA file output | Callback `8A66` also uses plain scan before character translation |
| Generic block/plain conversion | `42E81E`, called by clipboard mode 3 and file conversion helper `43A0AE`, strips records and hidden content |
| Raw file/scan access | Can retain bytes and records; no universal stripping claim for arbitrary binary Manager/app protocols |

The USB/PS2/IrDA AlphaWord calls at applet syscall stub `12ED8` resolve to
A2CC/TextScanRead in the original image, rather than relying on a guessed name.
The printer path was executed in the ROM with genuine 6000D requests, using
an initialized phase-7 transfer descriptor and an explicit chunk limit.
No physical printer, USB cable or IrDA peer was exercised. This establishes the
bytes supplied by the applet/native callback, not end-to-end transport behaviour.

## Vendor uses: confirmed matches versus false positives

The inventoried images were scanned for complete B1/B2 byte patterns and
candidate MOVE.B/CMP.B immediate constants, and reviewed alongside resolved
text-syscall callers. Raw matches alone are insufficient: dictionary compression,
font bitmaps and code jump tables contain every possible byte.

Confirmed examples (offsets are in the original applet image, including header):

| Image/site | Actual use |
|---|---|
| Neo AlphaWord `82A0` | BB terminates incoming PS/2 file payload in its protocol callback; not a framed text record |
| Neo AlphaWord `865C`/`8668` | BC/BD protocol command/handshake comparisons |
| Neo AlphaWord `8AE2`/`8BDE` | BB/BC in the IrDA transport callback |
| Neo AlphaWord `9708`/`979A` | A1–BF range test plus 8F: reserved input bytes are wrapped as B0-literal-B0, not interpreted as records |
| AS3000 AlphaWord `2662`…`26BE` | B0 literal framing in its input path |
| AS3000 Control Panel `301E` and later sites | BF is an AND mask for hardware register FFFFF421: clear bit 40 |
| Neo Responder `39B0` / Wireless File Transfer `4E1E` | BF masks a character during multibyte text encoding, not a record marker |
| CoWriter raw `A793` B2-01-B2 match | Bytes of a switch jump table, not text |
| SpellCheck Small raw `5D34` B2 comparison candidate | Encoded dictionary/table material, not validated executable token handling |

I found **no confirmed vendor producer/consumer of high region bits 10–80**, and
**no confirmed vendor payload meaning for B3/B4/B7/B8/B9/BA/BB/BE/BF**. Generic
record preservation does not establish what any original designer intended them
for. The inventory is candidate coverage, not a proof that computed markers or
compressed resources in every applet have been exhaustively decoded.

## Reproduce and retained evidence

From the repository root:

```
python3 research/syscalls/text/probe-token-semantics.py /tmp/neo-token-semantics
python3 research/syscalls/text/inventory-token-candidates.py /tmp/vendor-token-candidates.json
python3 research/syscalls/text/find-vendor-calls.py
```

The CPU probe passed **202 assertions in 92 native calls**: raw/plain conversion,
block conversion, real printer polls, and high-bit forward/reverse set/clear.
Each opaque type was tested individually. Only CPU/RAM was evaluated; no
screenshots or model inference were used, and flash/RAM were disposable.
An initial printer fixture omitted the per-transfer chunk limit and returned
an empty chunk; the corrected fixture follows the native phase initialization.
That initial failure is retained in the workspace research output and is not a
ROM-behaviour finding.

[Evidence folder](token-semantics-evidence/) contains exact results, execution
log, candidate inventory, vendor text-call inventory, transfer disassembly and
instruction/decompilation traces. `InspectTokenPaths.java` locates containing
functions for explicit instruction sites; confirm its inferred entry against
the actual instruction listing. `InspectTokenConsumers.java` supplements the
search on already-disassembled functions and is not a completeness oracle.
All ROM addresses and frame meanings here are scoped to Neo 3.21 unless a
vendor AS3000 example is explicitly named.
