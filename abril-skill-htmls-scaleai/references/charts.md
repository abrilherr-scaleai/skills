# Charts

Applies to any chart in this style. Written for hand-rolled inline SVG, which is
what these documents use, but the rules hold in any library.

## Colour

**Bind a hue to the entity, never to its rank.** The same series keeps its colour in
every chart, every table row and every group border, and across sibling documents.
Sorting by score or filtering must not repaint the survivors.

The palette, in fixed slot order:

| Slot | Hue | Hex | Contrast on `#FAFAFA` |
|---|---|---|---|
| 0 | blue | `#2a78d6` | 4.23:1 |
| 1 | violet | `#4a3aa7` | 8.20:1 |
| 2 | green | `#008300` | 4.74:1 |
| 3 | aqua | `#1baf7a` | 2.70:1 |
| 4 | yellow | `#eda100` | 2.07:1 |
| 5 | red | `#e34948` | |
| 6 | orange | `#eb6834` | |
| 7 | magenta | `#e87ba4` | |

Assign entities to slots in a stable, documented order. A new entity takes the
lowest free slot by name, which is deterministic across rebuilds.

**Why this order.** When several series share one plot a reader compares any pair,
not just neighbours, so the **all-pairs** separation floors apply rather than the
adjacent-pairs ones most palettes document for lines. Measured over the first five
slots, in OKLab ΔE ×100: worst pair 15.6 for normal vision, clearing the ≥ 15 hard
floor, and 7.6 under simulated colour-vision deficiency, which sits in the 6–8 band
and is permitted only with a second identity channel.

The usual default order fails this test. Blue, orange, aqua, yellow, magenta puts
orange against yellow at 13.7 and orange against magenta at 12.9, both under the
floor. If you inherit a palette, re-measure before trusting its order.

**Compute, never eyeball.** sRGB → linear → OKLab for ΔE, WCAG relative luminance
for contrast, and Machado et al. (2009) severity 1.0 matrices in linear RGB for
protanopia, deuteranopia and tritanopia. Enumerate candidate subsets and orderings
and pick by the measured minimum, rather than by taste.

**Past the palette, stop.** More series than hues means faceting or dropping series.
A generated ninth hue is not an option.

**Low-contrast slots oblige relief.** Aqua and yellow fall under 3:1 on this paper.
That is acceptable only with visible direct labels or a table view of the same data.
Both should be present anyway.

## Identity beyond colour

Every chart carries three channels, so nothing depends on hue alone:

1. a **direct label** at the end of every line, in ink, with the swatch beside it
2. a **legend** in the figure head, always present for two or more series
3. a **facet** view: one small panel per entity on a shared scale

Text wears text colours. A value or a name never takes the series hue; the swatch
next to it carries the identity.

## Marks

- Lines 2px, round caps and joins, no dash patterns when hues are distinct.
- Markers 4–4.5px radius with a 2px surface-coloured ring, so overlaps stay legible.
- Marker fill deepens across an ordered sequence, which encodes order without a
  second legend.
- Grid lines in `--rule`, axis line in `--text-3`, both recessive.
- Reference lines dashed `5 4` in `--text-3`.
- Native `<title>` on each marker gives a free tooltip with no script.

## Reference lines

Label them **in the right-hand gutter**, as one more entry in the same
collision-avoidance pass as the series labels, with a dashed swatch. Never on the
plot: a reference line usually sits where the data is densest, and any label placed
on it will eventually print through a series. In a faceted chart with no gutter, put
it in the legend instead.

## Axes

- Captions are sentences, not shorthand: quantity, split, scale, then direction.
  "Mean regret, held-out split (log scale). Lower values indicate better
  performance." Sentence case, not uppercase.
- Size the left margin from the widest tick label. A fixed margin clips the leading
  character the moment a metric changes magnitude.
- Log ticks: generate candidates as {1, 1.5, 2, 3, 5, 7} × decades from 1e-6 upward.
  Omitting decades below 1 makes a metric in [0.03, 0.13] fall back to raw data
  values as tick labels.
- Five significant digits for every printed number. Rounding by magnitude turns
  128.5 and 117.6 into 128 and 118 and stops distinguishing runs.
- One y-axis. Two measures of different scale means two charts.

## Label collisions

Collect the end labels as `(y, name, value, colour)`, sort by `y`, then walk the
list pushing any label closer than about 15px down to the minimum gap. Include the
reference line in the same list. Where a label must cross a line or a rule, give it
a paper-coloured halo via `paint-order: stroke`, or a filled rect behind it when the
halo is not enough.

## Panels and facets

A facet grid needs top margin for its titles: labels placed at the very top of the
viewBox get clipped in half, which looks like a rendering bug rather than a spacing
one. Give each facet its own title with a swatch, share the y scale across all of
them, and label only the first and last point, nudged clear of any reference rule.

## Before shipping

The colour work is computable and the layout is not. After the palette passes:

1. Render the chart and look at it. Check for collisions, clipped text, overflow.
2. Confirm the legend, the direct labels and the facet all agree on identity.
3. Read the axis caption aloud. If it needs a decoder, rewrite it.
