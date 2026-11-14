---
name: scale-one-pager
description: "Build a one-page project summary (HTML plus a one-sheet PDF) for any Scale project in a minimalist black and white style: big title, one description paragraph, then Methodology with a process diagram, Task structure as a file tree, Quality assurance checks, Domains with distribution charts, and Results with headline numbers and one plot. Use when someone asks for a one pager, one-page summary, project brief, leave-behind or \"scale one pager\" for a project, from any source (website, text, docs, GitHub repo, example task bundle)."
---

# scale-one-pager

One letter page that summarises a project. Same look for every project; the content comes from the person's sources. `assets/template.html` holds every component. If `assets/example.html` exists (local only, not in the repository), it is the reference for look and density.

## 1. Collect the inputs

Read every source the person gave first (a website, pasted text, a doc, a GitHub repo, a folder, an example task bundle). Then ask, in one AskUserQuestion round, only for what is still missing. Never invent content: anything not provided and not found becomes a grey placeholder, `<p class="ph">[Placeholder: what is missing]</p>`.

| Needed | Used for | If missing |
|---|---|---|
| Project name, and a short name for the header | Title, header wordmark | Ask. Required. |
| Description of the project (2 to 3 sentences) | Paragraph under the title | Ask. Required. |
| How it works: the method or process, step by step | Methodology: diagram plus one paragraph | Ask |
| One example task bundle (folder, zip or repo path) | Task structure: file tree | Ask for one. Read it and build the tree from its real files. |
| Quality assurance or task difficulty checks | Quality assurance list | Ask |
| Domains or categories and their distribution (counts or shares, plus any two-way split such as CPU or GPU) | Domains: split bar and bar chart | Ask |
| Relevant results: headline numbers and the data points of the best plot | Results: stat row and one plot | Ask |
| Footer line (for example a confidentiality note) | Footer | Leave the footer out |

A section with no content at all is removed, not padded. Sections can be renamed to fit the project (for example "Environment structure" in place of "Task structure").

## 2. Content rules

- **Keep the person's wording.** When the source is their own text, copy sentences as written and cut whole sentences for length. Do not paraphrase. Fix only grammar they asked to fix.
- No sentence may talk about delivery ("what we deliver", "deliverable", "we provide"). Describe the thing itself: "Task structure", "Each task contains".
- Neutral, formal, client-safe: never "customer", nothing internal (pricing, staffing, tools, ticket names).
- No first person: never "we", "our" or "us". Describe the project and the tasks, not the team.
- No em dashes, en dashes or double hyphens. Use commas, colons or "to".
- No intros that explain the page, no takeaways, no filler. One paragraph per section at most, apart from Results.
- Sections must not repeat each other. If two overlap, keep one.
- Names only for anything future or optional (for example upcoming domains): no detailed breakdown.
- Numbers come from the source, never estimated. Say in the reply which date or version they are from.

## 3. Build the page

1. Copy `assets/template.html` to `<project-folder>/one-pager.html` (ask where if there is no obvious folder; default `~/<project-short-name>-one-pager/`). It already holds all the styles and the Scale mark.
2. Replace every `{{...}}` slot. No `{{` may remain.
3. Header: Scale mark plus the project short name. Never another project's name.
4. Layout: two columns that end at the same height. Left: Methodology, Task structure, Quality assurance. Right: Domains, Results. Move a section across if one column is much longer.
5. Diagrams and charts are hand-written inline SVG using the template's classes (colors come from the tokens, so dark mode works):
   - **Process diagram:** one rounded box per step with arrows; add the return arrow only if the process loops. Check that every label fits inside its box.
   - **Split bar** (`.csplit`): a two-way share such as GPU and CPU. Black for the first part, grey for the second.
   - **Distribution chart:** one horizontal bar per category, value label after the bar, x axis titled. Stack black and grey only when there is a two-way split.
   - **Results plot:** one plot, the one with the clearest result, redrawn from the real data points. Both axes titled, series labelled at the line end, baseline dashed, weaker or reference series dashed grey. The template holds a sample line chart to adapt.
   - Monochrome only: black, white, greys. The only color is the green tick in Quality assurance.
6. Chart titles name what the chart shows, not a conclusion. One line under the title says what the axes are and which direction is better.
7. One font, Geist. No monospace, including file names in the tree.

## 4. Fit to one page and check

Run `scripts/fit.sh /abs/path/one-pager.html`. It picks the largest print font size that keeps the page on one letter sheet, writes `one-pager.pdf` and a screenshot `one-pager.png` next to the HTML.

- If it reports "STILL OVER ONE PAGE", cut content (whole sentences, or the least important section) and run it again. Do not shrink the type further.
- Read the screenshot and the PDF: no overlapping chart labels, no text outside diagram boxes, both columns ending level, nothing on a second page.
- Search the file for `{{`, `—`, `–`, "deliverable", "customer" and the words "we", "our", "us"; all must be absent from visible text.
- Open the HTML for the person (`open one-pager.html`).

## 5. Report back

Short: where the HTML and PDF are, which parts are placeholders, which sentences were cut, and where the numbers came from. Then ask what to change.
