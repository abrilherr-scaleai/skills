# Failure modes

Every entry here is a bug that shipped or nearly shipped while building the first
two task views. They are listed because each one is silent: the page renders and
looks finished while being wrong.

## The page script dies and only the first tab works

**Symptom.** Overview shows, the other three tabs do nothing.

**Cause.** The generator emits JavaScript from a Python string. `"\n"` written in
that Python string reaches the page as a real newline, and a real newline inside a
JS string literal is a syntax error, which kills the whole script including the tab
wiring. The escape has to survive one round of Python interpretation, so the
generator source needs `"\\n"`.

**Guard.** `--check` loads each tab in headless Chrome and asserts exactly one
section is visible. Run it on every build.

## A block of content appears on every tab

**Cause.** Fragments lifted from the source are sliced on heading boundaries, so
they can carry a stray `</div>` or leave an element open. A stray closer ends the
generator's own `<section>` early and everything after it lands outside all tabs,
which means it is never hidden.

**Guard.** `balance_html()` runs over every lifted fragment: it drops closers for
elements that were never opened and closes what is still open. The build also
counts `<div>` against `</div>` per section.

## A whole overview block silently disappears

**Cause.** Matching source headings against a hard-coded list. The cache sample's
third heading reads "How the chain is run, and what it is compared against" while
the tokenizer's reads "How the chain is run", so an exact-match whitelist dropped
the block from one page only.

**Guard.** Render whatever blocks the source has, in source order, and match on
prefixes when substituting.

## One model's iterations get attached to another model

**Cause.** Splitting the source section on every `<h3>`. The models' own `notes.md`
contain `<h3>` headings ("Round 3 notes"), so the split tears each model's group
apart at the first note.

**Guard.** `model_groups()` walks only the top level, jumping over whole
`<details>` blocks so nested headings stay invisible.

## Every file in the zip comes out wrapped in code fences

**Cause.** `re.findall(r"<pre>...")` never matches, because the tag carries
attributes. Every file then took the markdown path, which fences `<pre>` content.

**Guard.** `<pre[^>]*>`. Verify by comparing an entry's size in the zip against the
size printed in the task card: they should match exactly.

## Anchors, metric or task id read as the fallback

**Cause.** `task.toml` is embedded HTML-escaped, so `metric = "mean_regret"` is
actually `metric = &quot;mean_regret&quot;` in the source. A regex expecting real
quotes matches nothing and the code falls back silently.

**Guard.** Parse against `H.unescape(doc)`. The build prints the model list and
iteration count; if the task id looks like a slug of the title rather than the id
from `task.toml`, suspect this.

## Usernames and host paths leak into the trajectories

The two campaigns ran on different hosts, so run directories appeared in three
shapes, and a username also appears in `ls -l` output where no path is involved:

- `/mnt/efs/<user>/src/.rsi_sandboxes/rsi_run_X/workspace`
- `/tmp/rsi_run_X/workspace`
- `/private/var/folders/…/T/rsi_run_X/workspace`
- the same path dash-flattened and used as a directory name
- `claude-1335`, `claude-08b1-cwd` session ids
- bare `renxiongwang` as file owner and group in `ls -l`

**Guard.** The redactor collects usernames from every path shape it finds, then
replaces the bare token everywhere, and collapses any absolute path containing a
run id. After a build from a new campaign, grep the output for `/Users/`, `/mnt`,
`/tmp/rsi`, `rsi_run`, and the operator's name.

## Axis labels clipped, or tick values that are raw data

**Causes.** The left margin was a constant, so a wide tick label lost its leading
character. Separately, the log tick generator had no decades below 1, so a metric
living in `[0.03, 0.13]` fell through to using raw data values as ticks.

**Guard.** The margin is sized from the widest tick label; tick magnitudes run from
1e-6. Look at both charts after any metric change.

## A label prints through a data line

**Cause.** A reference line's label drawn on the plot. On the tokenizer task three
models finish within a point of reward 0, so no side of that rule is clear.

**Guard.** The reference is labelled in the right-hand gutter and joins the same
collision-avoidance pass as the series labels.

## Numbers rounded until they stop distinguishing runs

**Cause.** Formatting by magnitude, which turned 128.5 and 117.6 into 128 and 118.

**Guard.** Five significant digits everywhere, via `fmt()`.

## Headings smaller than the text they head

**Cause.** Reusing a small uppercase label style for real headings, including
inside the models' rendered notes.

**Guard.** Any heading is at least as large as its body text. Inside lifted note
bodies, `h3` is 16px and `h4` is 14px against 13.5px body.
