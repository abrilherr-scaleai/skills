# Model colours

## The rule

Colour identifies the **model**, never its rank. A model keeps its hue across every
chart, the results table, the round table, and the coloured left border on its
group in Trajectories and in the per-iteration output. It also keeps it across
tasks, so a reader moving between two task views does not have to relearn the key.

## The palette

Taken from the validated reference categorical palette, in this fixed slot order:

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

Fixed assignments: Claude Opus 5 → 0, GPT-5.6-sol → 1, Muse-Spark 1.2 → 2,
Claude Sonnet 5 → 3, Claude Haiku 4.5 → 4. Any other model takes the lowest free
slot in name order.

## Why this order and not the palette's default

Five series share one plot, so a reader compares any pair, not just neighbours.
That means the **all-pairs** floors apply, not the adjacent-pairs ones the palette
documents for lines.

Measured over the first five slots above, in OKLab ΔE ×100:

- worst pair, normal vision: **15.6**, clearing the ≥ 15 hard floor
- worst pair, simulated CVD (protan, deutan, tritan): **7.6**, inside the 6–8 band

The 6–8 band is permitted only with a second identity channel. Here that channel is
the direct label at the end of every line, plus the per-model facet in Round by
round, plus the coloured chip beside every model name in every table. No series is
ever identified by colour alone.

The palette's own default order fails on this plot. Its first five slots put blue,
orange, aqua, yellow and magenta on screen together, and orange against yellow
measures 13.7 while orange against magenta measures 12.9, both under the floor.

Aqua at 2.70:1 and yellow at 2.07:1 sit below 3:1 on the page surface, which
triggers the relief rule: visible direct labels or a table view. Both are present.

## If a campaign uses more models

Past eight the palette cannot separate the series and the build warns. Facet the
extra models or drop them from the line charts rather than accepting a repeated
hue. Adding a generated ninth hue is not an option.

## Redoing the maths

There is no JS runtime on this machine, so the palette validator cannot be run
directly. The figures above were computed in Python: sRGB → linear → OKLab for the
ΔE, WCAG relative luminance for the contrast, and Machado et al. (2009) severity
1.0 matrices in linear RGB for the three CVD simulations. Recompute the same way if
the palette or the model set changes, and enumerate candidate orderings rather than
picking by eye.
