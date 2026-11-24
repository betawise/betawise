# Why native insertion slows down

Investigated 2026-11-23 in original Neo 3.21 ROM. SHA-256 of
`Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos`:
`32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0`.
Addresses below are specific to this image, not portable SDK entry points.

## TextScanInsert really does reflow the file

The syscall entry at **0x4297BA** checks editable/current-file state and calls
**0x42E164**. That helper has three distinct operations:

| Operation | Instruction evidence | Scaling |
|---|---|---|
| Validate encoded input tokens, or count plain-text escapes | 0x42E1AA..0x42E1C8 calls token parser 0x42B4F8 on the input buffer; the end pointer is input + insertion length | New chunk |
| Grow file and open a hole | 0x42E24A calls 0x42BF58; that calls file-length setter 0x43A640 and memmove 0x436B46 at 0x42BFE2 | Suffix after insertion, plus possible filesystem allocation/relocation |
| Copy input | 0x42E2B4..0x42E2C0 calls memcpy 0x436678 for encoded input | New chunk |
| Reflow | **0x42E2C4 pushes 1**, 0x42E2C8 pushes editor, **0x42E2CA calls 0x42B5D0** | Whole resident file |

In 0x42BF58, the suffix-copy length is `new_length - insertion_offset - inserted_length`,
equivalently `old_length - insertion_offset`. At EOF this is zero. File growth
can still move storage elsewhere; this is not a claim that all allocation is
free. But shifting the old prefix is not what that memmove requests.

The final reflow call is unconditional after a successful insert. There is no
public `TextScanInsert` argument to suppress it. Encoded versus plain mode only
changes input conversion/validation, not this final call.

## The two layout modes

**0x42B5D0 is a layout/normalization routine, not just a validator or painter.**
It obtains glyph widths through 0x42BECE, tracks horizontal/vertical positions,
and rewrites space/tab/hyphen cache bytes. It can also insert/remove hard-wrap
markers and normalize redundant formatting tokens. Relevant bytes include:

* 0x81: cached wrapping space (plain equivalent space).
* 0x8D: cached wrapping tab.
* 0xAD: cached wrapping hyphen (plain equivalent hyphen).
* 0x8F: inserted hard-wrap marker.

At **0x42B65E..0x42B662**, its second argument chooses the path:

* **1:** start from file byte zero with a 0xFFFFFFFF vertical budget
  (initialized at 0x42B5FC..0x42B5FE). The main loop at
  0x42BDBC..0x42BDC6 continues to EOF. This is what insertion calls.
* **0:** start from `editor.viewport_offset`, restoring its saved formatting and
  line state, with a budget based on layout height plus font height
  (0x42B666..0x42B6A4). This is the incremental path used by ordinary editing.

The second path is **not an unconditional stop after N pixels**. Reflow must
propagate until an old wrap boundary is stable. For spaces, see
**0x42B826..0x42B83A**: when the budget is exhausted but the new break was not
already 0x81, the routine extends its budget. Similar logic handles tabs and
hyphens. Hard paragraph boundaries can stop propagation, but an uncached long
paragraph can run to EOF. Our flowing Bible chapter uses spaces between verses,
so Psalm 119 is one long paragraph.

This explains both the measured 12-to-235 ms insertion slope and why ordinary
scrolling through an already wrapped chapter is cheap.

## Does opening or positioning lay out everything?

Usually yes on this editable-editor path:

* Normal `TextEditorInit` at 0x427E04 calls **0x42AFBC**, which traverses and
  repairs/normalizes the existing encoded file and establishes its gap/state.
  On the editable path, 0x42B4E8 then invokes full layout with argument 1.
* `TextEditorSetScanPosition` at 0x429818 calls full layout at **0x429888**.
  Its Boolean controls subsequent selection drawing; **false does not skip
  layout**.
* Font changes use the full layout path as well.
* The native repaint notification (message 0x1B) with parameter **0xFE** calls
  full layout before drawing. Parameter zero goes directly to drawing without
  that reflow. This is observed firmware behavior, not a general published SDK
  guarantee.

The app already initializes and installs fonts while the file is empty, avoiding
repeated full-file initialization. But its later SetScanPosition and insertion
calls were still invoking full layout. `TEXT_EDITOR_DEFER_LAYOUT` can skip the
initial preparation; it does not turn those later calls into lazy operations.
A deferred descriptor still needs valid gap, scan and font state before use.

## Can we avoid it?

**For controlled, append-only reader content, yes experimentally.** New optional
`NATIVE_STREAM=5` (`BibleReader-NativeViewport`) does this:

1. Initialize the native editor empty; decode a page-sized prefix.
2. Raw-append further known-valid encoded text rather than use TextScanInsert.
3. Copy the 94-byte editor descriptor, place the temporary caret at its viewport,
   and invoke **private ROM helper 0x42B5D0 with argument 0** on that descriptor.
   A two-screen budget prepares native wrap markers ahead without changing the
   live caret/viewport. Prepare again before navigation, even if no refill is
   necessary; bytes per page vary with fonts.
4. For first display at chapter start, use draw-only repaint parameter zero.
   Jumps and other existing operations can still request full layout.

Raw append **without** cache preparation was tested and rejected: source caret
rows and exact bitmaps diverged, despite the Lua harness completing key delivery.
Native movement relies on cached wrap markers ahead of the caret.

This is a **research-only Neo 3.21 coupling**, not a new stable SDK API. Its
minimal instruction signature check does not establish compatibility with other
ROMs. The helper may change encoded length for long unbreakable words or token
normalization; the prototype rejects a length change because copied descriptor
positions would otherwise become stale. A complete adapter must handle those
mutations and global native state correctly.

**Known failure:** the final cache-before-each-movement revision stalls at the
ninth selection-page extension in the long-selection fixture. An earlier
revision passed all 49 feature states; the current one does not. A bounded
navigation-acknowledgement experiment also failed, so this is not accepted as
merely a short synthetic key pulse. Those failed runs are retained. The
acknowledgement-only harness modification was removed. Do not promote this
prototype to the default reader or claim full native feature parity.

## MAME measurements

NKJV Psalm 119, real 6x16 system font, numbered text, same Huffman/index assets
and current dynamic-clock MAME. Times are service time including lookahead work,
not reading/key gaps, idle scheduling delays, captures, or physical energy.

| Reader | First screen | Whole chapter by page | Whole chapter by line |
|---|---:|---:|---:|
| Native full chapter, optimized | 1.414 s | 4.123 s | 8.487 s |
| Native TextScanInsert page lookahead | 0.350 s | 11.657 s | 16.157 s |
| Private viewport lookahead, final | 0.346 s | 5.155 s | 11.308 s |
| Custom LCD roll | 0.044 s | 4.077 s | 6.002 s |

The final private path spends 1.464 s idle work by page / 1.437 s by line, in
55 slices. Largest slice: **33.175 / 33.531 ms**, versus 266.683 / 268.057 ms
with TextScanInsert. All idle append/cache slices have **zero LCD data writes**.
First exploratory viewport versions measured 4.55 s by page, but lacked the
per-movement cache preparation needed by Extra Large fonts. They are not the
final speed quoted here.

Production costs: 23,744 application ROM bytes (**23.19 KiB**, excluding common
Bible resources), 3,546 A5 bytes, peak chapter file 14,860 bytes. The temporary
layout function's compiler stack record is **132 bytes**, bounded. No dynamic
library or shared framebuffer is introduced.

### Whole chapter decoded before first display

A separate `NATIVE_OPEN_TEST=3` experiment decodes all 14,348 encoded chapter
bytes, then attempts viewport-relative preparation and draw-only display. It
passes 8 exact initial-display/selection/EOF states, but **does not avoid the
cold full-paragraph reflow**: the first captured file already has all 313 wrap
markers, including one at byte 14,322. First display takes **1.473 s**, of which
0.252 s is the final layout/draw interval. This is not an improvement over the
optimized full-chapter reader. Streaming keeps that uncached suffix small;
merely selecting the incremental mode does not.

## Evidence and reproduction

All artifacts are under `.research-work/bible-compression/`:

* `native-insert-disassembly/ghidra.log`: instructions and decompilation from a
  read-only disposable copy of the ROM project. Conclusions above use the
  instructions, not Ghidra's guessed C parameter types.
* `native-viewport-page-final`: **83 passed** bitmap/source/cursor/file states.
* `native-viewport-line-final`: **317 passed** equivalent states.
* `native-viewport-xlarge-v3`: **17 passed** vendor Extra Large states.
* `native-viewport-full-initial`: **8 passed** full-file-first-display states.
* `native-viewport-production-final`: production ELF/map/source/stack/metrics.
* `native-viewport-features-final` and `native-viewport-features-ack`: rejected
  long-selection runs, raw failure state and logs retained.
* `native-viewport-features`: 49 passed states from an earlier revision, not
  evidence of final-revision parity.

The viewport prototype's tests use disposable flash/RAM, independently expected
bitmaps, cursor assertions before hiding, three identical LCD samples and
firmware cursor restoration. No model/vision oracle. Normal applet defaults and
the existing custom demo are preserved.

```sh
python3 betawise/tests/mame/asneo/check-bible-reader.py --version NKJV --native-stream viewport --system-font --profile --readthrough page --experiment huffman-prune --output OUTPUT
python3 betawise/research/bible-reader/profile-readthrough.py OUTPUT --output SUMMARY.json
python3 betawise/research/bible-reader/check-native-lookahead.py OUTPUT --viewport --output AUDIT.json
```

Use `--readthrough line` for line traversal. Cold whole-file first display:
`--native-open-test viewport-full --feed-end-smoke` instead of `--readthrough`.
The private helper is isolated in `NativeFeed.h`; SDK callers are unchanged.
