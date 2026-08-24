#!/usr/bin/env python3
"""Build the standard RSI task view from a recursive-improvement sample.

Reads the sample HTML a run campaign produces, lifts its content verbatim, and
re-emits it in the delivery format:

  OVERVIEW           task id, one-line summary, stat band, Methodology,
                     Task description, Inputs, Scoring, Results
  TASK CARD          limits, anchors, a zip of every shipped file, each file inline
  TRAJECTORIES       every model x every iteration, turn by turn, JSON per iteration
  MODEL PERFORMANCE  three charts, the per-iteration table with reward on [0, 1],
                     each iteration's submitted artifact and notes

Nothing about the model set or the iteration count is hard-coded: both are read
from the source. Per-task prose comes from a config file, with defaults keyed by
the metric and a generated fallback so a new task still builds.

  python3 build.py SOURCE.html --out OUT.html [--config task.json] [--check]

See SKILL.md for the workflow and references/troubleshooting.md for the failure
modes this generator is built to avoid.
"""
import html as H
import json
import os
import re
import sys
from html.parser import HTMLParser

# ---------------------------------------------------------------- source slicing


def read(path):
    return open(path, encoding="utf-8").read()


# Aeonik cut -> CSS weight. Medium is the text face for these pages.
FONT_WEIGHTS = [("Light", 300), ("Regular", 400), ("Medium", 500), ("Bold", 700)]


def font_faces(font_dir):
    """Base64 @font-face rules for Aeonik.

    These pages are single self-contained files, so a relative src= would break as
    soon as the file is moved; embedding keeps the page portable. woff2 is preferred
    where the foundry supplied it, woff otherwise (Medium and Bold shipped as desktop
    OTF and were converted locally, and woff2 needs brotli which is not installed).
    """
    if not font_dir or not os.path.isdir(font_dir):
        return ""
    import base64

    out = []
    for cut, weight in FONT_WEIGHTS:
        path = fmt_ = None
        for ext, css in (("woff2", "woff2"), ("woff", "woff")):
            cand = os.path.join(font_dir, f"AeonikPro-{cut}.{ext}")
            if os.path.exists(cand):
                path, fmt_ = cand, css
                break
        if not path:
            continue
        b64 = base64.b64encode(open(path, "rb").read()).decode()
        out.append(
            "@font-face{font-family:'Aeonik';font-style:normal;"
            f"font-weight:{weight};font-display:swap;"
            f"src:url(data:font/{fmt_};base64,{b64}) format('{fmt_}')}}"
        )
    return "\n".join(out)


def section(doc, name):
    a = doc.find(f'<section data-tab="{name}"')
    if a < 0:
        return ""
    b = doc.find("<section data-tab=", a + 10)
    return doc[a : (b if b > 0 else len(doc))]


def balanced(s, start, tag="details"):
    """Return s[start:end] where end closes the tag opened at start."""
    depth = 0
    i = start
    op, cl = f"<{tag}", f"</{tag}>"
    while i < len(s):
        n_op = s.find(op, i)
        n_cl = s.find(cl, i)
        if n_cl < 0:
            return s[start:]
        if 0 <= n_op < n_cl:
            depth += 1
            i = n_op + len(op)
        else:
            depth -= 1
            i = n_cl + len(cl)
            if depth == 0:
                return s[start:i]
    return s[start:]


def details_blocks(frag):
    """Every top-level <details> in frag, as raw markup."""
    out, i = [], 0
    while True:
        a = frag.find("<details", i)
        if a < 0:
            return out
        blk = balanced(frag, a)
        out.append(blk)
        i = a + len(blk)


def text_of(frag):
    s = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", frag))).strip()
    # tags collapse to spaces, which strands a space before punctuation:
    # "<em>in sequence</em>," would read "in sequence ,"
    return re.sub(r"\s+([,.;:!?%])", r"\1", s)


VOID = {
    "br", "img", "hr", "input", "meta", "link", "col", "source", "area", "base", "wbr",
    "circle", "line", "path", "rect", "text", "use", "stop", "polyline", "polygon",
    "ellipse", "tspan",
}
_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*?)(/?)>", re.S)


def balance_html(frag):
    """Make a lifted fragment self-contained.

    Slicing the old page on heading boundaries cuts through open elements, so a
    fragment can carry stray </div> closers or leave elements open. Either one
    silently reparents everything that follows: a stray closer ended my <section>
    early and pushed the block after it outside every tab.
    """
    out, stack, pos = [], [], 0
    for m in _TAG.finditer(frag):
        out.append(frag[pos : m.start()])
        pos = m.end()
        closing, name, _, self_closed = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if name in VOID or self_closed:
            out.append(m.group(0))
        elif not closing:
            stack.append(name)
            out.append(m.group(0))
        else:
            if name in stack:
                while stack and stack[-1] != name:
                    out.append(f"</{stack.pop()}>")
                stack.pop()
                out.append(m.group(0))
            # else: a closer for something never opened here. Drop it.
    out.append(frag[pos:])
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)


def h_blocks(frag, tag, cls=None):
    """Split frag on <tag> boundaries: [(heading_text, body_markup), ...]."""
    pat = re.compile(rf"<{tag}[^>]*>(.*?)</{tag}>", re.S)
    hits = list(pat.finditer(frag))
    out = []
    for n, m in enumerate(hits):
        end = hits[n + 1].start() if n + 1 < len(hits) else len(frag)
        out.append((text_of(m.group(1)), frag[m.end() : end]))
    return out


# ---------------------------------------------------------------- redaction

REDACT = [
    # Generic first: the two samples ran on different hosts, so run directories show
    # up as /mnt/efs/<user>/src/.rsi_sandboxes/rsi_run_X/workspace, /tmp/rsi_run_X/
    # workspace and /private/var/folders/../T/rsi_run_X/workspace. Any absolute path
    # carrying a run id collapses to the same placeholder.
    (re.compile(r"(?:/[\w.+-]+)*/rsi_run_[A-Za-z0-9]+(?:/workspace)?"), "[workspace]"),
    # dash-flattened path used as a directory name, e.g. a scratch dir named after
    # the workspace it belongs to. Must run before the path rules below.
    (re.compile(r"-mnt-efs-[A-Za-z0-9._-]+?-src--rsi-sandboxes-rsi-run-[A-Za-z0-9]+(?:-workspace)?"), "[workspace-slug]"),
    # sandbox workspaces, whatever host they ran on
    (re.compile(r"(?:/private)?/mnt/efs/[A-Za-z0-9._-]+/src/\.rsi_sandboxes/rsi_run_[A-Za-z0-9]+/workspace"), "[workspace]"),
    (re.compile(r"(?:/private)?/var/folders/[^\s\"'`\\]*?/rsi_run_[A-Za-z0-9]+/workspace"), "[workspace]"),
    (re.compile(r"/private/tmp/claude-\d+/[^\s\"'`\\]*?/scratchpad"), "[scratch]"),
    (re.compile(r"(?:/private)?/var/folders/[A-Za-z0-9_+/]+"), "[tmp]"),
    # sandbox root without the /workspace suffix (an agent listing its parent dir)
    (re.compile(r"(?:/private)?/mnt/efs/[A-Za-z0-9._-]+/src/\.rsi_sandboxes/rsi_run_[A-Za-z0-9]+"), "[workspace]"),
    (re.compile(r"/mnt/efs/[A-Za-z0-9._-]+"), "[home]"),
    (re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+"), "[home]"),
    (re.compile(r"-Users-[A-Za-z0-9._-]+-scaleapi[A-Za-z0-9._-]*"), "[project]"),
    # anything the earlier rules shortened but left a run id on
    (re.compile(r"\[home\]/src/\.rsi_sandboxes/rsi_run_[A-Za-z0-9]+"), "[workspace]"),
    (re.compile(r"\.rsi_sandboxes/rsi_run_[A-Za-z0-9]+"), "[workspace]"),
    # harness session and shell ids that surface in tool output
    # no \b here: in JSON payloads these sit directly after an escaped "\n", so the
    # preceding character is a word character and a boundary never matches
    (re.compile(r"claude-[0-9a-f]{4}-cwd"), "[session]"),
    (re.compile(r"claude-\d{3,}"), "[session]"),
    (re.compile(r"-?mnt-efs-[A-Za-z0-9._-]*?-?rsi-sandboxes-rsi-run-[A-Za-z0-9]+(?:-workspace)?"), "[workspace-slug]"),
]

# Usernames leak in more than paths: `ls -l` prints owner and group. Collect every
# name the paths reveal, then replace the bare token everywhere.
_USER_PAT = [
    re.compile(r"/mnt/efs/([A-Za-z0-9._-]+)"),
    re.compile(r"/(?:Users|home)/([A-Za-z0-9._-]+)"),
    re.compile(r"-Users-([A-Za-z0-9.-]+?)-scaleapi"),
]
_users = []


def learn_users(doc):
    found = set()
    for pat in _USER_PAT:
        for m in pat.finditer(doc):
            u = m.group(1)
            if u and u not in ("root", "src", "tmp"):
                found.add(u)
                found.add(u.replace("-", ""))
    _users.clear()
    _users.extend(sorted(found, key=len, reverse=True))
    return _users


# Applied last, once usernames are already placeholders: the dash-flattened
# workspace slug appears with either "rsi-run-" or "rsi-run_" and embeds the
# substituted [user] token, so it cannot be matched before that pass runs.
POST = [
    (re.compile(r"-?mnt-efs-[^\"\\\s]*?-rsi-sandboxes-rsi-run[-_][A-Za-z0-9]+(?:-workspace)?"), "[workspace-slug]"),
    (re.compile(r"-?(?:tmp|mnt|var)-[\w-]*?rsi-run[-_][A-Za-z0-9]+(?:-workspace)?"), "[workspace-slug]"),
]


def redact(s):
    for pat, rep in REDACT:
        s = pat.sub(rep, s)
    for u in _users:
        s = re.sub(rf"\b{re.escape(u)}\b", "[user]", s)
    for pat, rep in POST:
        s = pat.sub(rep, s)
    return s


def dedash(s):
    """Abril's copy rule: no em or en dashes in page copy. Verbatim artefacts are
    never passed through here."""
    s = re.sub(r"\s+[—–]\s+", ", ", s)
    s = re.sub(r"[—–]", ",", s)
    return s


# ---------------------------------------------------------------- chart data


def chart_titles(doc, aria):
    i = doc.find(f'aria-label="{aria}"')
    if i < 0:
        return []
    j = doc.find("</svg>", i)
    return [H.unescape(m.group(1)) for m in re.finditer(r"<title>([^<]+)</title>", doc[i:j])]


def parse_rounds(doc):
    """model -> {round: score} from the per-round line chart."""
    out = {}
    for s in chart_titles(doc, "held-out score per round, one line per model"):
        m = re.match(r"(.+?)\s+[—-]+\s+(?:after )?round (\d+):\s*([\d.]+)", s)
        if m:
            out.setdefault(m.group(1).strip(), {})[int(m.group(2))] = float(m.group(3))
    return out


# The same chart has shipped under two aria labels across campaign builds. Match
# both rather than the newer one, so an older sample still parses.
TOKEN_ARIA = ("held-out score against cumulative tokens spent",
              "held-out score against cumulative output tokens")


def parse_tokens(doc):
    """model -> {round: (score, cumulative_tokens)}."""
    out = {}
    titles = []
    for aria in TOKEN_ARIA:
        titles += chart_titles(doc, aria)
    for s in titles:
        m = re.match(
            r"(.+?)\s+[—-]+\s+after round (\d+):\s*([\d.]+)\s+at\s+([\d,]+)\s+cumulative", s
        )
        if m:
            out.setdefault(m.group(1).strip(), {})[int(m.group(2))] = (
                float(m.group(3)),
                int(m.group(4).replace(",", "")),
            )
    return out


def parse_anchors(doc):
    z = re.search(r"reward_zero\s*=\s*([\d.]+)", doc)
    o = re.search(r"reward_one\s*=\s*([\d.]+)", doc)
    return (float(z.group(1)) if z else None, float(o.group(1)) if o else None)


def inputs_block(file_cards):
    """What the solve container holds, and what is kept out of it.

    Both are stated by the solve Dockerfile itself: the COPY lines list what the model
    gets, and its header comment lists what is deliberately withheld. Reading them
    beats describing them, which is how the two could drift apart.
    """
    body = ""
    for det in file_cards:
        lab, _ = summary_bits(det)
        if lab.strip() == "Dockerfile":
            body = H.unescape(re.sub(r"<[^>]+>", "", body_of(det)))
            break
    if not body:
        return None
    given = []
    for m in re.finditer(r"^COPY\s+(\S+)\s", body, re.M):
        src = m.group(1)
        if src not in given:
            given.append(src)
    absent = ""
    m = re.search(r"Deliberately absent:(.*?)(?:\n\s*#\s*\n|\n[A-Z])", body, re.S)
    if m:
        absent = re.sub(r"\s*#\s*", " ", m.group(1))
        absent = re.sub(r"\s+", " ", absent).strip().rstrip(".")
    if not given:
        return None
    lst = "".join(f"<li><code>{esc(g)}</code></li>" for g in given)
    return f'<ul class="filelist">{lst}</ul>' 


def parse_metric(doc):
    """The metric name from task.toml, which is what keys the per-task defaults."""
    m = re.search(r'^\s*metric\s*=\s*["\']([^"\']+)["\']', H.unescape(doc), re.M)
    if m:
        raw = m.group(1)
        return {
            "tokens_per_1k_bytes": "tokens / 1000 bytes",
            "mean_regret": "mean regret",
        }.get(raw, raw.replace("_", " "))
    return "score"


def parse_task_id(doc, fallback):
    """The benchmark-style identifier the task ships under, from task.toml."""
    m = re.search(
        r"\[task\][^\[]*?\bname\s*=\s*[\"']([A-Za-z0-9._-]+)[\"']",
        H.unescape(doc),
        re.S,
    )
    return m.group(1) if m else fallback


def parse_limits(doc):
    out = {}
    for key in ("max_timeout", "attempts", "runtime_limit"):
        m = re.search(rf"{key}\s*=\s*(\d+)", doc)
        if m:
            out[key] = int(m.group(1))
    return out


def reward(score, z, o):
    if z is None or o is None or z == o:
        return None
    return max(0.0, min(1.0, (z - score) / (z - o)))


# ---------------------------------------------------------------- svg helpers

INK = "#111113"
INK2 = "#4B4B52"
INK3 = "#8A8A92"
RULE = "#E6E6EA"
PAPER = "#FAFAFA"
SURFACE = "#FFFFFF"

# Categorical hues from the validated reference palette, in a fixed order. Five
# series share one plot, so a reader compares non-adjacent pairs and the set was
# chosen against the ALL-PAIRS floors rather than the adjacent ones: the first five
# slots below measure worst-pair normal-vision OKLab dE 15.6 (>= 15 hard floor) and
# worst-pair CVD dE 7.6, which sits in the 6-8 band and so requires a second
# identity channel: every line is labelled at its end and each model is faceted.
# The palette's own default order (blue, orange, aqua, yellow, magenta) fails here,
# with orange vs yellow at 13.7 and orange vs magenta at 12.9.
#
# Colour is bound to the model, never to its rank, so a model keeps its hue across
# every chart and table and across tasks. See references/palette.md.
PALETTE = [
    "#2a78d6",  # blue
    "#4a3aa7",  # violet
    "#008300",  # green
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e34948",  # red
    "#eb6834",  # orange
    "#e87ba4",  # magenta
]
# Models seen so far keep a stable slot. Anything else takes the lowest free slot in
# name order, which is deterministic across rebuilds and across tasks.
# Slot 5, red, was measured against the five already in use before being pinned: it
# is the only candidate that clears the normal-vision floor (worst all-pairs OKLab dE
# 15.6, floor 15) while keeping the worst CVD pair highest at 6.8. Magenta passes the
# first test and drops CVD to 6.0; orange, slate and teal fail the floor outright.
MODEL_SLOT = {
    "Claude Opus 5": 0,
    "GPT-5.6-sol": 1,
    "Muse-Spark 1.2": 2,
    "Claude Sonnet 5": 3,
    "Claude Haiku 4.5": 4,
    "Grok 4.6": 5,
}
ROUND_SHADE = ["#C9C9CF", "#A1A1A9", "#75757D", "#4B4B52", "#111113"]
COLOURS = {}


def assign_colours(models, overrides=None):
    """name -> hex, stable for known models and deterministic for new ones."""
    COLOURS.clear()
    taken = set()
    for m in models:
        slot = MODEL_SLOT.get(m)
        if slot is not None and slot not in taken:
            COLOURS[m] = PALETTE[slot]
            taken.add(slot)
    free = [i for i in range(len(PALETTE)) if i not in taken]
    for m in sorted(x for x in models if x not in COLOURS):
        if free:
            i = free.pop(0)
        else:  # more series than hues: the palette cannot separate these
            i = len(taken) % len(PALETTE)
            print(f"  warning: {len(models)} models exceeds the {len(PALETTE)}-hue "
                  f"palette; {m} reuses a hue. Facet or drop a series instead.")
        COLOURS[m] = PALETTE[i]
        taken.add(i)
    for k, v in (overrides or {}).items():
        COLOURS[k] = v
    return COLOURS


def style_for(name):
    return COLOURS.get(name, PALETTE[0]), "none"


def colour_for(name):
    return COLOURS.get(name, PALETTE[0])


def esc(s):
    return H.escape(str(s), quote=True)


def log_ticks(lo, hi):
    """Nice-ish ticks for a log axis covering [lo, hi].

    Magnitudes run below 1: mean regret lives in [0.03, 0.13], and without the
    small decades this fell through to raw data values as tick labels.
    """
    cands = []
    mag = 1e-6
    while mag <= 1e6:
        for base in (1, 1.5, 2, 3, 5, 7):
            v = round(base * mag, 10)
            if lo <= v <= hi:
                cands.append(v)
        mag *= 10
    if len(cands) < 3:
        cands = [lo, (lo * hi) ** 0.5, hi]
    while len(cands) > 6:
        cands = cands[::2]
    return cands


def decade_ticks(lo, hi):
    """1, 2, 5 per decade, the ladder a reader already knows from a log axis. The
    1, 1.5, 2, 3, 5, 7 ladder used on the y axis is too dense for a span this wide
    and thins out to an unreadable 1.5, 3, 7, 15 when it is halved to fit."""
    out, mag = [], 1e-9
    while mag <= 1e12:
        for base in (1, 2, 5):
            v = base * mag
            if lo <= v <= hi:
                out.append(v)
        mag *= 10
    return out


def millions(v):
    """Tick labels for a token axis. A cheap run can start below a million, and
    "0.2M" is a worse label than "200k" for the same tick."""
    if v < 1e6:
        return f"{v/1e3:.0f}k"
    return f"{v/1e6:.1f}M"


def fmt(v):
    if v is None:
        return "n/a"
    return f"{v:.5g}"


def push_apart(labels, min_gap=13.0):
    """labels = [(y, *rest)] -> same tuples, nudged in y so none overlap."""
    labels = sorted(labels, key=lambda t: t[0])
    for i in range(1, len(labels)):
        y0 = labels[i - 1][0]
        if labels[i][0] - y0 < min_gap:
            labels[i] = (y0 + min_gap,) + tuple(labels[i][1:])
    return labels


def legend(names, ref_label=None):
    """Always present for two or more series; identity is never colour alone.

    The reference line is a legend entry rather than a label drawn on the plot: on
    the tokenizer task three models finish within a point of reward 0, so anything
    sitting on that rule collides with a series whichever side it is placed.
    """
    items = "".join(
        f'<span class="lg"><i style="background:{colour_for(n)}"></i>{esc(n)}</span>'
        for n in names or []
    )
    if ref_label:
        items += f'<span class="lg"><i class="dash"></i>{esc(ref_label)}</span>'
    return f'<div class="legend">{items}</div>'


def relabel(det):
    """Source captures label each attempt "Round N". The page calls it an iteration,
    which is the term the spec uses for this loop, so the row labels follow."""
    return re.sub(r">Round (\d+)<", r">Iteration \1<", det)


class _Md(HTMLParser):
    """Rendered markdown back to markdown.

    Six of the seven task-card files are shipped in the page as <pre> blocks and come
    back byte-exact. instruction.md is stored rendered, and no complete raw copy
    exists anywhere in the source (the trace captures of it all truncate at 1,800
    characters), so for the zip it is regenerated from the rendering.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.pre = False
        self.cell = None
        self.row = None
        self.rows = None

    def _w(self, t):
        if self.cell is not None:
            self.cell.append(t)
        else:
            self.out.append(t)

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._w("\n\n" + "#" * max(1, int(tag[1]) - 2) + " ")
        elif tag == "p":
            self._w("\n\n")
        elif tag == "br":
            self._w("\n")
        elif tag in ("strong", "b"):
            self._w("**")
        elif tag in ("em", "i"):
            self._w("*")
        elif tag == "code" and not self.pre:
            self._w("`")
        elif tag == "pre":
            self.pre = True
            self._w("\n\n```\n")
        elif tag in ("ul", "ol"):
            self._w("\n")
        elif tag == "li":
            self._w("\n- ")
        elif tag == "table":
            self.rows = []
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("strong", "b"):
            self._w("**")
        elif tag in ("em", "i"):
            self._w("*")
        elif tag == "code" and not self.pre:
            self._w("`")
        elif tag == "pre":
            self._w("\n```\n")
            self.pre = False
        elif tag in ("td", "th"):
            if self.row is not None and self.cell is not None:
                self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None
        elif tag == "tr":
            if self.rows is not None and self.row:
                self.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.rows:
            w = ["| " + " | ".join(r) + " |" for r in self.rows]
            sep = "| " + " | ".join("---" for _ in self.rows[0]) + " |"
            self.out.append("\n\n" + "\n".join([w[0], sep] + w[1:]) + "\n")
            self.rows = None

    def handle_data(self, d):
        if self.pre:
            self._w(d)
        elif d.strip() or d == " ":
            self._w(re.sub(r"\s+", " ", d))


def html_to_md(frag):
    p = _Md()
    p.feed(frag)
    out = "".join(p.out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip() + "\n"


def raw_file_text(det):
    """The file's own text, for the zip. A card that is one <pre> is verbatim."""
    body = body_of(det)
    # the tag carries attributes, so an unqualified <pre> never matched and every
    # file was routed through the markdown path and came out fenced
    pres = re.findall(r"<pre[^>]*>(.*?)</pre>", body, re.S)
    stripped = re.sub(r"<pre[^>]*>.*?</pre>", "", body, flags=re.S)
    if len(pres) == 1 and not re.search(r"<(p|h[1-6]|table|ul|ol)\b", stripped):
        return H.unescape(re.sub(r"<[^>]+>", "", pres[0]))
    return html_to_md(body)


TEXT_CAP = 80_000  # inline a file's contents up to here; larger ones ship in the zip


def task_files(task_dir):
    """Every file the task ships, from disk, in a stable order.

    The page previously showed only the seven files the sample HTML happened to
    embed. Reading the task directory means the task card and the bundle describe
    the same thing the environment actually contains.
    """
    if not task_dir or not os.path.isdir(task_dir):
        return []
    out = []
    for root, dirs, files in os.walk(task_dir):
        dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", ".git"))
        for fn in sorted(files):
            if fn == ".DS_Store":
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, task_dir)
            raw = open(full, "rb").read()
            text = None
            if len(raw) <= TEXT_CAP:
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = None
            out.append({"rel": rel, "size": len(raw), "text": text, "path": full})
    order = {"instruction.md": 0, "task.toml": 1}
    return sorted(out, key=lambda f: (order.get(f["rel"], 5), f["rel"]))


def write_bundle(out_path, task_dir, runs, summary_obj):
    """One zip beside the page: the whole task, the full trajectories, the summary.

    Built here rather than in the browser because a task directory can run to
    megabytes of fixtures, which is not something to embed in a page.
    """
    import zipfile

    name = os.path.splitext(os.path.basename(out_path))[0] + "-bundle.zip"
    path = os.path.join(os.path.dirname(os.path.abspath(out_path)) or ".", name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if task_dir and os.path.isdir(task_dir):
            for f in task_files(task_dir):
                z.write(f["path"], "task/" + f["rel"])
        for model, payload in runs.items():
            slug = re.sub(r"[^A-Za-z0-9.-]+", "-", model)
            z.writestr(f"trajectories/{slug}.json", payload)
        if summary_obj is not None:
            z.writestr("recursive-loop-summary.json", json.dumps(summary_obj, indent=1))
        entries = [(i.filename, i.file_size) for i in z.infolist()]
    return name, os.path.getsize(path), entries


def placeholder(label, what, fmt=""):
    """A visible gap in the page, so the layout can be reviewed before the content
    that fills it exists."""
    tail = f" Expected format: {fmt}." if fmt else ""
    return f'<div class="todo"><b>{esc(label)}</b>{what}{tail}</div>'


def load_summary(cfg):
    """The recursive loop summary: per model, per iteration, what was tried, what it
    scored, and the note carried in from the iteration before."""
    path = cfg.get("recursive_summary")
    if not path or not os.path.exists(path):
        return None
    return json.load(open(path, encoding="utf-8"))


def prose(txt):
    """Summary text back to markup. The notes are written as bullet lists, so a
    leading "- " becomes a list item and anything else a paragraph."""
    out, buf = [], []

    def flush():
        if buf:
            out.append("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in buf) + "</ul>")
            del buf[:]

    for line in (txt or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("- "):
            buf.append(line[2:])
        else:
            flush()
            out.append(f"<p>{esc(line)}</p>")
    flush()
    return "".join(out) or '<p class="none">Not recorded for this iteration.</p>'


def iteration_blocks(rows):
    """One closed row per iteration, opening onto the two recorded fields.

    The notes are unabridged, so laid out flat this ran to several screens per model.
    Closed rows give the whole run at a glance, iteration and reward, and the same
    disclosure the rest of the page uses.
    """
    out = []
    for r in rows:
        rew = r.get("reward")
        # three decimals, as the results table shows reward everywhere else
        tag = (f'<span class="tag">reward {rew:.3f}</span>' if rew is not None else "")
        out.append(
            '<details><summary><span class="grow">'
            f'Iteration {esc(r.get("iteration", ""))}</span>{tag}</summary>'
            '<div class="body ibody">'
            "<h4>Approach this iteration</h4>"
            + prose(r.get("turn_approach"))
            + "<h4>Notes carried in from the previous iteration</h4>"
            + prose(r.get("recursive_notes_prev_turn"))
            + "</div></details>"
        )
    return "".join(out)


def tree_lines(entries):
    """A directory tree of the bundle, built from the entries actually written to it,
    so the page cannot describe a zip it did not produce."""
    root = {}
    for name, size in entries:
        parts = name.split("/")
        node = root
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = size
    out = []

    def walk(node, prefix):
        items = sorted(node.items(), key=lambda kv: (not isinstance(kv[1], dict), kv[0]))
        for i, (k, v) in enumerate(items):
            last = i == len(items) - 1
            stem = "\u2514\u2500\u2500 " if last else "\u251c\u2500\u2500 "
            if isinstance(v, dict):
                out.append(f"{prefix}{stem}{k}/")
                walk(v, prefix + ("    " if last else "\u2502   "))
            else:
                out.append(f"{prefix}{stem}{k}  ({v:,} B)")

    walk(root, "")
    return out


def chip(name):
    """Model identity in a table cell: swatch plus the name in ink, never the name
    coloured, so the label survives any contrast or CVD condition."""
    return (
        f'<span class="mchip"><i style="background:{colour_for(name)}"></i>{esc(name)}</span>'
    )


# The direction of the metric, however a task happens to word it. Both delivered
# tasks are lower-is-better, but a higher-is-better task must mark its own sentence,
# so the phrasing is matched rather than assumed.
DIRECTION = re.compile(
    r"((?:Lower|Higher) values indicate better performance\.|"
    r"(?:Lower|Higher) is better\.)"
)


def mark_direction(text):
    """Escaped text with the direction sentence marked."""
    return DIRECTION.sub(r'<span class="dir">\1</span>', esc(text))


def mark_direction_html(frag):
    """The same, in a fragment that is already markup."""
    return DIRECTION.sub(r'<span class="dir">\1</span>', frag)


def figure(title, models, svg, caption="", ref_label=None, subtitle="",
           caption_html=""):
    head = f'<div class="fhead"><span class="ftitle">{esc(title)}</span>'
    if (models and len(models) > 1) or ref_label:
        head += legend(models, ref_label)
    if subtitle:
        head += f'<span class="fsub">{mark_direction(subtitle)}</span>'
    head += "</div>"
    body = caption_html or esc(caption)
    cap = f"<figcaption>{body}</figcaption>" if body else ""
    return f'<figure>{head}<div class="fbody">{svg}</div>{cap}</figure>'


def line_chart(series, ref, ref_label, y_label, x_label, x_ticks, aria, log=True,
               log_x=False):
    """series = [(name, [(x, y)])] in draw order; x in data units.

    log_x puts the x axis on a log scale, computes its own ticks and draws them as
    gridlines. Pass x_ticks=None with it.
    """
    import math

    W, Hh = 856, 380
    mr, mt, mb = 196, 14, 52
    xs = [p[0] for _, pts in series for p in pts]
    ys = [p[1] for _, pts in series for p in pts] + ([ref] if ref else [])
    x0, x1 = min(xs), max(xs)
    if x1 == x0:
        x1 = x0 + 1
    lo, hi = min(ys), max(ys)
    pad = (hi / lo) ** 0.06 if log else (hi - lo) * 0.06
    if log:
        lo, hi = lo / pad, hi * pad
        sy = lambda v: mt + (Hh - mt - mb) * (math.log(hi) - math.log(v)) / (
            math.log(hi) - math.log(lo)
        )
    else:
        lo, hi = lo - pad, hi + pad
        sy = lambda v: mt + (Hh - mt - mb) * (hi - v) / (hi - lo)

    ticks = log_ticks(lo, hi)
    ml = max(58, 18 + max((len(fmt(v)) for v in ticks), default=4) * 6.6)
    if log_x:
        # enough clearance that the first marker is not on the frame, and no more:
        # a wider pad pulls a spare tick a decade below the cheapest run into range
        xpad = (x1 / x0) ** 0.045
        x0, x1 = x0 / xpad, x1 * xpad
        lx0, lx1 = math.log(x0), math.log(x1)
        sx = lambda v: ml + (W - ml - mr) * (math.log(v) - lx0) / (lx1 - lx0)
        x_ticks = [(v, millions(v)) for v in decade_ticks(x0, x1)]
    else:
        sx = lambda v: ml + (W - ml - mr) * (v - x0) / (x1 - x0)

    o = [f'<svg viewBox="0 0 {W} {Hh}" width="100%" role="img" aria-label="{esc(aria)}">']
    # recessive grid, labels outside the plot
    for v in ticks:
        y = sy(v)
        o.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{W-mr}" y2="{y:.1f}" stroke="{RULE}"/>')
        o.append(f'<text x="{ml-11}" y="{y+3.5:.1f}" text-anchor="end" class="ax">{fmt(v)}</text>')
    for v, lab in x_ticks:
        # a log axis is unreadable without its own gridlines: the spacing between
        # ticks is the only cue that the scale is not linear
        if log_x:
            o.append(f'<line x1="{sx(v):.1f}" y1="{mt}" x2="{sx(v):.1f}" '
                     f'y2="{Hh-mb}" stroke="{RULE}"/>')
        o.append(
            f'<text x="{sx(v):.1f}" y="{Hh-mb+21}" text-anchor="middle" class="ax">{esc(lab)}</text>'
        )
    o.append(f'<line x1="{ml}" y1="{Hh-mb}" x2="{W-mr}" y2="{Hh-mb}" stroke="{INK3}"/>')
    # the x caption centres under its own axis; the y caption is rendered by the
    # figure head, where it can sit at the page's own text size
    o.append(
        f'<text x="{(ml + W - mr) / 2:.0f}" y="{Hh-6}" text-anchor="middle" '
        f'class="axl">{esc(x_label)}</text>'
    )
    if ref:
        y = sy(ref)
        o.append(
            f'<line x1="{ml}" y1="{y:.1f}" x2="{W-mr}" y2="{y:.1f}" stroke="{INK3}" '
            f'stroke-dasharray="5 4"/>'
        )
    labels = []
    for name, pts in series:
        col, dash = style_for(name)
        d = " ".join(
            ("M" if i == 0 else "L") + f"{sx(x):.1f} {sy(y):.1f}" for i, (x, y) in enumerate(pts)
        )
        da = f' stroke-dasharray="{dash}"' if dash != "none" else ""
        o.append(
            f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"{da}/>'
        )
        for i, (x, y) in enumerate(pts):
            o.append(
                f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4.5" fill="{col}" '
                f'fill-opacity="{0.35 + 0.65 * i / max(1, len(pts) - 1):.2f}" '
                f'stroke="{SURFACE}" stroke-width="2"><title>{esc(name)} round {i+1}: '
                f"{fmt(y)}</title></circle>"
            )
        labels.append((sy(pts[-1][1]), name, fmt(pts[-1][1]), col, False))
    # values and names wear text tokens; the swatch beside them carries identity
    # the reference joins the right-hand labels, so it is named beside its own rule
    # and nudged clear of the series labels by the same pass
    if ref:
        labels.append((sy(ref), "reward 0", fmt(ref), INK3, True))
    for y, name, val, col, dashed in push_apart(labels, 15.0):
        if dashed:
            swatch = (
                f'<line x1="{W-mr+10}" y1="{y:.1f}" x2="{W-mr+23}" y2="{y:.1f}" '
                f'stroke="{col}" stroke-width="2" stroke-dasharray="4 3"/>'
            )
        else:
            swatch = (
                f'<rect x="{W-mr+10}" y="{y-1.5:.1f}" width="13" height="3" rx="1.5" '
                f'fill="{col}"/>'
            )
        o.append(
            swatch
            + f'<text x="{W-mr+29}" y="{y+3.5:.1f}" class="sl">{esc(name)}</text>'
            + f'<text x="{W-6}" y="{y+3.5:.1f}" text-anchor="end" class="sv">{esc(val)}</text>'
        )
    o.append("</svg>")
    return "\n".join(o)


def panel_chart(rounds, ref, aria):
    """One facet per model, shared log scale. The facet is what makes a five-series
    plot legible for a reader who cannot separate two of the hues."""
    import math

    names = list(rounds.keys())
    cols = len(names)
    W, Hh = 856, 286
    gap = 12
    pw = (W - gap * (cols - 1)) / cols
    mt, mb = 46, 36
    ys = [v for r in rounds.values() for v in r.values()] + [ref]
    lo, hi = min(ys) / 1.08, max(ys) * 1.08
    sy = lambda v: mt + (Hh - mt - mb) * (math.log(hi) - math.log(v)) / (math.log(hi) - math.log(lo))
    o = [f'<svg viewBox="0 0 {W} {Hh}" width="100%" role="img" aria-label="{esc(aria)}">']
    for k, name in enumerate(names):
        ox = k * (pw + gap)
        col, _ = style_for(name)
        o.append(f'<rect x="{ox:.1f}" y="9" width="13" height="3" rx="1.5" fill="{col}"/>')
        o.append(f'<text x="{ox+19:.1f}" y="14" class="pt">{esc(name)}</text>')
        o.append(
            f'<line x1="{ox:.1f}" y1="{sy(ref):.1f}" x2="{ox+pw:.1f}" y2="{sy(ref):.1f}" '
            f'stroke="{INK3}" stroke-dasharray="5 4"/>'
        )
        rr = rounds[name]
        ks = sorted(rr)
        step = pw / (len(ks) + 1)
        pts = [(ox + step * (i + 1), sy(rr[r])) for i, r in enumerate(ks)]
        d = " ".join(("M" if i == 0 else "L") + f"{x:.1f} {y:.1f}" for i, (x, y) in enumerate(pts))
        o.append(
            f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
        )
        for i, (x, y) in enumerate(pts):
            o.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{col}" '
                f'fill-opacity="{0.35 + 0.65 * i / max(1, len(pts) - 1):.2f}" '
                f'stroke="{SURFACE}" stroke-width="2">'
                f"<title>{esc(name)} round {ks[i]}: {fmt(rr[ks[i]])}</title></circle>"
            )
            o.append(
                f'<text x="{x:.1f}" y="{Hh-mb+17}" text-anchor="middle" class="ax">r{ks[i]}</text>'
            )
        for idx in (0, len(ks) - 1):
            px, py = pts[idx]
            dy = -12 if abs(py - sy(ref)) > 12 or py > sy(ref) else 19
            o.append(
                f'<text x="{px:.1f}" y="{py+dy:.1f}" text-anchor="middle" '
                f'class="pv halo">{fmt(rr[ks[idx]])}</text>'
            )
        o.append(
            f'<line x1="{ox:.1f}" y1="{Hh-mb:.1f}" x2="{ox+pw:.1f}" y2="{Hh-mb:.1f}" '
            f'stroke="{RULE}"/>'
        )
    o.append("</svg>")
    return "\n".join(o)


# A plain statement of the measured quantity, per metric. The lifted originals
# explained the metric by contrast ("not the hit rate, the hit rate relative to a
# cache that could see the future"), which is harder to read than the thing itself.
def spell(k):
    return {1: "once", 2: "twice", 3: "three", 4: "four", 5: "five"}.get(k, str(k))


def methodology(limits, n_iter):
    """The RSI setup, which is the same for every task in this series. Every number
    comes from the task's own limits rather than from prose."""
    caps = []
    if "max_timeout" in limits:
        caps.append(f"its wall-clock limit of {limits['max_timeout']:,} seconds")
    if "attempts" in limits:
        caps.append(f"its cap of {limits['attempts']} graded submissions")
    # the limits are alternatives, not a conjunction: whichever binds first ends it
    cap_txt = " or ".join(caps) if caps else "a fixed budget"
    art = (
        f" The submitted artifact is separately capped at "
        f"{limits['runtime_limit']:,} seconds during grading."
        if "runtime_limit" in limits
        else ""
    )
    return (
        "<p>Each model is given a fixed time budget, a capped number of graded "
        "submissions, and an open-ended optimisation task. It carries out its own "
        "research and experimentation inside an isolated container with no network "
        "access, and submits a single artifact for grading.</p>"
        f"<p>The task is attempted {spell(n_iter)} times in sequence. Each iteration begins "
        "from the artifact the previous iteration submitted, together with that "
        "iteration's written record of what it tried and what it measured, so a run "
        "accumulates rather than restarts. Every model runs in its provider's standard "
        "agentic harness in long-running autonomous mode.</p>"
        f"<p>An iteration ends when it reaches {cap_txt}, whichever comes first.{art} "
        "The score is recomputed by the harness on a held-out split the model never "
        "sees, then mapped onto [0, 1] against two fixed anchors the model is not "
        "told.</p>"
    )

# Per-task prose. A config file overrides any of these; the dicts are defaults for
# tasks already built, keyed by the metric name found in task.toml. A metric with no
# entry falls back to a generated sentence, so an unseen task still produces a page.
ONELINE = {
    "mean regret": (
        "The model writes an online cache eviction policy, which is graded on held-out "
        "workloads spanning five traffic patterns at two cache sizes."
    ),
    "tokens / 1000 bytes": (
        "The model selects the 4,096 byte strings that make up a tokenizer vocabulary, "
        "which is graded on how many tokens it needs to encode held-out text."
    ),
}

# Work the environment was modelled on, linked from the task description.
CITATION = {
    "mean regret": (
        "https://www.usenix.org/system/files/fast21-rodriguez.pdf",
        "Rodriguez et al., <i>Learning Cache Replacement with CACHEUS</i>, "
        "USENIX FAST '21",
    ),
    "tokens / 1000 bytes": (
        "https://arxiv.org/abs/2503.13423",
        "Liu et al., <i>SuperBPE: Space Travel for Language Models</i>, COLM 2025, "
        "arXiv:2503.13423",
    ),
}

AXIS_LABEL = {
    "mean regret": "Mean regret, held-out split (log scale). Lower values indicate better performance.",
    "tokens / 1000 bytes": "Tokens per 1000 bytes, held-out split (log scale). Lower values indicate better performance.",
}

SCORED = {
    "mean regret": (
        "<p>The shortfall between the policy's hit rate and the best hit rate achievable "
        "on the same request stream at the same cache size, averaged across every "
        "workload type and cache size in the graded split. Lower is better.</p>"
    ),
    "tokens / 1000 bytes": (
        "<p>The number of tokens the vocabulary requires per 1000 bytes of previously "
        "unseen text. Encoding is performed by the harness, so submissions differ only "
        "in the strings they select. Lower is better.</p>"
    ),
}


# ---------------------------------------------------------------- shell

CSS = """
:root{
  --bg:#FAFAFA; --surface:#FFFFFF; --sunken:#F1F1F4;
  --text:#111113; --text-2:#4B4B52; --text-3:#8A8A92;
  --rule:#E6E6EA; --rule-2:#D8D8DE; --ink:#111113; --hover:#F4F4F7;
  --code-fg:#6D5AE6; --code-bg:#F1F1F4;
  --r:6px; --r-lg:8px;
  --display:"Aeonik",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,sans-serif;
  --ui:"Aeonik",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,"SF Mono",Menlo,monospace;
  --font:"Aeonik","Aeonik Medium","Inter",-apple-system,BlinkMacSystemFont,
    "Segoe UI",Helvetica,sans-serif;
  --col:1240px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font);
  font-weight:300;font-size:14.5px;line-height:1.6;font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased}
a{color:var(--text);text-decoration:underline;text-underline-offset:2px}
code,pre,.mono{font-family:var(--mono)}
code{color:var(--code-fg);background:var(--code-bg);padding:.1em .34em;border-radius:4px;
  font-size:.88em}
pre{background:var(--code-bg);border:1px solid var(--rule);border-radius:var(--r);
  padding:14px 16px;overflow-x:auto;font-size:12.5px;line-height:1.55;margin:12px 0}
pre code{background:none;padding:0;color:var(--text)}
hr{border:0;border-top:1px solid var(--rule);margin:22px 0}

/* ---------- chrome ---------- */
header{position:sticky;top:0;z-index:30;background:var(--surface);
  border-bottom:1px solid var(--rule-2)}
.hrow{max-width:var(--col);margin:0 auto;padding:0 32px;display:flex;
  align-items:stretch;gap:40px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px;align-self:center;flex:none;
  margin-right:8px}
.wm{font-family:var(--display);font-weight:500;font-size:21px;letter-spacing:.02em}
svg.scale{display:block;height:20px;width:20px;color:var(--ink)}
.hmeta{margin-left:auto;font-family:var(--mono);font-size:11.5px;
  letter-spacing:.01em;color:var(--text-3);align-self:center;white-space:nowrap}
.tabbar{display:flex;flex-wrap:wrap;gap:36px}
.tabbar button{font-family:var(--ui);font-size:17px;font-weight:400;
  letter-spacing:0;background:none;border:0;color:#9A9AA2;
  padding:17px 0 16px;cursor:pointer;transition:color .13s linear}
.tabbar button:hover{color:var(--text-2)}
.tabbar button[aria-selected="true"]{color:var(--text);font-weight:500}

main{max-width:var(--col);margin:0 auto;padding:40px 32px 40px}
footer{max-width:var(--col);margin:0 auto;padding:26px 32px 90px;
  border-top:1px solid var(--rule);font-family:var(--ui);font-size:10.5px;
  color:var(--text-3);line-height:1.75}

/* ---------- type ---------- */
h1{font-family:var(--display);font-weight:500;font-size:clamp(24px,2.5vw,31px);
  line-height:1.16;letter-spacing:-.015em;margin:0 0 8px}
.taskid{font-family:var(--mono);font-size:13.5px;color:var(--text-3);margin:0 0 8px}
.oneline{font-size:16px;color:var(--text-2);max-width:none;margin:0 0 32px}
.grule code,.taskid code{background:none;padding:0;color:var(--text-3)}
/* the reference sits between the summary paragraph and the detail below it, so it
   needs air on both sides or the three run together */
.cite{font-size:13.5px;color:var(--text-3);margin:18px 0 26px}
.col>.cite:last-child{margin-bottom:0}
.cite a{color:var(--text-2);text-decoration:underline;text-underline-offset:2px}
.cite i{font-style:italic}
/* the round table groups five iterations under one model: rules separate models,
   not iterations, so the grouping is legible */
table.rounds td{border-bottom:0}
table.rounds tr.grp td{border-top:1px solid var(--rule-2)}
table.rounds tbody tr:first-child td{border-top:0}
table.rounds tbody tr:last-child td{border-bottom:1px solid var(--rule)}
.grule{display:flex;justify-content:flex-start;margin:48px 0 0;padding-bottom:10px;
  border-bottom:1px solid var(--rule-2)}
.grule span{font-family:var(--ui);font-size:10px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--text-3)}
.grule code{font-size:13px}
.grule+.sec{margin-top:24px;border-top:0;padding-top:0}
.lead{font-size:16px;color:var(--text-2);max-width:76ch;margin:0 0 32px}
.sec{border-top:1px solid var(--rule);padding-top:24px;margin-top:48px}
.sec:first-of-type{margin-top:0;border-top:0;padding-top:0}

.sec>h2{font-family:var(--display);font-weight:500;font-size:clamp(17px,1.7vw,20px);
  margin:0 0 9px;letter-spacing:-.01em}
.sec .sub{color:var(--text-2);max-width:92ch;margin:0 0 24px}
.sec.split{display:grid;grid-template-columns:minmax(190px,230px) minmax(0,1fr);
  gap:8px 48px;align-items:start}
.sec.split>h2{margin:0;padding-top:1px}
.sec.split>.col{min-width:0}
.sec.split>.col>*:first-child{margin-top:0}
@media (max-width:900px){.sec.split{grid-template-columns:1fr;gap:8px}}
h3{font-family:var(--display);font-weight:500;font-size:17px;margin:32px 0 8px}
h4{font-family:var(--ui);font-weight:300;font-size:10px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--text-3);margin:24px 0 8px}
p{margin:0 0 12px;max-width:92ch}
ul,ol{max-width:92ch;padding-left:20px}
li{margin:3px 0}
strong{font-weight:500}

/* ---------- stat band ---------- */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  background:var(--surface);border:1px solid var(--rule-2);border-radius:var(--r-lg);
  margin:0 0 32px;overflow:hidden}
.stat{padding:16px 22px;border-left:1px solid var(--rule)}
.stat:first-child{border-left:0}
.stat .k{font-family:var(--ui);font-size:10px;text-transform:uppercase;
  letter-spacing:.09em;color:var(--text-3);display:block}
.stat .v{font-family:var(--display);font-weight:500;font-size:22px;display:block;
  margin-top:5px;line-height:1.1}
.stat .n{font-size:12.5px;color:var(--text-3);display:block;margin-top:4px}

/* ---------- tables ---------- */
.wrap-x{overflow-x:auto;margin:16px 0 24px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th{font-family:var(--ui);font-size:10px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--text-3);font-weight:300;text-align:left;padding:0 16px 9px 0;
  border-bottom:1px solid var(--ink);white-space:nowrap}
td{padding:10px 16px 10px 0;border-bottom:1px solid var(--rule);vertical-align:top}
tbody tr:hover td{background:var(--hover)}
td.n,th.n{text-align:right;font-family:var(--ui);font-size:12.5px}
th:last-child,td:last-child{padding-right:0}

/* ---------- key / value ---------- */
.kv{display:grid;grid-template-columns:max-content 1fr;gap:0 26px;margin:16px 0 26px;
  font-size:13.5px}
.kv dt{font-family:var(--ui);font-size:10px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--text-3);padding:10px 0;border-top:1px solid var(--rule)}
.kv dd{margin:0;padding:10px 0;border-top:1px solid var(--rule);color:var(--text-2)}

/* ---------- figures ---------- */
figure{margin:16px 0 32px;background:var(--surface);border:1px solid var(--rule-2);
  border-radius:var(--r-lg);overflow:hidden}
.fhead{display:flex;align-items:baseline;gap:20px;flex-wrap:wrap;
  padding:15px 20px 13px;border-bottom:1px solid var(--rule)}
.ftitle{font-family:var(--display);font-weight:500;font-size:14px}
.fsub{flex-basis:100%;font-size:13px;color:var(--text-3);margin-top:5px}
.dir,.key{font-weight:500;color:var(--text);background:var(--sunken);
  padding:1.5px 6px;border-radius:4px;white-space:nowrap}
.key{white-space:normal;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.fbody{padding:16px 20px 6px}
figcaption{font-size:13px;color:var(--text-2);padding:13px 20px 15px;
  border-top:1px solid var(--rule);max-width:none;line-height:1.55}
.legend{margin-left:auto;display:flex;flex-wrap:wrap;gap:15px;align-items:center}
.lg{font-family:var(--ui);font-size:10px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--text-2);display:inline-flex;align-items:center;gap:6px}
.lg i{width:13px;height:3px;border-radius:1.5px;display:inline-block}
.lg i.dash{height:0;border-radius:0;border-top:2px dashed var(--text-3);background:none}
svg{display:block;width:100%;height:auto}
svg text{font-family:var(--ui);fill:var(--text-3)}
svg .ax{font-size:10px}
svg .axl{font-size:10.5px;letter-spacing:.01em}
svg .sl{font-size:10.5px;fill:var(--text-2)}
svg .sv{font-size:10.5px;fill:var(--text)}
svg .ref{font-size:9.5px}
svg .pt{font-size:9.5px;letter-spacing:.07em;text-transform:uppercase;fill:var(--text-2)}
svg .pv{font-size:10px;fill:var(--text-2)}
svg .halo{paint-order:stroke;stroke:var(--surface);stroke-width:3.5px;stroke-linejoin:round}

/* a figure's own commentary: set in from the panel above it, so it reads as being
   about that figure without being boxed in with it */
.fnote{margin:0 0 32px;padding-left:18px;border-left:1px solid var(--rule-2)}
.fnote p{font-size:13.5px;color:var(--text-2);margin:0 0 11px}
.fnote p:last-child{margin-bottom:0}
.fnote .claim{color:var(--text);margin:0 0 6px}

/* ---------- model identity ---------- */
.mchip{display:inline-flex;align-items:center;gap:8px;white-space:nowrap}
.mchip i{width:11px;height:3px;border-radius:1.5px;flex:none}
.mgroup{margin:32px 0 0;padding-left:16px;border-left:3px solid var(--rule-2)}
.mgroup>h3{margin-top:0}
.mgroup .meta{font-family:var(--ui);font-size:10px;color:var(--text-3);
  text-transform:uppercase;letter-spacing:.06em;margin:0 0 12px}

/* ---------- disclosure ---------- */
details{border-top:1px solid var(--rule)}
details:last-of-type{border-bottom:1px solid var(--rule)}
summary{cursor:pointer;padding:13px 8px 13px 2px;list-style:none;display:flex;
  align-items:baseline;gap:16px;font-family:var(--ui);font-size:14px;font-weight:300;
  transition:background .13s linear}
summary code{font-family:var(--mono);font-size:13.5px}
summary::-webkit-details-marker{display:none}
summary::before{content:"+";color:var(--text-3);width:11px;flex:none}
details[open]>summary::before{content:"−"}
summary:hover{background:var(--hover)}
summary .grow{flex:1 1 auto;min-width:0}
summary .note{color:var(--text-3);font-size:11.5px;font-family:var(--font)}
summary .tag{font-family:var(--ui);font-size:10px;text-transform:uppercase;
  letter-spacing:.06em;color:var(--text-3);border:1px solid var(--rule-2);
  border-radius:var(--r);padding:2px 8px;flex:none}
.body{padding:8px 0 24px}
.body h3{font-family:var(--display);font-weight:500;font-size:16px;margin:24px 0 8px;
  text-transform:none;letter-spacing:0;color:var(--text)}
.body h4{font-family:var(--display);font-weight:500;font-size:14.5px;margin:24px 0 8px;
  text-transform:none;letter-spacing:0;color:var(--text)}
.body h3:first-child,.body h4:first-child{margin-top:6px}
.body p,.body li{font-size:13.5px}
.body table{font-size:13px}

/* ---------- trace events ---------- */
.ev{display:grid;grid-template-columns:92px 1fr;gap:16px;padding:10px 0;
  border-top:1px solid var(--rule)}
.ev .lbl{font-family:var(--ui);font-size:10px;text-transform:uppercase;
  letter-spacing:.07em;color:var(--text-3);padding-top:3px}
.ev pre{font-family:var(--mono);margin:0;background:none;border:0;padding:0;font-size:12.5px;
  white-space:pre-wrap;word-break:break-word}
.ev.say pre{font-family:var(--font);font-size:13.5px;color:var(--text)}
.ev.out pre{color:var(--text-2)}
.more{font-family:var(--ui);font-size:10px;color:var(--text-3);margin-top:6px}
.cw{min-width:0}
.cw.cl{position:relative}
.cw.cl>pre{max-height:150px;overflow:hidden}
.cw.cl:after{content:"";position:absolute;left:0;right:0;top:106px;height:44px;
  background:linear-gradient(to bottom,rgba(250,250,250,0),var(--bg));pointer-events:none}
.xp{font-family:var(--ui);font-size:10px;text-transform:uppercase;
  letter-spacing:.07em;color:var(--text-2);background:var(--surface);
  border:1px solid var(--rule-2);border-radius:var(--r);padding:4px 10px;cursor:pointer;
  margin-top:8px;position:relative;z-index:1;transition:background .13s linear,
  color .13s linear}
.xp:hover{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.filelist{list-style:none;padding:0;margin:16px 0 24px}
.filelist li{padding:2px 0}
.zipbtn{font-family:var(--ui);font-size:11px;text-transform:uppercase;
  letter-spacing:.07em;background:var(--ink);color:var(--surface);border:1px solid var(--ink);
  border-radius:var(--r);padding:8px 16px;cursor:pointer;margin:0 0 22px;
  transition:background .13s linear,color .13s linear}
.zipbtn:hover{background:var(--surface);color:var(--ink)}

/* ---------- iteration record ---------- */
.ibody{min-width:0;padding-bottom:22px}
.ibody>h4{font-family:var(--ui);font-weight:300;font-size:10.5px;
  text-transform:uppercase;letter-spacing:.08em;color:var(--text-3);margin:20px 0 7px}
.ibody>h4:first-child{margin-top:2px}
.ibody p,.ibody li{font-size:13.5px;color:var(--text-2);max-width:88ch}
.ibody ul{margin:0;padding-left:19px}
.ibody .none{color:var(--text-3)}

/* ---------- lead sentences in prose ---------- */
.claim{font-weight:500;color:var(--text);margin:26px 0 8px}
.col>.claim:first-child{margin-top:0}

/* ---------- bundle tree ---------- */
pre.tree{font-size:12px;line-height:1.55;color:var(--text-2)}

/* ---------- notices ---------- */
details.nofile>summary{cursor:default}
details.nofile>summary::before{content:"";width:11px}
.todo{border:1px dashed var(--rule-2);border-radius:var(--r);padding:16px 18px;
  margin:0 0 8px;background:var(--surface);color:var(--text-3);font-size:13.5px}
.todo b{display:block;font-family:var(--ui);font-size:10px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--text-2);font-weight:500;margin-bottom:6px}
.todo code{color:var(--code-fg)}
.btnrow{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:16px 0 24px}
.btnrow .zipbtn,.btnrow .btn2{margin:0}
.btn2{font-family:var(--ui);font-size:11px;text-transform:uppercase;
  letter-spacing:.07em;background:var(--surface);color:var(--text-2);
  border:1px solid var(--rule-2);border-radius:var(--r);padding:8px 16px;cursor:pointer;
  transition:background .13s linear,color .13s linear}
.btn2:hover{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.runbtn{font-family:var(--ui);font-size:10px;text-transform:uppercase;
  letter-spacing:.07em;background:var(--surface);color:var(--text-2);
  border:1px solid var(--rule-2);border-radius:var(--r);padding:4px 10px;cursor:pointer;
  margin-left:12px}
.runbtn:hover{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.rsum{margin:0 0 8px}
.rsum td{vertical-align:top}
.rsum td.ap{color:var(--text)}
.rsum td.nt{color:var(--text-2)}
.gap{background:var(--surface);border:1px solid var(--rule-2);
  border-left:3px solid var(--ink);border-radius:var(--r);padding:14px 18px;
  margin:18px 0;font-size:13.5px;color:var(--text-2)}
.gap b{font-family:var(--ui);font-size:10px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--text);display:block;margin-bottom:5px;font-weight:300}
section[hidden]{display:none}
@media (max-width:760px){
  .hrow,.tabbar,main,footer{padding-left:18px;padding-right:18px}
  .ev{grid-template-columns:1fr;gap:4px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

SCRIPT = """
var tabs=[].slice.call(document.querySelectorAll('.tabbar button'));
var secs=[].slice.call(document.querySelectorAll('section[data-tab]'));
function show(k){
  tabs.forEach(function(b){b.setAttribute('aria-selected',b.dataset.tab===k)});
  secs.forEach(function(s){s.hidden=s.dataset.tab!==k});
  try{history.replaceState(null,'','#'+k)}catch(e){}
  try{scrollTo(0,0)}catch(e){}}
tabs.forEach(function(b){b.onclick=function(){show(b.dataset.tab)}});
function esc(t){return String(t).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
// Tool output runs to hundreds of lines. Anything past LIM lines is clipped to a
// readable height with a control to open it, so a trace can be skimmed.
var LIM=9;
document.addEventListener('toggle',function(e){
  var d=e.target;
  if(!d.open||d.tagName!=='DETAILS'||!d.dataset.trace||d.dataset.done) return;
  d.dataset.done='1';
  var src=document.getElementById(d.dataset.trace);
  if(!src) return;
  var body=d.querySelector('.body'),out=[];
  JSON.parse(src.textContent).forEach(function(v){
    var more=v.m?'<div class="more">'+v.m.toLocaleString()+' more characters</div>':'';
    var lines=String(v.t).split('\\n').length;
    var clip=lines>LIM+4;
    out.push('<div class="ev '+v.k+'"><div class="lbl">'+esc(v.l)+'</div>'+
             '<div class="cw'+(clip?' cl':'')+'"><pre>'+esc(v.t)+'</pre>'+more+
             (clip?'<button class="xp" type="button" data-n="'+lines+
                   '">show all '+lines+' lines</button>':'')+'</div></div>');});
  body.innerHTML=out.join('');},true);

document.addEventListener('click',function(e){
  var b=e.target;
  if(b.classList&&b.classList.contains('xp')){
    var w=b.parentNode,open=w.classList.toggle('cl');
    b.textContent=open?('show all '+b.dataset.n+' lines'):'show less';
    return;}
  },true);
// Minimal store-only zip writer. The file contents are already in the page, so the
// download is assembled locally and the page keeps working offline.
var CRC=(function(){var t=[],c,i,j;for(i=0;i<256;i++){c=i;
  for(j=0;j<8;j++)c=(c&1)?(0xEDB88320^(c>>>1)):(c>>>1);t[i]=c>>>0;}return t;})();
function crc32(b){var c=0xFFFFFFFF;for(var i=0;i<b.length;i++)
  c=CRC[(c^b[i])&0xFF]^(c>>>8);return (c^0xFFFFFFFF)>>>0;}
function zipOf(files){
  var enc=new TextEncoder(),parts=[],central=[],off=0;
  files.forEach(function(f){
    var data=enc.encode(f.text),name=enc.encode(f.name),crc=crc32(data);
    var lh=new DataView(new ArrayBuffer(30));
    lh.setUint32(0,0x04034b50,true);lh.setUint16(4,20,true);
    lh.setUint32(14,crc,true);lh.setUint32(18,data.length,true);
    lh.setUint32(22,data.length,true);lh.setUint16(26,name.length,true);
    parts.push(new Uint8Array(lh.buffer),name,data);
    var cd=new DataView(new ArrayBuffer(46));
    cd.setUint32(0,0x02014b50,true);cd.setUint16(4,20,true);cd.setUint16(6,20,true);
    cd.setUint32(16,crc,true);cd.setUint32(20,data.length,true);
    cd.setUint32(24,data.length,true);cd.setUint16(28,name.length,true);
    cd.setUint32(42,off,true);
    central.push(new Uint8Array(cd.buffer),name);
    off+=30+name.length+data.length;});
  var cdSize=central.reduce(function(a,p){return a+p.length;},0);
  var eo=new DataView(new ArrayBuffer(22));
  eo.setUint32(0,0x06054b50,true);eo.setUint16(8,files.length,true);
  eo.setUint16(10,files.length,true);eo.setUint32(12,cdSize,true);
  eo.setUint32(16,off,true);
  return new Blob(parts.concat(central,[new Uint8Array(eo.buffer)]),
                  {type:'application/zip'});}
function traceFile(id){
  var el=document.getElementById(id);
  return el?el.textContent:'[]';}
function runJson(model){
  var idx=JSON.parse(document.getElementById('traceindex').textContent);
  var rows=(idx[model]||[]).slice().sort(function(a,b){return a.iter-b.iter;});
  return JSON.stringify({model:model,iterations:rows.map(function(r){
    return {iteration:r.iter,events:JSON.parse(traceFile(r.id))};})},null,1);}
document.addEventListener('click',function(e){
  var b=e.target;
  if(!b.classList) return;
  if(b.classList.contains('runbtn')){
    e.preventDefault();e.stopPropagation();
    save(new Blob([runJson(b.dataset.run)],{type:'application/json'}),b.dataset.name);}
  if(b.id==='sumbtn'){
    save(new Blob([document.getElementById('sumfile').textContent],
      {type:'application/json'}),b.dataset.name);}
},true);
function save(blob,name){
  var a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download=name;
  document.body.appendChild(a);a.click();
  setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},0);}
var zb=document.getElementById('zipbtn');
if(zb) zb.onclick=function(){
  var src=document.getElementById('zipfiles');
  var a=document.createElement('a');
  a.href=URL.createObjectURL(zipOf(JSON.parse(src.textContent)));
  a.download=zb.dataset.name;
  document.body.appendChild(a);a.click();
  setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},0);};

var want=location.hash.slice(1);
show(tabs.some(function(b){return b.dataset.tab===want})?want:tabs[0].dataset.tab);
"""

TABS = [
    ("overview", "Overview"),
    ("task", "Task card"),
    ("traj", "Trajectories"),
    ("perf", "Model performance"),
    ("loop", "Recursive loop"),
]


# ---------------------------------------------------------------- extraction


def model_groups(frag):
    """[(model_name, headline, [details_markup, ...]), ...].

    Walks only the top level: notes.md bodies contain their own <h3> headings, so
    splitting the section on every <h3> tears each model's rounds apart. Jumping
    over whole <details> blocks keeps nested headings invisible.
    """
    out, i, cur = [], 0, None
    h3 = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S)
    while i < len(frag):
        a = frag.find("<h3", i)
        b = frag.find("<details", i)
        if a < 0 and b < 0:
            break
        if b < 0 or (0 <= a < b):
            m = h3.match(frag, a) or h3.search(frag, a)
            if not m:
                break
            raw = text_of(m.group(1))
            mm = re.match(r"(.+?)\s*best\s+([\d.]+)\s*[·・]\s*(.+)$", raw)
            name = mm.group(1).strip() if mm else raw
            head = f"best {mm.group(2)}, {mm.group(3)}" if mm else ""
            cur = (name, head, [])
            out.append(cur)
            i = m.end()
        else:
            blk = balanced(frag, b)
            if cur is not None:
                cur[2].append(blk)
            i = b + len(blk)
    return out


def summary_bits(det):
    """(label, note) from a details' summary."""
    m = re.search(r"<summary>(.*?)</summary>", det, re.S)
    if not m:
        return "", ""
    spans = re.findall(r"<span[^>]*>(.*?)</span>", m.group(1), re.S)
    parts = [text_of(s) for s in spans] or [text_of(m.group(1))]
    return parts[0], " ".join(parts[1:])


def body_of(det):
    m = re.search(r'<div class="body">(.*)</div>\s*</details>\s*$', det, re.S)
    return m.group(1) if m else re.sub(r"^.*?</summary>", "", det, flags=re.S).rsplit("</details>", 1)[0]


ROLES = {
    "instruction.md": "The task text the agent is given when the container starts",
    "task.toml": "Task definition, scoring anchors and the three limits",
    "Dockerfile": "Solve container. Network off at run time; build asserts no leaks",
    "grade/Dockerfile": "Grading container. Self-checks determinism and anchor ordering",
    "rubrics.jsonl": "Trajectory rubrics, judged against the recorded session",
    "tests/test_verifier.py": "Hostile submissions the verifier must reject, honest ones it must accept",
    "tests/adversarial_cases.py": "Degenerate inputs every submission is fitted on before scoring",
    "grade/verify.py": "Submission gates, run before any score is computed",
    "grade/score.py": "Scorer entry point; maps the raw metric onto the reward scale",
    "grade/anchors.json": "The two reward endpoints and why each was chosen",
    "grade/recipe/": "Split construction, the reference table and the expert baselines",
    "solve/pack.py": "The simulator and metric, for local iteration",
    "solve/evaluate_dev.py": "Local scorer over the practice split. Raw metric only",
    "solve/dev_traces.json": "The practice split shipped with the container",
    "solve/seed_policy.py": "The starting implementation round 1 inherits",
    "solve/seed_vocab.py": "The starting implementation round 1 inherits",
    "starter/policy.py": "The starting implementation, copied to submission/ at build",
    "starter/vocab.py": "The starting implementation, copied to submission/ at build",
}


def manifest(doc, viewable):
    names = set(viewable)
    for m in re.finditer(r"^COPY\s+(\S+)\s+\S+", doc, re.M):
        names.add(m.group(1).lstrip("/"))
    for m in re.finditer(r'^\s*(?:instruction|dockerfile|grader|tests|rubrics|starting_impl)\s*=\s*"([^"]+)"', doc, re.M):
        names.add(m.group(1))
    for extra in ("grade/verify.py", "grade/score.py", "grade/anchors.json"):
        names.add(extra)
    return [(n, ROLES.get(n, "Shipped with the environment"), n in viewable) for n in sorted(names)]


# ---------------------------------------------------------------- build


def resolve_text(cfg, key, table, unit, fallback):
    """config value, then the per-metric default, then a generated fallback."""
    if cfg.get(key):
        return cfg[key]
    if table.get(unit):
        return table[unit]
    return fallback


def model_sentence(cfg, order):
    """The Model performance lead. Says which models are which only when told:
    inventing a SOTA split would be a claim the run data does not carry."""
    n_models = len(order)
    base = (
        f"Performance over {{iters}} iterations for each of {spell(n_models)} models."
    )
    sota = [m for m in cfg.get("sota_models", []) if m in order]
    comp = [m for m in cfg.get("comparison_models", []) if m in order]
    if not sota and not comp:
        comp = [m for m in order if m not in sota]
    parts = [base]
    if sota:
        verb = "candidate is" if len(sota) == 1 else "candidates are"
        parts.append(f"The SOTA {verb} {join_names(sota)}.")
    if sota and comp:
        parts.append(
            f"{join_names(comp)} "
            + ("forms" if len(comp) == 1 else "form")
            + " the non-SOTA comparison set."
        )
    parts.append(
        "Each iteration receives a summary of what the previous ones tried and "
        "scored, which is the mechanism the improvement rests on."
    )
    return " ".join(parts)


def join_names(xs):
    xs = list(xs)
    if len(xs) < 2:
        return xs[0] if xs else ""
    return ", ".join(xs[:-1]) + " and " + xs[-1]


def build(src_path, out_path, font_dir=None, cfg=None):
    cfg = cfg or {}
    if font_dir is None:
        here = os.path.dirname(os.path.abspath(__file__))
        cand = os.path.join(here, "fonts")
        font_dir = cand if os.path.isdir(cand) else None
    doc = read(src_path)
    learn_users(doc)
    title = text_of(re.search(r"<h1[^>]*>(.*?)</h1>", doc, re.S).group(1))
    lead_m = re.search(r"<h1[^>]*>.*?</h1>\s*<p[^>]*>(.*?)</p>", doc, re.S)
    lead = text_of(lead_m.group(1)) if lead_m else ""

    ov = section(doc, "overview")
    task = section(doc, "task")
    code = section(doc, "code")
    traces = section(doc, "traces")

    title = cfg.get("task_title") or title
    task_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    task_id = cfg.get("task_id") or parse_task_id(doc, task_slug)
    z, o = parse_anchors(doc)
    limits = parse_limits(doc)
    rounds = parse_rounds(doc)
    tokens = parse_tokens(doc)
    order = sorted(rounds, key=lambda m: min(rounds[m].values()))
    n_rounds = max((len(v) for v in rounds.values()), default=0)
    assign_colours(order, cfg.get("model_colours"))
    print(f"  {len(order)} models, {n_rounds} iterations: {', '.join(order)}")

    unit = cfg.get("metric") or parse_metric(doc)
    one_line = resolve_text(cfg, "one_line", ONELINE, unit, "")
    scoring = resolve_text(
        cfg, "scoring", SCORED, unit,
        f"<p>The task is scored on {esc(unit)}, measured on a held-out split. "
        "Lower is better.</p>",
    )
    axis_label = resolve_text(
        cfg, "axis_label", AXIS_LABEL, unit,
        f"{unit[:1].upper()}{unit[1:]}, held-out split (log scale). "
        "Lower values indicate better performance.",
    )
    citation = cfg.get("citation") or CITATION.get(unit)

    # --- files
    file_cards = details_blocks(task)
    viewable = []
    for det in file_cards:
        lab, _ = summary_bits(det)
        viewable.append(lab.strip())

    # --- per-round artifacts + notes, per model
    subs = {name: dets for name, _, dets in model_groups(code)}
    # --- traces, per model
    trs = {name: dets for name, _, dets in model_groups(traces)}
    payloads = re.findall(r'<script type="application/json" id="tr\d+">.*?</script>', doc, re.S)
    # model -> [{iter, id}], so the page can assemble a whole run or a full bundle
    trace_index = {}
    trace_text = dict(
        re.findall(
            r'<script type="application/json" id="(tr\d+)">(.*?)</script>', doc, re.S
        )
    )
    for name, _, dets in model_groups(traces):
        for det in dets:
            mid = re.search(r'data-trace="(tr\d+)"', det)
            lab, _note = summary_bits(det)
            it = re.search(r"(\d+)", lab)
            if mid and it:
                trace_index.setdefault(name, []).append(
                    {"iter": int(it.group(1)), "id": mid.group(1)}
                )
    # one full-stream document per model, for the bundle
    runs = {}
    for model, items in trace_index.items():
        runs[model] = json.dumps(
            {
                "model": model,
                "iterations": [
                    {
                        "iteration": it["iter"],
                        "events": json.loads(trace_text.get(it["id"], "[]")),
                    }
                    for it in sorted(items, key=lambda x: x["iter"])
                ],
            },
            indent=1,
        )

    # --- candidates per model/round from the submission summaries
    cands = {}
    for name, dets in subs.items():
        for det in dets:
            lab, note = summary_bits(det)
            rn = re.search(r"Round (\d+)", lab)
            cm = re.search(r"(\d+)\s+candidates", note)
            if rn:
                cands.setdefault(name, {})[int(rn.group(1))] = int(cm.group(1)) if cm else None

    bundle_name = bundle_size = None
    bundle_entries = []
    if cfg.get("task_dir") or runs:
        bundle_name, bundle_size, bundle_entries = write_bundle(
            out_path, cfg.get("task_dir"), runs, load_summary(cfg)
        )
        print(f"  bundle {bundle_name}  {bundle_size:,} bytes")

    P = []
    a = P.append

    # ============ 01 overview
    ovb = dict(h_blocks(ov, "h3"))
    a('<section data-tab="overview">')
    a(f"<h1>{esc(title)}</h1>")
    a(f'<p class="taskid">{esc(task_id)}</p>')
    if one_line:
        a(f'<p class="oneline">{esc(one_line)}</p>')
    best = order[0]
    span = rounds[best]
    a('<div class="stats">')
    a(f'<div class="stat"><span class="k">Models</span><span class="v">{len(order)}</span>'
      f'<span class="n">{n_rounds} runs each</span></div>')
    a(f'<div class="stat"><span class="k">Best result</span><span class="v">{fmt(min(span.values()))}</span>'
      f'<span class="n">{esc(best)}</span></div>')
    a(f'<div class="stat"><span class="k">Reward 0</span><span class="v">{fmt(z)}</span></div>')
    a("</div>")
    # Render whatever blocks the source overview has, in its order, with two
    # substitutions: the metric gets a plain statement, and the block describing the
    # loop is replaced by one sentence. The source version of that block was a table
    # of labels (isolation, control, what carries over) that explained the loop by
    # listing its parts.
    # Methodology describes the RSI setup and is identical for every task in the
    # series. A labelled rule then marks where the task-specific material starts, so a
    # reader can tell which parts generalise and which describe this environment.
    def block_html(heading, body_html):
        return (
            f'<div class="sec split"><h2>{esc(heading)}</h2>'
            f'<div class="col">{body_html}</div></div>'
        )

    a(block_html("Methodology", methodology(limits, n_rounds)))

    task_blocks = []
    for h, block in h_blocks(ov, "h3"):
        low = h.lower()
        if low.startswith("what is scored"):
            task_blocks.append(("Scoring", mark_direction_html(scoring)))
        elif low.startswith("how the chain is run"):
            continue  # covered by Methodology
        elif low.startswith("the problem"):
            body_html = balance_html(dedash(block))
            cite = citation
            if cite:
                body_html += (
                    f'<p class="cite">Motivation: '
                    f'<a href="{cite[0]}" target="_blank" rel="noreferrer">{cite[1]}</a></p>'
                )
            detail = cfg.get("task_detail")
            if detail:
                body_html += detail
            task_blocks.append(("Task description", body_html))
        else:
            task_blocks.append((h, balance_html(dedash(block))))
    a(f'<div class="grule"><code>{esc(task_id)}</code></div>')
    ib = inputs_block(file_cards)
    for heading, body_html in task_blocks:
        a(block_html(heading, body_html))
        if heading == "Task description" and ib:
            a(block_html("Inputs", ib))
    a(block_html(
        "Why the task is hard",
        cfg.get("why_hard")
        or placeholder(
            "To provide",
            "A task-level explanation of what makes this hard, written for a reader "
            "who has not seen the environment. The instruction file's own difficulty "
            "section is a starting point.",
            "one or two paragraphs, config key <code>why_hard</code>",
        ),
    ))
    # results summary
    a('<div class="sec split"><h2>Results</h2><div class="col">')
    a(f'<p class="sub">Scored on the held-out split in {esc(unit)}, '
      f'<span class="dir">lower is better</span>. '
      f'Reward maps the measurement onto [0, 1] against two fixed anchors the agent is not told.</p>')
    a('<div class="wrap-x"><table><thead><tr><th>Model</th>'
      f'<th class="n">Iteration 1</th><th class="n">Iteration {n_rounds}</th>'
      '<th class="n">Best</th><th class="n">Reward, best</th>'
      '<th class="n">Improvement</th></tr></thead><tbody>')
    for m_ in order:
        r = rounds[m_]
        b = min(r.values())
        d = (r[1] - r[max(r)]) / r[1] * 100 if r.get(1) else 0
        a(f"<tr><td>{chip(m_)}</td><td class='n'>{fmt(r[1])}</td><td class='n'>{fmt(r[max(r)])}</td>"
          f"<td class='n'>{fmt(b)}</td><td class='n'>{reward(b,z,o):.3f}</td>"
          f"<td class='n'>{d:.1f}%</td></tr>")
    a("</tbody></table></div></div></div>")
    a("</section>")

    # ============ 02 task card
    a('<section data-tab="task" hidden>')
    a('<div class="sec split"><h2>Task card</h2><div class="col">')
    a('<div class="kv">')
    if "max_timeout" in limits:
        a(f'<dt>Session wall clock</dt><dd>{limits["max_timeout"]:,} s</dd>')
    if "attempts" in limits:
        a(f'<dt>Graded submissions per session</dt><dd>{limits["attempts"]}</dd>')
    if "runtime_limit" in limits:
        a(f'<dt>Artifact runtime at grading</dt><dd>{limits["runtime_limit"]:,} s</dd>')
    a(f'<dt>Reward 0</dt><dd>{fmt(z)} (a typical from-scratch session)</dd>')
    a(f'<dt>Reward 1</dt><dd>{fmt(o)}</dd>')
    a("</div>")
    disk_files = task_files(cfg.get("task_dir"))
    a('<div class="btnrow">')
    if bundle_name:
        # With bundle_url set, the page carries an absolute link to a hosted copy and
        # is then a single self-sufficient file: nothing has to sit beside it. The
        # download attribute is ignored cross-origin, so a hosted bundle opens in its
        # own tab and the browser saves it on the strength of its content type, which
        # for a zip it always does.
        remote = cfg.get("bundle_url")
        href = remote or bundle_name
        attrs = ' target="_blank" rel="noreferrer"' if remote else " download"
        a(f'<a class="zipbtn" href="{esc(href)}"{attrs}>'
          f"Download full task (zip, {bundle_size/1e6:.1f} MB)</a>")
    a(f'<button class="btn2" id="zipbtn" type="button" '
      f'data-name="{esc(task_id)}-task-files.zip">Text files only (zip)</button>')
    a("</div>")
    if bundle_name:
        inline = sum(1 for f in disk_files if f["text"] is not None)
        a(f'<p class="sub">The bundle holds the complete task directory '
          f'({len(disk_files)} files), every trajectory as an unabridged stream, and '
          f'the recursive loop summary. {inline} of those files are also readable '
          f'below; the rest are data and fixtures.</p>')
    if bundle_entries:
        a("<h3>What is in the bundle</h3>")
        tot = sum(sz for _, sz in bundle_entries)
        a(f'<p class="sub">{len(bundle_entries)} files, {tot/1e6:.1f} MB uncompressed. '
          f'<code>task/</code> is the environment exactly as the models received it, '
          f'<code>trajectories/</code> holds one file per model containing all '
          f'{n_rounds} of its iterations turn by turn, and the summary is the '
          f'iteration record shown on the recursive loop tab.</p>')
        a(f'<pre class="tree">{esc(bundle_name)}\n'
          + esc("\n".join(tree_lines(bundle_entries)))
          + "</pre>")
    if disk_files:
        for f in disk_files:
            tag = f"{f['size']:,} B"
            if f["text"] is None:
                a(f'<details class="nofile"><summary><span class="grow">'
                  f'<code>{esc(f["rel"])}</code></span>'
                  f'<span class="note">in the bundle</span>'
                  f'<span class="tag">{esc(tag)}</span></summary></details>')
            else:
                a(f'<details><summary><span class="grow"><code>{esc(f["rel"])}</code>'
                  f'</span><span class="tag">{esc(tag)}</span></summary>'
                  f'<div class="body"><pre>{esc(redact(f["text"]))}</pre></div>'
                  "</details>")
    else:
        for det in file_cards:
            lab, note = summary_bits(det)
            parts = note.rsplit(" ", 2)
            tag = " ".join(parts[-2:]) if len(parts) >= 2 and parts[-1] == "B" else ""
            a(f'<details><summary><span class="grow"><code>{esc(lab)}</code></span>'
              f'<span class="tag">{esc(tag)}</span></summary>'
              f'<div class="body">{balance_html(redact(body_of(det)))}</div></details>')
    a("</div></div></section>")

    # ============ 03 trajectories
    a('<section data-tab="traj" hidden>')
    a('<div class="sec split"><h2>Trajectories</h2><div class="col">')
    a('<p class="sub">Every iteration of every run, recorded turn by turn. Long tool '
      'outputs are clipped to a readable height with a control to open them, and the '
      'longest are truncated in the capture itself. Each iteration can be downloaded as '
      'JSON. Infrastructure paths are replaced with labelled placeholders; nothing else '
      'is altered.</p>')
    missing = [m_ for m_ in order if not trs.get(m_)]
    if missing:
        a('<div class="gap"><b>Open gap</b>No trajectories were captured for '
          + esc(", ".join(missing))
          + ". Their scores appear in Model performance; their sessions are not on this page.</div>")
    for m_ in order:
        dets = trs.get(m_) or []
        if not dets:
            continue
        r = rounds[m_]
        slug = re.sub(r"[^a-z0-9]+", "-", m_.lower()).strip("-")
        a(f'<div class="mgroup" style="border-left-color:{colour_for(m_)}">'
          f'<h3>{esc(m_)}<button class="runbtn" type="button" data-run="{esc(m_)}" '
          f'data-name="{esc(task_slug)}-{slug}-run.json">download run json</button></h3>'
          f'<p class="meta">best {fmt(min(r.values()))}</p>')
        for det in dets:
            a(balance_html(redact(relabel(det))))
        a("</div>")
    a("</div></div></section>")

    # ============ 04 model performance
    a('<section data-tab="perf" hidden>')
    a('<div class="sec split"><h2>Model performance</h2><div class="col">')
    a(f'<p class="sub">'
      + esc(model_sentence(cfg, order).replace("{iters}", spell(n_rounds)))
      + "</p>")

    ser = [(m_, [(k, rounds[m_][k]) for k in sorted(rounds[m_])]) for m_ in order]
    a(figure(
        "Performance over iterations", order,
        line_chart(ser, z, f"reward 0, {fmt(z)}",
                   axis_label, "Iteration",
                   [(k, str(k)) for k in sorted(rounds[order[0]])],
                   "held-out score per round, one line per model"),
        subtitle=axis_label))

    if tokens:
        ser2 = []
        for m_ in order:
            pts = [(tokens[m_][k][1], tokens[m_][k][0]) for k in sorted(tokens.get(m_, {}))]
            if pts:
                ser2.append((m_, pts))
        a(figure(
            "Performance over cumulative tokens", [m for m, _ in ser2],
            line_chart(ser2, z, f"reward 0, {fmt(z)}",
                       axis_label,
                       "Cumulative tokens, log scale", None,
                       "held-out score against cumulative tokens spent",
                       log_x=True),
            caption_html="A run that ends early on this axis spent less, "
                         "<strong>not necessarily scored worse</strong>: horizontal "
                         "extent is cost and vertical position is score.",
            subtitle=axis_label))
        # the reading of this figure, which is the one chart on the page whose x axis
        # is a cost rather than a step count and is therefore the easiest to misread
        if cfg.get("token_note"):
            a(f'<div class="fnote">{cfg["token_note"]}</div>')

    a(figure(
        "Iteration by iteration", None,
        panel_chart({m_: rounds[m_] for m_ in order}, z,
                    "per-model round-by-round detail"),
        ref_label=f"reward 0, {fmt(z)}", subtitle=axis_label))

    a('<div class="wrap-x"><table class="rounds"><thead><tr><th>Model</th>'
      '<th class="n">Iteration</th>'
      f'<th class="n">{esc(unit)}</th><th class="n">Reward</th>'
      '<th class="n">Candidates measured</th></tr></thead><tbody>')
    for m_ in order:
        for k in sorted(rounds[m_]):
            c = (cands.get(m_) or {}).get(k)
            # a rule is drawn above the first iteration of each model, not between
            # iterations, so the five-row block reads as one model
            grp = ' class="grp"' if k == 1 else ""
            a(f"<tr{grp}>"
              f"<td>{chip(m_) if k==1 else ''}</td><td class='n'>{k}</td>"
              f"<td class='n'>{fmt(rounds[m_][k])}</td>"
              f"<td class='n'>{reward(rounds[m_][k],z,o):.3f}</td>"
              f"<td class='n'>{c if c is not None else 'n/a'}</td></tr>")
    a("</tbody></table></div>")

    a("<h3>Where the models fail</h3>")
    a(cfg.get("failure_analysis") or placeholder(
        "To provide",
        "The failure pattern shared across models, then one line per model saying "
        "where its run stalled and on what. Iteration-level detail already lives in "
        "each iteration's notes below.",
        "short prose, config key <code>failure_analysis</code>",
    ))

    a("<h3>Output for each run</h3>")
    a('<p class="sub">The artifact each round submitted, as it was graded, and the notes it '
      'passed to the next round.</p>')
    for m_ in order:
        dets = subs.get(m_) or []
        a(f'<div class="mgroup" style="border-left-color:{colour_for(m_)}">'
          f'<h3>{esc(m_)}</h3>')
        if not dets:
            a('<div class="gap"><b>Open gap</b>No artifacts or notes were captured for this '
              "model.</div></div>")
            continue
        for det in dets:
            a(balance_html(redact(relabel(det))))
        a("</div>")
    a("</div></div></section>")

    # ============ 05 recursive loop
    a('<section data-tab="loop" hidden>')
    a('<div class="sec split"><h2>Recursive loop summary</h2><div class="col">')
    a(f'<p class="sub">The iteration record for every run: what each iteration tried, '
      f'what it scored, and the note it inherited from the iteration before it. That '
      f'inherited note is the only thing besides the artifact that crosses between '
      f'iterations, so it is what makes a run of {spell(n_rounds)} cumulative rather '
      f'than {spell(n_rounds)} independent attempts.</p>')
    rsum = load_summary(cfg)
    if rsum:
        per_model = rsum.get("recursive_loop_summary", {})
        a('<div class="btnrow">'
          '<button class="btn2" id="sumbtn" type="button" '
          f'data-name="{esc(task_id)}-recursive-loop-summary.json">'
          "Download the record (json)</button></div>")
        for m_ in order:
            rows = per_model.get(m_) or per_model.get(m_.lower().replace(" ", "-"))
            if not rows:
                continue
            rows = sorted(rows, key=lambda r: r.get("iteration") or 0)
            a(f'<div class="mgroup" style="border-left-color:{colour_for(m_)}">'
              f"<h3>{esc(m_)}</h3>{iteration_blocks(rows)}</div>")
        missing = [
            m_ for m_ in order
            if not (per_model.get(m_) or per_model.get(m_.lower().replace(" ", "-")))
        ]
        if missing:
            a(placeholder("Not in the summary file", esc(", ".join(missing)) + "."))
    else:
        a(placeholder(
            "To provide",
            "The recursive loop summary file. One entry per model per iteration with "
            "the iteration number, the reward, the approach that iteration tried, and "
            "the note handed forward from the previous one.",
            "<code>recursive_loop_summary</code> json, config key "
            "<code>recursive_summary</code>",
        ))
    a("</div></div></section>")

    zip_json = json.dumps(
        [
            {"name": summary_bits(d)[0].strip(), "text": redact(raw_file_text(d))}
            for d in file_cards
        ]
    )
    rsum_now = load_summary(cfg)
    summary_payload = (
        '<script type="application/json" id="sumfile">'
        + json.dumps(rsum_now)
        + "</script>"
        if rsum_now
        else ""
    )
    body = "\n".join(P)
    nav = "".join(
        f'<button data-tab="{k}" aria-selected="{"true" if i==0 else "false"}">{esc(lab)}</button>'
        for i, (k, lab) in enumerate(TABS)
    )
    out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>{font_faces(font_dir)}
{CSS}</style>
</head>
<body>
<header>
  <div class="hrow"><span class="brand"><span class="wm">RSI</span><svg class="scale" viewBox="0 0 24 24" role="img" aria-label="Scale"><path d="M4 4H20V20Z" fill="currentColor" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/><path d="M3.4 15H9.5V21.1Z" fill="currentColor" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/></svg></span>
    <nav class="tabbar">{nav}</nav>
    <span class="hmeta">{esc(task_id)}</span></div>
</header>
<main>
{body}
</main>
{''.join(redact(p) for p in payloads)}
<script type="application/json" id="zipfiles">{zip_json}</script>
<script type="application/json" id="traceindex">{json.dumps(trace_index)}</script>
{summary_payload}
<script>{SCRIPT}</script>
</body>
</html>
"""
    open(out_path, "w", encoding="utf-8").write(out)
    return out_path, len(out)


def check(path):
    """Load the page in headless Chrome and assert each tab actually opens.

    A generator that emits JavaScript can break the page silently: one bad string
    escape once killed the whole script, leaving only the first tab reachable and
    everything else invisible. This is the check that catches it.
    """
    import shutil
    import subprocess

    chrome = next(
        (
            c
            for c in (
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                shutil.which("google-chrome"),
                shutil.which("chromium"),
            )
            if c and os.path.exists(c)
        ),
        None,
    )
    if not chrome:
        print("  check skipped: no Chrome found")
        return True
    ok = True
    for tab, _ in TABS:
        out = subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--virtual-time-budget=2500",
             "--dump-dom", f"file://{os.path.abspath(path)}#{tab}"],
            capture_output=True, text=True,
        ).stdout
        vis = re.findall(r'<section data-tab="([a-z]+)"(?![^>]*hidden)', out)
        if vis != [tab]:
            print(f"  FAIL tab {tab}: visible sections {vis}")
            ok = False
    print(f"  tabs: all {len(TABS)} open" if ok else "  tabs: BROKEN, check the page script")
    return ok


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    def flag(name, default=None):
        for f in flags:
            if f.startswith(f"--{name}="):
                return f.split("=", 1)[1]
        return default

    cfg_path = flag("config")
    cfg = json.load(open(cfg_path, encoding="utf-8")) if cfg_path else {}
    src = args[0] if args else cfg.get("source")
    out = flag("out") or (args[1] if len(args) > 1 else cfg.get("out"))
    if not src or not out:
        print(__doc__)
        sys.exit(2)
    p, size = build(src, out, flag("fonts"), cfg)
    print(f"wrote {p}  {size:,} bytes")
    if "--check" in flags:
        sys.exit(0 if check(p) else 1)
