# Native applet message inventory

This investigation updates `Message_e` from local source and original Neo 3.21
ROM instructions. It is **static evidence**, not hardware or emulator acceptance.
No saved session or screen was used. Numeric names below are descriptive SDK
names, not recovered manufacturer enum spellings. The [dispatch audit](dispatch-audit.md) summarizes the USB message families.

## 0x1B: refresh, with a scalar reason

`0x1B` is not a subscription request, nor exclusively a font-change message.
The foreground event loop calls the applet entry point directly with it. No
registration call is needed in the traced path. `param` is a full scalar word;
it is not a font descriptor pointer or font number. The entry returns void,
with any reply written through its separate status pointer.

| Parameter | Evidence and meaning on Neo 3.21 |
|---|---|
| `0` | Ordinary refresh/redraw after firmware activity. At `417C1E`, `417CB6`, `417CC6`, and `417CEA`, the loop selects message `1B` and clears its parameter register. Idle reply 7 also requests this refresh (`417CAC–417CB8`). |
| `FC` | Font refresh. System-key handling sets its result byte to `FC` at `418742`, checks applet flag bit 7 at header offset `13`, and calls the font chooser `42284E`. The event loop converts this to message `1B`, parameter `000000FC`, at `417AEE–417AFE`. |
| `FE` | Native cursor-style setting refresh. `418588–4185C0` reads the applet setting before/after firmware UI and emits `FE` only when it differs. `417B00–417B0E` forwards it as parameter `000000FE`. The editor reads this setting into `TextEditor_t.cursor_style` at `+4C`. This is not another font slot. |

The dispatch at `417B1A–417B24` pushes status address, parameter, then message,
and invokes the foreground callback. The font reason is set **before** the
chooser runs; receiving it does not prove that a different font was selected.
It is a notification to reacquire state, not a commit acknowledgement.

The native editor handler (slot 176, `42882C`) compares the full message to
`1B` at `428886`. For parameter `FC`, `428896–4288C2` calls `422AF4` for
font indices 0, 1, 2, 3 and writes descriptor pointers to editor offsets
`4E/52/56/5A`. It recalculates vertical extent, reconciles writable-editor
layout with `42B5D0`, and clears the display. For `FE`, `42890C–42891E`
reads the native setting through `41C2E4` and stores it at `+4C`; writable
editors take the draw-selection path. All `1B` reasons then reach the common
editor refresh/draw tail (`4290E8`), subject to the initial valid-file checks.
Unknown reason values are not additional established protocols. No separate
`FD` or `FF` branch exists in this handler. Occurrences of those numbers as
string IDs, file IDs, or arguments to unrelated functions are not messages.

The form handler (slot 189, `42F200`) also recognizes `1B/FC`: it obtains font
index zero and updates `TextForm_t.font` at `+16` (`42F224–42F242`).

Bible Reader's existing `1B/FC` handler is consistent with this producer and
both native consumers. Its explicit `TextEditorHandleMessage(...,1B,FE,...)`
redraw calls exercise the cursor-style refresh path; they are not evidence that
`FE` means only “redraw.” Its chapter reload restores custom font overrides
that the native `FC` handler would otherwise replace.

`AppletSendMessage` adds bit 24 for ordinary codes, so sending `MSG_REFRESH`
through that service delivers `0100001B`, not the native `0000001B`. The native
editor compares the complete code: do not assume synthetic injection is
equivalent to a firmware refresh. There is no blanket masking change here.

## Other recovered/previously unnamed messages

| Added enum | Contract and source |
|---|---|
| `MSG_SETTINGS_READ = 1C` | Applet settings/resource read. ROM `411A00–411A0E` calls the applet with the native request at `0482`; `41C304–41C34C` queries type `0103`, ID `100F` using a stack request and examines the returned data pointer. |
| `MSG_SETTINGS_WRITE = 1D` | Corresponding settings/resource application. `411BEA–411C4C` parses records, dispatches them to the system or applet, and `41C394–41C3FE` constructs a `0103/100F` write request. These are not the foreground focus messages. |
| `MSG_FONT_GET_NAME = 01000001` | Existing NeoFontTerminal callback writes a borrowed name pointer through `param`. |
| `MSG_FONT_GET_NORMAL/BOLD/ITALIC/BOLD_ITALIC = 01000002..01000005` | Font-provider queries. `422BE4–422C64` calls `AppletSendMessage` with low codes 2–5 and addresses of four pointer cells; missing faces fall back to normal/normal/bold respectively. NeoFontTerminal implements all four. |
| `MSG_FONT_GET_HEIGHT = 01000006` | Stock Neo font providers initialize their descriptor and write its first (height) byte, zero-extended to a 32-bit scalar through `param`. The earlier pointer interpretation was wrong; NeoFontTerminal is corrected and tested. `MSG_FONT_INITIALIZE` remains a compatibility alias. |
| `MSG_TRANSFER_OPEN/CLOSE/CHAR = 60001/6000C/60020` | Already established full-code editor/form transfer cases, formerly only raw numbers in research and typed probes. See [text investigation](../text/README.md). Payload layout remains scoped to those workflows. |

The settings request is **not** `AppletResource_t`: the observed native request
has selection fields preceding type/id/length/data. No universal public struct
is introduced by this update. `AppletSendMessage` explicitly exempts exactly
`1C` and `1D` from adding the synthetic flag (`439CA0–439CB6`). Font enum
values above are full delivered callback values; low query codes also work
with that dispatcher. Do not strip bit 24 from a font callback and accidentally
confuse its name query with another low-code protocol.

The extended [dispatch audit](dispatch-audit.md) identifies `25` at `417C8C`
as the notification after a low-battery warning, traces `0E` and `26`, and maps
the additional transport and provider protocols. Literal `1E/1F` occurrences in the ROM also occur in UI/string
operations; they do not alone establish new top-level applet messages.

## Reproduce the evidence

From the workspace root:

```sh
python3 betawise/research/syscalls/applet/investigate-messages.py
```

This checks the original image SHA-256 against the maintained ROM inventory,
asserts twelve selected instruction byte sequences, and regenerates the scoped
[disassembly excerpts](messages-disassembly.txt) with GNU m68k objdump. Addresses
are absolute ROM addresses (image base `410000`), not applet-relative offsets.
The opcode assertions check evidence identity, not behavioral correctness.
Other firmware versions and every possible message/reason remain unqualified.
