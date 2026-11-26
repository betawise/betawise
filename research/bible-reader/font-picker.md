# BibleWise font selection

BibleWise uses the SDK [shared proportional picker](../syscalls/applet/font-picker.md)
from `os3k.h`. It owns only event routing and application of the returned choice.
The picker has six proportional rows, family navigation, closest-line-count size
selection and size details only on the active row. There is no alternate native
or console picker build. F opens it; Ctrl/Cmd+F remains Find.

## Provider identity and fallback

Provider discovery uses the SDK font flag and disable mask. Names are bounded
header labels, with branding and size parsing handled by the SDK. BibleWise
retains provider IDs, re-resolving and validating current indices at focus/font
setup. A removed provider falls back safely rather than using a reused slot.

First run prefers five-line Book/Serif/Sans/Mono, then six-, four- and three-line
reading providers. With none installed it selects ROM 6×16, independently of the
user's global font. Explicit choices are retained. System 9px remains available
as a seven-line option; the 11px dialog font is not exposed through a fixed ROM
address. See the [font access audit](../syscalls/applet/font-access.md).

The old 40-column native-list workaround and name-based discovery investigation
are historical; they no longer describe the active picker. AlphaWord's picker
skips eleven header-prefix bytes. BetaWise fonts preserve those bytes while the
shared picker retains BetaWise branding in its own family labels.

## Glyphs and verse numbers

Private reading faces provide native smaller-strike digits where selected by the
[font recipe](../../fonts/README.md). Their fallbacks and BibleWise's in-app
fallback overlay share the TI-83/84 small numeral descriptor. H-top alignment is
computed during font generation or from one packed H glyph when configuring an
unrelated provider. No per-character glyph scan or bitmap rescaling is used.

The in-app overlay uses four immutable 88-byte ROM banks at offsets 0,1,2,4 and
no writable bitmap buffer. Offsets between banks round upwards on the screen
(3→2); deeper offsets clamp to 4. Descriptor height matches bodies up to 16px,
then uses a top-aligned 16px face for larger bodies. The fully minimal-height
trial left six cursor pixels in System 9px and was rejected by exact LCD checks.
Retaining body height through 16px fixes that without pixel erasure or changes
to the capture oracle. Vendor 21/32px fonts verify mixed-height behavior.

## Reproduction

From the repository root:

```sh
python3 tests/mame/asneo/run-biblewise.py
python3 tests/mame/asneo/check-biblewise.py --case family-picker --output tests/biblewise/build/family-picker
python3 tests/mame/asneo/check-biblewise.py --case default-font --vendor-font vlarge --output tests/biblewise/build/no-inheritance
python3 tests/biblewise/test_superscript_alignment.py
```

The 26-checkpoint picker suite covers family/size navigation, fixed arrows,
selection, cancellation, System 9px and an AlphaWord focus round trip. Tests use
exact source-derived glyph/LCD comparisons, independent cursor assertions and
three identical cursor-hidden controller samples, restoring cursor state through
firmware calls. Historical snapshots stay under ignored build directories.
The [usage suite](../../tests/mame/asneo/check-biblewise-usage.py) covers ordinary
reading/navigation/search combinations. Generated reports are not checked in.
