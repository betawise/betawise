# Native editor API usage follow-up

Current costs: [application-only ROM and maintenance metrics](reader-costs.md),
with compact native superscript fonts.

See the [unified native streaming comparison](native-streaming.md) for the new
moving-window/on-demand/background variants and ROM/A5 measurements.

Measured 2026-11-23 after the [complete read-through comparison](readthrough.md).
The earlier native numbers described our wrapper, not the firmware's best paging
path. The corrected native usage essentially ties LCD-roll streaming for a full
Psalm 119 traversal by pages.

Same NKJV resource, original system 6×16 font, visible superscripts, 314 wrapped
lines, emulator/firmware and phase timing method as the earlier report. Times
exclude keyboard waits and reading time, and include the final End command.

| Implementation | Initial display | Page traversal | Total |
|---|---:|---:|---:|
| Original native wrapper | 2.050 s | 7.081 s | 9.131 s |
| Native: skip preliminary Refresh | 1.414 s | 7.081 s | 8.495 s |
| Native: skip Refresh + native page command | 1.414 s | 2.709 s | **4.123 s** |
| LCD-roll streaming, previous measured run | 0.044 s | 4.033 s | **4.077 s** |

All three native traversal runs passed 83 independent source/font/bitmap/caret/
viewport checks each, including the same 79 page commands and final source EOF.
A separate KJV profiling run passed seven further checks, including a fresh jump
to Psalm 119:176, full-chapter pure decoding and exact search. Those artifacts
are in `.research-work/bible-compression/native-direct-kjv-jumps-v2`.
The faster native command reaches the same expected caret and viewport as our
four ordinary Down calls, including the last partial movement.

## What was unnecessary

We initialize the editor against an empty file, install all four font faces
(including the private superscript face), then append the generated chapter.
We previously called TextEditorRefresh and then TextEditorSetScanPosition through
move_to. The latter already performs native editable layout.

Refresh is a file reopen/reconciliation operation; the ROM can check, normalize,
lay out or reinitialize the descriptor. It is not simply a screen refresh. In
this particular generated, known-valid file, bypassing the preliminary Refresh
and retaining SetScanPosition saves **636 ms** and preserves the verified result.
Pure decompression remains about 641 ms; formatted decode/file filling about
854 ms. The native open still decodes and stores the entire chapter, whereas
streaming initially decodes only enough to populate the screen.

The opposite experiment, keeping Refresh but omitting SetScanPosition on verse
1, failed the first exact bitmap assertion: the initial screen was blank. That
variant is not an accepted optimization.

## The old wrong-glyph flash

It is no longer in the measured load path: the superscript face is installed
while the file is empty, before any chapter text can be drawn.
A fresh baseline run installed LCD write taps after firmware startup mapping and
measured these deltas for the Psalm load:

| Phase | LCD data writes |
|---|---:|
| File/editor/font setup | 4 |
| Decode and append file | 0 |
| TextEditorRefresh | **0** |
| Final positioning/clear/draw | **4,496** |

Thus the current native load is not painting ordinary placeholder characters and
then repainting superscripts. The extra cost is file/editor reconciliation,
followed by a separate necessary final positioning/draw. The final operation
includes our explicit ClearScreen, so its bus count includes clearing as well
as text/caret rendering.

## Native paging

Original Neo 3.21 TextEditorHandleMessage (`0x42882c`) dispatches
KEY_MOD_CMD|KEY_DOWN to `0x42c6fa` and the corresponding Up command to `0x42c41e`.
The Down helper iterates native line movement internally until the viewport's
pixel height is traversed. It remains inside one editor message, rather than
repeating the entire public key handler four times. Replacing our Space wrapper
with one such message cuts page traversal processing from 7.081 to 2.709 seconds.
This is original firmware functionality, not a patched ROM or injected layout.

The earlier steady one-line difference was modest: roughly 22 ms native versus
19 ms LCD-roll streaming. Streaming's earlier 6.00-versus-9.12-second full-line
advantage also included roughly two seconds of native startup and the final End
cost. The much larger page gap was largely our choice of API usage.

## Scope and reproduction

The shortcuts are optional comparison builds, not a change to the normal demo:

```sh
python3 betawise/tests/mame/asneo/check-bible-reader.py --version NKJV --profile --system-font --experiment huffman-prune --native-open-test direct --native-page-test --readthrough page --output OUTPUT
```

`NATIVE_OPEN_TEST=1` skips the preliminary Refresh; `NATIVE_PAGE_TEST=1` uses
native Command+Up/Down from Space. Defaults remain zero. Test mode 2 deliberately
retains the failed Refresh-only experiment for reproduction.
The known-valid generated file is important: this does not establish that a
general editor may omit reconciliation after arbitrary external file mutation.
Other fonts, selections, edit operations and applet resume with the new shortcuts
need broader acceptance before making them the default native-reader policy.

The profile fixture's A/B/C shortcuts also needed a guard against intercepting
letters while a reference/search prompt is active. This affects profiling builds
only; the ordinary demo has no such shortcuts.

[JSON](native-overhead-results.json) includes stage timing, valid baseline LCD
counters, traversal totals and evidence paths. Older trial taps installed before
startup remapping stopped receiving writes and are not used for bus counts.
Failed trials remain preserved alongside successful evidence. Sessions use
private disposable storage and exact local bitmap/cursor/controller assertions;
no screenshot inference is used. These CPU service measurements do not measure
physical energy or battery life.
