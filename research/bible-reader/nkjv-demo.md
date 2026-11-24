# NKJV streaming demo with all vendor fonts

Historical measurements/design below. See the [current UI revision](reader-ui.md)
for the updated repainting renderer and demo.

Run from `/home/kirk/Projects/Alphasmart`:

```sh
bash .research-work/bible-compression/reader8-nkjv-demo/launch.sh
```

The launcher copies the tested ROM/configuration/NVRAM into fresh `/tmp` storage
before opening MAME. The retained evidence and existing user sessions are not
changed. Use Applets (host F9) to select **BibleReader-Stream-NKJV** if needed.
Ctrl+Alt+Cmd+F opens the native font picker. The demo finishes its test in Small.

Installed together: original Small (11 px), Medium (13), Large (16), VLarge (21)
and XLarge (32), plus the system 16 px font and terminal 8 px font. The five
vendor font applets occupy 35,332 bytes of shared ROM separately from the Bible
applet; their original bitmap/width tables are used directly. They are available
to other applets such as AlphaWord.

## Build and data

```sh
make -C betawise/applets/BibleReader READER=Streaming VERSION=NKJV
python3 betawise/tests/mame/asneo/check-bible-stream.py \
  --version NKJV --all-vendor-fonts --production --output /tmp/bible-nkjv-new
bash /tmp/bible-nkjv-new/launch.sh
```

Output: `BibleReader-Stream-NKJV.OS3KApp`, applet ID 0xA1B1. This is a
translation-specific streaming output; the default translation remains KJV.
The builder reuses the previously verified NKJV-specific trained codec and
builds the full packed exact chapter index and grammar summaries. It does not
apply KJV predictions to NKJV. No partial-index policy is used.

| NKJV component | Bytes |
| --- | ---: |
| Compressed text/dictionary/model | 1,040,674 |
| Full packed exact chapter index | 260,782 |
| Grammar-pruning summaries | 6,144 |
| Verse counts | 2,378 |
| Applet code, runtime, navigation, other resources | 22,704 |
| Complete Bible applet ROM | **1,332,682** |
| Complete applet static RAM | **3,816** |
| Private chapter/status files | **0** |

Static RAM includes the decoder, search engine, compressed line checkpoints,
selection, copy scratch, search history, UI state, diagnostics and runtime globals.
Firmware stack, native dialogs and the shared clipboard are additional; copying
a large selection intentionally allocates clipboard content. The figure is not
a whole-system peak-memory measurement.

The approximately 22.7 KB ROM overhead also includes Bible-specific decoder,
search, reference/citation and book-navigation code. It is not the footprint of
an extracted generic layout library. Streaming is the preferred Bible-reader
implementation after its initial-display and memory comparisons. For Markdown or
ordinary books, a shared layout/drawing/cursor layer can omit Bible-specific
services; its separate ROM/RAM cost remains to be measured when extracted.
A full software redraw remains a possible scrolling policy. This demo retains
the measured 64-row hardware roll and blank independent 65th COMS row.

## Deterministic acceptance

`reader8-nkjv-demo` under `.research-work/bible-compression/` passes 66 checks:
source-derived text, wrapping, superscripts, selection/cursor geometry, citation
copying with NKJV labels, word/chapter movement, reference and exact search,
search history, font picker, applet return, and scrolling in all installed fonts.
Each vendor selection is identified by exact bitmap bytes in its retained original
font image, rather than relying only on height (system and vendor Large are both
16 pixels). All 65 panel rows are checked; the fixed COMS row stays blank.
The real cursor-hide call is observed before three identical full LCD RAM/flag
samples, with native registers and scratch preserved/restored. No model vision
or screenshot oracle is used.

`reader8-nkjv-host` independently reconstructs all 1,189 chapters and 4,025,833
ASCII source bytes exactly, including reverse chapter order. The 25 offline
oracle unit tests pass. The KJV production binary remains byte-identical to its
previously passing 51-check release; the change to translation-specific streaming
names does not change that executable.

In the new NKJV production session, jumping to Matthew 2:1 takes 45 ms and
scrolling one new line takes 19 ms with the original system 6×16 font. These are
in-guest operation timers excluding reference typing and emulator boot. They are
not physical-device power measurements. Raw records, expected source/font images,
assertions, original binaries, manifests, logs and the disposable session are retained.
