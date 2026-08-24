---
name: abril-skill-htmls-scaleai
description: >
  Abril's visual system for customer-facing technical HTML at Scale: reports,
  deliverables, result explorers, data-heavy single-page documents, dashboards and
  decks. Aeonik Light body with Medium headings, cool near-white paper and ink,
  hairline-bordered white panels, a two-column section layout, a sticky header with
  a sentence-case tab bar, and colour reserved for data series drawn from a validated
  categorical palette. Use when asked for the "report style", "technical report
  look", "the RSI deliverable look", "our HTML style", a "professional data page", or
  when building any page whose job is to present measurements and evidence to an
  outside reader. Content-agnostic: for the RSI task pages specifically, rsi-task-view
  applies this system to that data. For the earlier fully monochrome monospace-display
  variant, use minimal-tech-style.
---

# Abril's HTML style, Scale AI

A document that reads as evidence, not as marketing. Type does the work, panels
give structure, and the only colour on the page identifies data series.

## One-liner

> Cool near-white paper and ink · Aeonik Light for text, Medium for headings ·
> monospace only for identifiers and code · hairline-bordered white panels for
> figures and figure bands · two-column sections with the heading on the left ·
> colour only for data series, from a validated categorical palette · emphasis by
> weight and a grey marker, never by hue · no captions explaining the design, no
> provenance boilerplate.

## Principles

1. **Every heading is at least as large as the text it heads.** Small uppercase
   labels are for column headers and metadata, never for section titles.
2. **Contrast comes from type scale and weight**, then from hairlines, then from
   panels. Never from decoration.
3. **Colour is data.** The chrome is monochrome. A hue on the page means a series,
   and it identifies that series everywhere: chart, legend, table row, group border.
4. **Panels, not cards.** A white surface with a 1px hairline and 8px radius, no
   shadow, no gradient. Used for figures and the figure band only, so they read as
   instruments rather than decoration.
5. **Fill the width.** Section headings sit in a left column and prose in a wider
   right column. Text that uses half the screen reads as an unfinished memo.
6. **Monospace is for identifiers and code**: document ids, file names, file
   contents, transcript output. Everything else is the sans.
7. **Say nothing about the design.** No caption explaining what a marker shade
   means, no footer stating where the figures came from.
8. **Emphasis is monochrome and rationed.** One marked claim per paragraph, weight
   on the figures that support it. A highlight is a grey ground, never a hue, or the
   page loses the one thing colour is reserved to mean.
9. **A figure that can be misread carries its own reading.** Not a caption
   describing the chart, but the claim the chart supports and the measurements
   behind it, set beside the panel rather than inside it.

## Tokens

`assets/tokens.css` is the whole stylesheet, paste-ready, with a class map at the
top. Load two fonts and use the class names; nothing in it is project specific.

```css
--bg:#FAFAFA;      --surface:#FFFFFF;  --sunken:#F1F1F4;
--text:#111113;    --text-2:#4B4B52;   --text-3:#8A8A92;
--rule:#E6E6EA;    --rule-2:#D8D8DE;   --ink:#111113;  --hover:#F4F4F7;
--code-fg:#6D5AE6; --code-bg:#F1F1F4;  --r:6px; --r-lg:8px;  --col:1240px;
```

Colour is a strict monochrome ramp plus indigo for code. Data-series hues come
from `references/charts.md` and appear nowhere in the chrome.

## Type

- **Aeonik**, Light 300 for body, Medium 500 for headings, wordmark and figures.
  The scale runs one cut lighter than instinct suggests: what looks like it wants
  Bold takes Medium, what wants Medium takes Light.
- **A monospace face** for identifiers and code only. `code`, `pre`, transcript
  bodies, file names, document ids.
- Body 14.5px / 1.6. Section title `clamp(17px,1.7vw,20px)`. Page title
  `clamp(24px,2.5vw,31px)`. Small labels 9.5–11px uppercase, letter-spacing .08em.
- `font-variant-numeric: tabular-nums` globally, so figures in tables and charts
  line up.
- Sentence case for anything longer than three words. Uppercase is for short
  labels: column headers, tab labels, legend entries, metadata.
- Never uppercase an identifier. `adaptive-cache-replacement` stays lowercase.

Fonts are licensed. `assets/fonts` holds Aeonik Light and Regular as woff2 from the
foundry's web package, plus Medium and Bold converted locally from desktop OTF.
Base64-embed them for a self-contained file. Check the web licence before shipping
a file outside the organisation; Fontshare's Satoshi or General Sans substitute
cleanly if it does not permit that.

## Layout

- Max width 1240px, 32px gutters, one column of content.
- A section is `.sec.split`: heading in a 190–230px left column, body in the right
  column at up to 92ch, collapsing to one column under 900px.
- Sections are separated by a hairline and 54px, never by boxes.
- `.grouprule` is a rule with a small label and an identifier, marking where the
  subject changes, for example where general method ends and specifics begin.
- Sticky header: wordmark, a quiet subtitle, and the document identifier pushed
  right. Tab bar below it, labels only, active tab underlined in ink. No numbering.

## Page shell and distribution

The measurements the RSI pages actually use, so a new page starts in the right place
rather than being tuned by eye.

**Header.** Sticky, on `--surface`, closed by a 1px `--rule-2` bottom border, no
shadow. One row: the wordmark in Medium 21px with `letter-spacing .02em`, a 20px
organisation mark beside it at 10px gap, then the tab bar, then the document
identifier pushed right in monospace 11.5px `--text-3`. The row is
`align-items: stretch` so the tabs can own the full header height and carry the
active underline at its bottom edge.

**Tab bar.** Labels only, sentence case, 17px at weight 400, 36px apart, `#9A9AA2`
when inactive and `--text` at weight 500 when active. Padding `17px 0 16px`. No
numbering, no uppercase, no pill or box. A tab label is a word, not a chip.

**Column.** `--col` 1240px, 32px gutters, one column of content. `main` pads
`40px 32px`. The footer sits above 90px of air, on a hairline, at 10.5px.

**Section rhythm.** A section is `.sec.split`: a `minmax(190px, 230px)` heading
column and a `minmax(0, 1fr)` body column, `gap: 8px 48px`, collapsing to one column
under 900px. Sections are 24px apart with no rule between them; `.grule` marks a
change of subject with a hairline and 48px above it. Prose caps at 92ch, never at
half the viewport.

**Type scale.** Page title `clamp(24px, 2.5vw, 31px)` Medium, `letter-spacing -.015em`,
line-height 1.16. Section title `clamp(17px, 1.7vw, 20px)` Medium. `h3` 17px Medium
with 32px above. `h4` is a 10px uppercase label at `letter-spacing .08em` in
`--text-3`, for field names inside a record, never for a section. Body 14.5px / 1.6.
The standfirst under a title is 16px in `--text-2`; the document identifier under it
is monospace 13.5px in `--text-3`.

**Figure band.** `repeat(auto-fit, minmax(190px, 1fr))` inside one bordered panel,
cells split by vertical hairlines, 16px by 22px padding, label 9.5px uppercase, value
Medium 22px. Three or four cells; past that it stops scanning.

**Spacing.** The vertical rhythm is 8, 12, 24, 32, 48, 90. Anything between those is
a decision that needs a reason.

## Components

**Figure band** (`.stats`) — the numbers under the title. One bordered white panel,
cells divided by vertical hairlines, label 9.5px uppercase, value in Medium at
22px, an optional note beneath. Three or four cells; past that it stops scanning.

**Figure panel** (`figure`) — white panel, hairline, 8px radius. A head bar with
the title on the left and the legend on the right, the axis caption beneath them as
`.fsub` at 13px, the chart in the body, and a `figcaption` only if it carries fact
rather than commentary. The caption is 13px in `--text-2`, not the 12px `--text-3` a
caption instinctively wants: it is read, so it is sized to be read. Let it carry
markup, so a phrase inside it can take emphasis.

**Figure commentary** (`.fnote`) — the paragraphs that say what a figure means, set
below the panel with an 18px indent and a hairline left border, so they read as
belonging to that figure without being boxed in with it. This is where a claim, its
measurements and the limits on what the figure can settle go. Anything longer than
two sentences belongs here rather than in a `figcaption`.

**Lead sentence** (`.claim`) — a one-sentence paragraph in Medium ink, standing in
for a heading inside a passage of prose. Use where a section has three or four
distinct claims that each need a paragraph but do not deserve headings. Never more
than one per claim, and never as a substitute for a real section title.

**Marker** (`.key`, and `.dir` for a metric's direction) — Medium ink on a `--sunken`
ground, 4px radius, 1.5px by 6px padding. The page's only highlighter. `.dir` is
nowrap for a short fixed phrase like "Lower values indicate better performance";
`.key` wraps and needs `box-decoration-break: clone` so the padding survives a line
break. One per paragraph.

**Record rows** (`details` in a `.mgroup`, body as `.ibody`) — for a long paired
record, per entity and per step: the step and its headline number in the summary, the
fields inside. Reach for this the moment a table would put two columns of prose side
by side, which no table width can carry.

**File tree** (`pre.tree`) — a `└──`/`├──` tree at 12px in `--text-2`, listing an
artifact's contents with byte sizes. Generate it from the artifact itself, never by
hand, so the page cannot describe a bundle it did not produce.

**Legend** (`.legend`, `.lg`) — a 13×3px swatch and a name in uppercase 10px. A
dashed swatch for a reference line. Always present for two or more series.

**Chip** (`.chip`) — swatch plus name in ink, for series identity in a table cell.
The name never takes the series colour; the swatch carries it.

**Tables** — mono uppercase header over a 1px ink rule, hairline row rules, hover
fill, numerics right-aligned and tabular. When rows group under an entity, put the
rule **above each group's first row and nowhere else**, so five rows read as one
block rather than five peers.

**Key/value** (`.kv`) — a two-column grid with hairline row separators, label in
small uppercase. For limits, parameters, anchors.

**Disclosure** (`details`/`summary`) — hairline rows, `+` and `−` markers, the name
at 14px and metadata pushed right. A filename in a summary reads larger than the
content it opens.

**Transcript row** (`.logrow`) — a 92px label column and the content beside it.
Long output is clipped to about nine lines with a fade and a `.btnghost` control to
open it, so a long transcript stays skimmable.

**Notice** (`.gap`) — white panel with a 3px ink left border, a small uppercase
label, one sentence. For missing or incomplete data. Never for good news.

**Buttons** — `.btn` is solid ink, paper text, hover inverts. `.btnghost` is a
hairline outline for secondary actions. Both mono-uppercase 10–11px.

## Charts

Full specification in `references/charts.md`: the colour formula and why the
default palette order fails past three series, mark sizes, reference lines, axis
captions, log ticks, label collision avoidance, and the checks to run. Read it
before writing chart code.

The three rules that matter most:

- **Bind colour to the entity, never to its rank.** A filter or a re-sort must not
  repaint the survivors.
- **Identity is never colour alone.** Direct labels at the end of every line, a
  legend, and a facet view.
- **Label reference lines in the gutter**, inside the same collision-avoidance pass
  as the series labels, never on the plot.

**A log axis where the span demands one.** An axis carrying a cost or a count often
runs one or two orders of magnitude across series, and on a linear scale the cheap
ones crush against the frame and the plot reads as a single outlier. Put that axis on
a log scale with **1, 2, 5 per decade** ticks, drawn as gridlines, since the uneven
tick spacing is the only cue the scale is not linear. The 1, 1.5, 2, 3, 5, 7 ladder
that suits a narrow y range thins to an unreadable 1.5, 3, 7, 15 when a wide span
forces it to halve. Say "log scale" in the axis caption. Pad the ends by about
`(hi/lo)**0.045`: enough that the first marker is off the frame, little enough that
it does not pull a spare tick a decade below the smallest value into range.

**State the direction of the metric, and mark it.** Lower-is-better and
higher-is-better both exist, and it is the one fact a reader must hold to read any
chart. Put it at the end of the axis caption and wrap it in `.dir`. Match the
phrasing rather than assuming the direction, so a higher-is-better figure marks its
own sentence with no change to the code.

## Copy

- No em-dashes or en-dashes. Commas, colons, "or".
- No emoji.
- Formal, specific, and about the subject. Never explain the interface, never
  describe the methodology twice, never state that the data is real.
- Axis captions are sentences: quantity, split, scale, then direction.
- Cut anything that reads as reassurance. "Nothing is transcribed by hand" belongs
  in a process document, not on the page.
- **Lead with the mechanism, not with how to feel about it.** "Read this as a
  difference in style, not in efficiency" tells the reader what to conclude;
  "cumulative consumption grows with the square of what a model writes" tells them
  why, and the conclusion follows on its own. Cut every sentence of the first kind:
  "that is the point of showing both", "this is not where winning happens", "it
  barely writes", "that compounds".
- **A figure's commentary leads with what the figure is for**, not with an
  explanation of one feature of it. If the interesting thing is that the last steps
  cost half the budget and returned nothing, that goes first; the reason one series
  sits far left is a detail and goes second.
- **Every number in the prose is recomputed from the data before it ships**, and any
  claim that fails is rewritten to what the data supports rather than softened.
  Aggregates across entities with different starting points are dominated by whoever
  started worst, so prefer per-entity ranges to a weighted total.
- Numbers use one format throughout. If a reward is three decimals in a table it is
  three decimals in a disclosure summary.

## Hard avoids

Shadows · gradients · glassmorphism · rounded SaaS cards · icon-heavy UI ·
centre-aligned body text · numbered tab labels · uppercase sentences · uppercase
identifiers · headings smaller than their body text · a colour in the chrome ·
captions that explain the design · a hue standing in for a rank · dual y-axes ·
prose confined to half the viewport · a coloured or yellow highlight · emphasis on
more than one phrase per paragraph · a table column holding a paragraph · a linear
axis across two orders of magnitude · text clipped with an ellipsis where the full
text exists.

## Checklist

1. Every heading larger than its body text.
2. No hue anywhere except data series and the indigo in code, and no highlight that
   is not the grey marker.
3. Charts: no label collisions, no clipped tick text, legend present, reference
   line labelled in the gutter, direction stated and marked, log scale where the
   span crosses a decade.
4. Tables: rules group rather than separate, numbers right-aligned and tabular, and
   no column carrying prose that a disclosure row should hold.
5. Copy swept for dashes, emoji, sentences that describe the interface, and
   sentences that tell the reader what to conclude.
6. Every figure in the prose recomputed from the source data, and any generated tree
   or manifest generated from the artifact rather than written.
7. At most one marked phrase per paragraph, and it is that paragraph's claim.
8. Rendered and looked at, not just built. Screenshot each tab or section. On a
   multi-megabyte page a headless screenshot may time out where a per-tab visibility
   assertion still passes; when that happens, say the layout was checked from the
   rendered DOM and not by eye rather than implying it was seen.
