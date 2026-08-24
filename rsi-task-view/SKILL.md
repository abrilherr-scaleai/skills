---
name: rsi-task-view
description: >
  Build the standard customer-facing HTML view for an RSI (recursive
  self-improvement) optimisation task from a run campaign's sample HTML. Use when
  asked to produce, rebuild or restyle an RSI task deliverable, a "task view", a
  "task explorer", or the HTML that ships with an RSI environment; when a new task
  needs the same four-tab page as adaptive-cache-replacement and
  tokenizer-vocabulary-design; or when an existing one needs a content or styling
  change. Handles any model set and any iteration count, and carries the per-task
  prose, the model colour system, the zip export and the build-time checks.
---

# RSI task view

Produces one self-contained HTML file per task, in the format agreed with the
customer. Two tasks already ship in this format and the generator reproduces both
byte-for-byte, so treat their output as the reference.

## What the page contains

Five tabs, in this order. The tab bar carries no numbering.

| Tab | Contents |
|---|---|
| **Overview** | Task title, task id in monospace, a one-sentence summary, a stat band, then `Methodology`, a rule marking where task-specific material starts, `Task description` with a Motivation link and the task detail, `Inputs`, `Scoring`, `Why the task is hard`, `Results` |
| **Task card** | Limits and reward anchors, the bundle download and a tree of what is in it, then each shipped file inline |
| **Trajectories** | Every model, every iteration, turn by turn, with long tool output clipped, and one JSON download per model covering the whole run |
| **Model performance** | Three charts, the per-iteration table with reward on `[0, 1]`, `Where the models fail`, and each iteration's submitted artifact and notes |
| **Recursive loop** | The iteration record from the summary file: per model, per iteration, the reward, the approach that iteration took, and the note it inherited, plus a JSON download |

There is deliberately **no download control per iteration**. The per-model button
hands over the whole run, and twenty-five buttons on one tab is a control on every
row for a file nobody wants individually.

`Methodology` describes the RSI setup and is identical across tasks. Everything
below the rule is specific to the task. Keep that separation.

## Run it

```bash
python3 build.py SOURCE.html --out rsi-<task-id>.html \
    --config task.json --fonts assets/fonts --check
```

`SOURCE.html` is the sample the run campaign produces (the `*_fv.html` files).
`--check` loads the result in headless Chrome and asserts each tab opens; always
pass it. `--fonts` points at the embedded Aeonik files, default `./fonts` beside
the script, and `assets/fonts` in this skill holds a copy.

Name the output `rsi-<task-id>.html`, e.g. `rsi-adaptive-cache-replacement.html`.

## What is read from the source, and what you must supply

**Read automatically. Never hard-code these.**

- the model set and the iteration count, from the per-round chart data
- per-iteration scores and cumulative token counts
- reward anchors and the three limits, from `task.toml`
- the task id, from `[task] name` in `task.toml`
- the shipped file list and their contents, from the file cards
- what the solve container holds, from its `Dockerfile` `COPY` lines
- trajectories, artifacts and notes, per model and iteration

**Supply per task**, in the config. Each falls back to a default keyed by the
metric name, then to a generated sentence, so an unseen task still builds:

```json
{
  "source": "sample_cache_recursive_fv.html",
  "out": "rsi-adaptive-cache-replacement.html",
  "one_line": "The model writes an online cache eviction policy, which is graded on held-out workloads spanning five traffic patterns at two cache sizes.",
  "scoring": "<p>The shortfall between the policy's hit rate and the best hit rate achievable on the same request stream at the same cache size, averaged across every workload type and cache size in the graded split. Lower is better.</p>",
  "axis_label": "Mean regret, held-out split (log scale). Lower values indicate better performance.",
  "citation": ["https://www.usenix.org/system/files/fast21-rodriguez.pdf", "Rodriguez et al., <i>Learning Cache Replacement with CACHEUS</i>, USENIX FAST '21"],
  "sota_models": ["GPT-5.6-sol", "Claude Opus 5", "Muse-Spark 1.2"],
  "comparison_models": ["Claude Sonnet 5", "Claude Haiku 4.5"],
  "task_title": "Adaptive cache replacement",
  "task_id": "adaptive-cache-replacement",
  "task_dir": "tasks/cache-replacement-policy",
  "recursive_summary": "summary-cache.json",
  "task_detail": "<p>The model writes exactly one factory, <code>make_policy(capacity)</code>...</p>",
  "why_hard": "<p>Requests arrive one at a time in five traffic patterns...</p>",
  "failure_analysis": "<p class=\"claim\">One model never beat a single from-scratch session.</p>..."
}
```

`task_dir` points at the Harbor task on disk. The task card and the bundle both read
it, so the page cannot describe files the zip does not contain.

`task_detail` is appended to `Task description`, after the Motivation line. The
lifted paragraph is an analogy; this is the concrete half, meaning the exact function
the model writes, the workload types or the encoding rule, the three splits, and the
hard limits. Take it from the task's own `instruction.md` rather than paraphrasing.

`why_hard` and `failure_analysis` are prose written after reading the runs. Both use
`<p class="claim">` for a bolded lead sentence followed by its paragraph. Check every
number in them against the run data before shipping; the figures in the delivered
pages were verified that way, including the late-iteration gain shares, which are
computed as *(score at iteration n-2 minus the best of the last two iterations)
divided by (iteration 1 minus the run's best)*.

`recursive_summary` is the iteration record, with exactly four fields per entry:
`iteration`, `reward`, `turn_approach`, `recursive_notes_prev_turn`. Where the source
for it is a page that clips long bullets, restore them from the untruncated logs by
prefix match before building. Never paraphrase to fill a gap; a missing field renders
as "Not recorded for this iteration", which is the honest output.

`task_title` and `task_id` are only needed when the source is wrong or missing
them. `model_colours` can pin a hue for a specific model if you ever need to.

## Writing the per-task prose

Four strings, and the register matters more than the length. See
`references/content.md` for the rules and worked examples. In short:

- **`one_line`**: one sentence, what the model produces and what it is graded on.
  No marketing, no restating what RSI is.
- **`scoring`**: state the measured quantity plainly. Do not define a metric by
  contrast ("not the hit rate, but the hit rate relative to…").
- **`axis_label`**: quantity, split, scale, then direction. Ends with "Lower
  values indicate better performance."
- **`citation`**: the paper the environment was modelled on. Verify the title and
  authors against the actual page before writing it; do not reconstruct a citation
  from memory.

## Models

The model set is whatever the source contains. Nothing assumes five models, and
nothing assumes which are SOTA candidates.

- `sota_models` and `comparison_models` only drive one sentence in Model
  performance. Omit them and the sentence omits the split rather than guessing:
  the run data does not record which models are candidates.
- The spec's SOTA set is GPT-5.6-sol, Claude Opus 5 and Muse-Spark 1.2, and the
  comparison models vary between campaigns. List whatever the campaign used.
- Colour is bound to the **model**, never to its rank, so a model keeps its hue
  across charts, tables and tasks. Known models hold fixed palette slots; a new
  model takes the lowest free slot in name order, which is deterministic.
- Past eight models the palette cannot separate the series; the build warns and
  you should facet or drop a series rather than accept a repeated hue.
  `references/palette.md` has the measured separation figures.

## Before you call it done

1. `--check` passed, so every tab opens.
2. Open the page and look at the charts. The validator checks colour, not layout:
   look for label collisions, clipped axis text and overlapping end labels.
3. Grep the output for leaks: no usernames, host paths, run ids or session ids.
   The build redacts them, but a new campaign can introduce a new path shape.
   `references/troubleshooting.md` lists the shapes seen so far.
4. Click the zip button and open the archive. Six of the seven files should be
   byte-exact; compare a size against the size shown in the task card.
5. If a model has no trajectories or no artifacts, the page says so in an "Open
   gap" notice. Chase the missing data rather than shipping the notice.

## Hard rules

- **Never invent run data.** Every number on the page is read from the source. If
  something is missing, the page says it is missing.
- **Verbatim stays verbatim.** `instruction.md`, the submitted artifacts and the
  models' `notes.md` are evidence. Do not rewrite their wording, including their
  em-dashes and their phrasing. Page copy you author follows the house style: no
  em-dashes, no emoji, formal register.
- **Redact infrastructure, alter nothing else.** Usernames, host paths, run ids
  and session ids become labelled placeholders such as `[workspace]`.
- **Monospace is for identifiers and code only**: task ids, file names, file
  contents and trace output. Everything else is Aeonik.
- **Reward on `[0, 1]` appears alongside the raw metric**, because that is the
  scale the spec defines. The raw metric is what the charts plot.
