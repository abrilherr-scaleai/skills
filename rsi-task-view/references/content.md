# Writing the per-task copy

Four strings per task. The register is formal and factual: this goes to a research
audience who know what RSI is and do not need it explained or sold.

## Voice rules

- No em-dashes or en-dashes. Use commas, colons or "or".
- No emoji.
- Never restate the methodology in the task copy. The `Methodology` block already
  says how the loop works; a task description that re-explains inheritance is noise.
- Never define a quantity by contrast. "Not the hit rate, but the hit rate relative
  to a cache that could see the future" reads as a riddle. State the thing.
- Never assert something the run data does not record. Reasoning-effort settings,
  harness names per model, and which models count as SOTA are not in the source: if
  they matter, ask for them and put them in the config.
- Prefer the concrete stopping condition over a vague one. "Until its budget is
  exhausted" became "An iteration ends when it reaches its wall-clock limit of
  3,600 seconds or its cap of 50 graded submissions, whichever comes first", with
  both numbers read from `task.toml`.

## `one_line`

One sentence under the title: what the model produces, and what it is graded on.

> The model writes an online cache eviction policy, which is graded on held-out
> workloads spanning five traffic patterns at two cache sizes.

> The model selects the 4,096 byte strings that make up a tokenizer vocabulary,
> which is graded on how many tokens it needs to encode held-out text.

## `scoring`

The measured quantity, plainly, ending with the direction. HTML, usually one `<p>`.

> The shortfall between the policy's hit rate and the best hit rate achievable on
> the same request stream at the same cache size, averaged across every workload
> type and cache size in the graded split. Lower is better.

> The number of tokens the vocabulary requires per 1000 bytes of previously unseen
> text. Encoding is performed by the harness, so submissions differ only in the
> strings they select. Lower is better.

## `axis_label`

Quantity, split, scale, then direction, as a sentence rather than a shorthand.

> Mean regret, held-out split (log scale). Lower values indicate better performance.

## `citation`

`[url, html]`. The work the environment was modelled on, rendered as a link labelled
`Motivation:` under the task description. Italicise the title.

> Rodriguez et al., *Learning Cache Replacement with CACHEUS*, USENIX FAST '21
> Liu et al., *SuperBPE: Space Travel for Language Models*, COLM 2025, arXiv:2503.13423

Verify the title and authors against the actual page before writing it. Where a
publisher blocks automated fetches, take the citation from an existing internal
document rather than reconstructing an author list from memory, and say which you
did.

## What not to write at all

The following were all cut from earlier drafts for being commentary rather than
content, and should not come back:

- chart captions explaining what a marker shade means or why colour is not the only
  identity channel
- a provenance footer stating that figures come from the run data
- a table of loop mechanics with labels like "isolation", "control" and "what
  carries over"
- "a typical from-scratch session" next to a stat-band number
- any note explaining that data was added or corrected after the fact
