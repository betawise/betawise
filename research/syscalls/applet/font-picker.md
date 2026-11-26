# Shared Neo font picker

The SDK's [font picker](../../../os3k/os3k_font_picker.h), included through
`os3k.h`, draws a six-row proportional list using the ROM 9px small font.
It enumerates installed providers on demand rather than retaining a font list.
Each applet owns its own picker state through its linked `libos3k` instance.

## Calling convention

Supply a callback that filters installed indices and copies a header name into
its 37-byte output buffer. For ordinary enabled font providers:

```c
static bool ReadFontName(unsigned index, char name[37]) {
    return AppletIsFont(index) && !AppletGetDisableMask(index) &&
        AppletGetName(index, name);
}
```

Call `FontPickerBegin(ReadFontName, current)` and `FontPickerOpen()` when opening
the picker. Open returns false if its required proportional font is unavailable.
The caller owns event routing and closes the picker on acceptance, cancellation
or loss of focus:

| Event | SDK operation |
|---|---|
| Up/Down | `FontPickerMove(-1, 0)` / `FontPickerMove(1, 0)` |
| Left/Right | `FontPickerMove(0, -1)` / `FontPickerMove(0, 1)` |
| Home/End | `FontPickerEdge(false)` / `FontPickerEdge(true)` |
| Navigation completed | `FontPickerDraw()` |
| Screen invalidated | `FontPickerRedraw()` |
| Enter | Read `FontPickerChoice()`, then `FontPickerClose()` |
| Escape or loss of focus | `FontPickerClose()` without applying the choice |

Opening or browsing never changes the global font selection or applies fonts
to an editor. The caller handles screen/cursor setup and restores its own screen
after closing. The picker has one active instance per applet and is not reentrant.

## Selection and presentation

Choice handles are transient: 1–31 are installed applet indices, zero is the
built-in 6×16 font, and `FONT_PICKER_SYSTEM_SMALL` (32) is the built-in 9px font.
Handle 32 is not an installed applet index and must not be sent to applet APIs.
Persist a selection kind and provider ID using `AppletGetId()`, then resolve
installed providers through `AppletFindById()` when using them again. Check the
font flag and disable mask after resolution; an erased provider can free its
old index for a different applet.

Names come from provider headers. Recognized size suffixes group variants of
the same family. Changing family preserves the desired line count, choosing the
closest available size and preferring larger letters on a tie. Only the selected
row shows size/resolution details and available-direction triangles.

BetaWise branding is preserved. The five original vendor IDs
AF00/AF75/AF02/AF73/AF03 form the size-only Neo Font family; a shared packaging
prefix alone does not identify a vendor font. Community faces remain separate
named families. The built-in System family offers 4-line and 7-line choices.
The unavailable 11px dialog font is not offered through a private ROM address.

## Validation

```sh
python3 tests/fonts/test_font_picker.py
python3 tests/qemu/applet-flags.py
python3 research/syscalls/applet/audit-font-access.py --mame
```

The host test exercises the production search/grouping code, closest-size
navigation, removal, bounds and community/vendor distinctions. QEMU checks the
compiled metadata adapters, including poisoned failure pointers, full-length
names and narrow boolean results. The original-ROM probe validates secondary
register results in disposable MAME state. See the
[firmware audit](font-access.md) for version scope and limitations.
