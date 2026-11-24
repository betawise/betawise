# Interactive font dialog demo (Neo System 3.21)

## Status: INCOMPLETE — known interactive problems

The user reported on 2026-11-23 that the demo still does not work correctly.
The demo is an experimental reproduction, not an accepted working example.
The controls below describe intended behavior; they are not a claim that all
controls work correctly. Passing targeted entry/state checks did not establish
correct end-to-end interaction. The remaining failure has not been diagnosed.
See the [research status](../README.md) before relying on these examples.

`FontDialogDemo.c` builds a regular Betawise SmartApplet (`0xA1F2`). It provides
an on-device selector for all sixteen supported font-dialog layouts and calls
the original firmware for dialog drawing, focus, input and selection. Source,
build rules, launcher and local checks live together in this research folder.

## Run locally

From the workspace root:

```bash
python3 betawise/research/syscalls/dialog/demo/run.py
```

The launcher builds the library and applet, stages original Neo 3.21 firmware,
AlphaWord Plus and the demo in a **new disposable session**, and starts the
existing `mame/neodiag` in a window. It does not inject keystrokes or load a saved
user session. The session path and complete MAME command are printed.

On first boot, answer **Y** to initialize, then **Enter** at the following
prompt. Press **F9** (SmartApplets), select **Font Dialog Demo**, and press
**Enter**. These are ordinary keys you press yourself.

Within the applet:

| Key | Action |
| --- | --- |
| Up / Down in selector | Choose layout, including entries below the visible list |
| Enter in selector | Open the highlighted layout |
| Escape in a layout | Return to the selector |
| Tab in a layout | Ask the native firmware to advance focus |
| Arrow keys in a layout | Forward native dialog navigation |
| A / B / C in a letter-choice field | Change the choice |
| Typing / Backspace in a text field | Edit text after its protected prompt |
| Ctrl+M | Toggle body selection highlighting in body panes |
| F9 | Return to the system SmartApplets menu |

If Tab opens MAME's configuration UI, press **Scroll Lock** to switch keyboard
UI mode so Tab reaches the emulated machine. The keyboard mappings are those
of the existing Neo driver. MAME's window controls close the emulator.

To prepare everything without opening a window:

```bash
python3 betawise/research/syscalls/dialog/demo/run.py --prepare-only
```

Copy the printed MAME command to start that prepared session. For a particular
session directory, add `--session /tmp/my-neo-dialog-demo`; it must not already
exist. `--mame` and `--firmware` override the local emulator and firmware paths.
No emulator rebuild is required when `mame/neodiag` already exists. The build
requires the workspace's `m68k-linux-gnu-*` toolchain and Python 3.

Build just the applet:

```bash
make -C betawise/os3k
make -C betawise/research/syscalls/dialog/demo
```

## What the examples establish

Body highlighting starts enabled where a body pane exists; Ctrl+M toggles it.
Layouts 7/8/9/18 use a specialized renderer whose numeric/multiple-answer
configuration is not established by the public prompt API. Those inputs remain
unconfigured and disabled; their title/body layout and selection can still be
explored. The demo does not present those specialized inputs as ordinary text
fields. Layout 12 shows letter choice, layout 13 has no default input, and
layout 15 shows editable text alongside a selected body.

The native font-dialog character renderer at `43264E` explicitly assigns its
small-font descriptor (`7E32`) for normal characters, selecting another built-in
face for certain special characters. The public dialog interface has no font
argument or per-region font setter. Changing the normal console/editor font
is not a way to resize this UI.

The first screenshot gallery supplied `Name:` to every input kind. For renderer
kind 5, its protected-prefix length became the bit mask `6`, which the choice
renderer interpreted as B and C. Those were actual ROM-drawn answer bubbles,
but the demo configuration was wrong. The specialized kind-5 state can also
represent other answer/numeric modes; its complete public initialization
contract is unresolved. This interactive demo leaves that input unconfigured
and disabled in layouts 7/8/9/18; their body/list regions remain interactive.
It does not invent a public configuration API or write private editor masks.

Layout 12 uses kind 4: `@A`, `@B`, `@C` mark letter choices and `#B` establishes
the initial selection. It is a choice field, not arbitrary text entry. Layout
13 defaults to title/body only. Layout 15 demonstrates editable text together
with a selectable body. Body highlighting is explicitly enabled by this demo
using `FONT_DIALOG_SELECT_ITEMS`; Ctrl+M lets you compare it with that property
disabled. This does not imply every template is a menu by default. Tab and
navigation still follow the ROM's layout-specific focus/default-input rules.

In layouts 5/6, region 0's first body rectangle spans y=10..20, while the next
input rectangle begins at y=18. Filling all regions with generic body text
therefore drew text underneath a later input clear. The corrected example
keeps that header body empty and supplies First/Last prompts in the actual
input regions. This was overlapping sample content, not lost screenshot pixels.

Each borrowed body has persistent, separate storage. Dialogs are destroyed on
focus loss and before replacement. Activation explicitly reselects region 0
when a pool address is reused; the ROM otherwise treats the same address as
already active.

## Local verification

```bash
python3 betawise/research/syscalls/dialog/demo/check-demo.py
```

This check cold-boots original firmware in disposable storage, handles startup
prompts through native matrix keys, then exercises the actual built applet's
entry/CRT in scratch RAM with controlled messages. It checks all sixteen
layouts, selector scrolling, C selection in layout 12, typing and backspace in
layout 15, Tab followed by selector restoration, menu toggles and dialog-pool
release/reacquisition. The interactive launcher does **not** run this harness.

The check preserves manifest hashes, Lua, logs, results and a stable three-sample
LCD RAM record. These are state/lifecycle checks, not font-glyph or full-screen
rendering assertions; no model vision is used. It does not claim physical-device
qualification or a complete keyboard/navigation audit of every template.

Revised screenshots: [contact sheet](../screenshots/selected/font-dialogs.png).
The original captures remain intact for comparison.

Generated evidence logs, captures and build hashes are not archived. Rebuild
and rerun into fresh disposable output if continuing this incomplete research;
no raw transcript makes the interactive behavior accepted.
