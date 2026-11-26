# Useful font-role matrix

[Complete image card (archived)](../../../font-archive/README.md#useful-pages-after-extraction) and [row gallery (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Reproduce from the workspace:

```
python3 betawise/research/bible-reader/font-specimens/useful_matrix.py
```

This is a curated visual shortlist, not an exhaustive availability table and
not a settled shipping selection. It covers serif, sans, book (generous serif),
mono source designs and fixed-column Terminal roles at 2–11 lines. Empty cells
mean no qualifying useful candidate was selected. They do not prove that no
font can exist at that size. No new face or synthetic weight is generated.

Every sample is the literal `AaBbCcDdEeFfGg` from source bitmaps at the same
2× nearest-neighbour enlargement. Proportional reading families show actual
R/B/I/BI glyphs; oblique counts as I. Existing vendor/community regular-only
fonts remain labelled references, to reveal whether styles add a useful
alternative. Terminal's role has no weight/oblique requirement. Fixed/ttyp0
are included there, independent of their missing combined bold-italic faces.

Imported candidates use the preceding checked 218-printable-character Western
repertoire. This is not certification of the full Neo device/control mapping.
Existing NeoFonts use their native byte tables. Vendor specimens are verified
against original applet bytes by the maintained family-role extraction.

Adobe 2–5-line selections use the native-ASCII/local-extended-repair generator.
Six-line Helvetica and Courier use the later aligned 8px alternatives without
staggered baselines. Times six/seven-line samples use the existing exports.
Dagger labels identify the extended-repair policy; ASCII is not rescaled.
No whole-face scaling is used. Neo cell bearing normalization can increase
advances: the Mono column denotes a monospaced source design, whereas Terminal
preserves fixed ASCII columns. Italic overhang normalization remains a separate
implementation concern, not a demonstrated source-font deficiency.

Lucida Sans/Bright are secondary visual alternatives, with native bold shown
so their regular stroke thinness at low density can be judged. Small Lucida
regulars may be too light for the Neo; larger strikes should be assessed
individually. Lucida notice/trademark review remains outstanding before
redistribution. Fixed is public domain per BDF; ttyp0 has its own permissive
licence and modified-font naming conditions. Existing community resources do
not acquire a new redistribution licence through this research.

Atto/Femto appear below the table as excluded references because of the known
C3 (Ã) block substitution. Atto's 11th line also clips some final-row ink.
Their exclusion leaves nine–eleven-line Sans cells blank. BetaWise Terminal
Small/Tiny remain nine/ten-line fixed-column choices. The eleven-line row is
intentionally empty. This is not a claim that emphasis is useful at that size.

The matrix is a source-font research diagram. No Neo LCD screenshot, external
vision inference or emulator session is used as a validation oracle. Geometry,
coverage and exact pixel-normalization assertions run during generation;
visual usefulness remains a user-review/design judgment.
