# Courier inflection and local continuity trials

[Comparison gallery (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [five-line glyph-specific specimen (archived)](../../../font-archive/README.md#useful-pages-after-extraction),
[a/W source pixel grids (archived)](../../../font-archive/README.md#useful-pages-after-extraction), [every cut and pixel edit (archived)](../../../font-archive/README.md#useful-pages-after-extraction).

Reproduce from the workspace:

```
python3 betawise/research/bible-reader/font-specimens/courier_inflection.py
```

Three source-font designs are compared at 3/4/5/6 lines with the unchanged
12/11/8/6px cell widths: previous bottom-three step, requested bottom-four step,
and glyph-specific inflections with a few explicit middle-row corrections.
All samples use nearest-neighbour enlargement; native 264x65 source page assets
are also provided. No gray or dithering pixels are generated.

A uniform cut can shift a bowl junction or compound an existing W diagonal.
The glyph-specific draft evaluates baseline-relative cuts, preferring source
components/counters and retained neighbors across the transition. These graph
criteria are design heuristics, not automated evidence of readability. They
can prefer a weak visual slant, so a/W have explicit reviewed overrides.

## Explicit a/W cuts

| Lines | a I / BI | W I / BI |
|---|---|---|
| 3 | 5 / 5 | 4 / 3 |
| 4 | 4 / 4 | 2 / 4 |
| 5 | 4 / 4 | 3 / 3 |
| 6 | 3 / 3 | 3 / 3 |

The cut is the number of bottom body rows left aligned; descenders remain with
that lower band. Rows above shift one pixel right. At five lines, placing the
a transition just above the bowl bar avoids stepping across that junction.
W retains a different transition, with explicit corrections to its middle.
Western accented a variants inherit the same baseline-relative cut as a. Their
individual edge trims remain recorded for review.

## Explicit middle-row corrections

Coordinates are after the constant glyph placement into its fixed cell:

* Five-line I W: delete (1,-3), a leftward spur, and add (3,-3), joining the inner diagonal across the transition.
* Five-line BI W: delete (0,-3), the corresponding spur after its -1 bearing placement.
* Six-line I W: delete (0,-3) and add the middle bridge (2,-3).
* Six-line BI W: move (0,-3)->(1,-3), (2,-3)->(3,-3), (4,-3)->(5,-3),
  and (0,-2)->(1,-2); add (3,-2). This is a local hinted junction trial.

These are deliberate pixel edits, not a claim of losslessness. Original upright
base symbol repairs from reader-candidates are retained. Other edge trims from
fitting the cell are independently listed in report.json. The original combined
reader-candidates set remains unchanged; no choice here is silently promoted.

The a/W grid shows the original upright input, both uniform step variants and
the final glyph-specific candidate with the cut marked in red. It makes the
middle-row changes reviewable at actual source-pixel granularity.

## Outputs and checks

The glyph-specific set exports all four styles at four sizes (16 BDFs). The
bottom-four comparator exports I/BI at each size (8 BDFs). All 5,232 glyphs are
parsed back and checked for exact pixels and advances. Fixed widths and vertical
positions are checked. Graph heuristics do not certify font semantics, physical
LCD contrast, editor rendering, or human readability.

The exports have 218 printable Western native-byte slots, not invented fillers
for Neo device/control glyphs. Production mapping and editor acceptance remain
separate. These images are source-font research diagrams, not captured Neo LCD
screens, and no model inference is used as a Neo validation oracle. The
Adobe/DEC source notice is preserved in FONT-LICENSE.txt.
