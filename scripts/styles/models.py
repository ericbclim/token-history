#!/usr/bin/env python3
"""Model-level breakdown charts.

charts/model/bar-tokens.svg   one horizontal bar per model, colored by the tool
                              that ran it, sorted by total tokens
charts/model/monthly.svg      monthly stacked bars split by model, so a model
                              that dominated a stretch of months is visible

The upstream charts aggregate by TOOL (Claude Code, Kilo Code, ...). The data
already carries a second dimension — `sources.<tool>.models.<model>.total` — and
this plugin surfaces it: which MODELS actually did the work, and when. A model
like `mimo-v2.5-pro` can be a third of all tokens while being invisible in a
per-tool chart, because it ran inside a tool that also ran other models.

Deterministic: colors are assigned by model rank (total desc, name tiebreak), so
the same data yields byte-identical SVG and both charts agree on a model's color.
Python 3.9, stdlib only; `import render` works when cwd is the repo's scripts/.
"""

import datetime as dt

import render

# A qualitative model palette, deliberately distinct from the tool palette so a
# model color never reads as "this is Claude Code". Index = rank (biggest model
# gets mm0). Cycled if there are more models than slots; the legend always names
# every model, so identity is never color-alone.
MODEL_PALETTE = {
    "light": ["#7a5ea8", "#1f8a70", "#b23a6b", "#8a6d1f", "#a24b3a", "#3f7d3f",
              "#5a5a8c", "#c07a1f", "#2f8a8a", "#8a3f7d", "#6b7a1f", "#3f5f9c"],
    "dark": ["#9b82c9", "#34b39a", "#d65c92", "#c2a24a", "#cf7a5f", "#6fb36f",
             "#8f8fc2", "#e0a44a", "#5bc2c2", "#c26fb0", "#a3b34a", "#6f8fd0"],
}
MAX_LEADERBOARD = 16      # rows shown on the leaderboard before "N more"
MAX_MONTH_STACKS = 8      # distinct models in the monthly stack, rest -> Other


def _collect(days):
    """Aggregate model totals, their dominant tool, and a per-month matrix."""
    total = {}                       # model -> tokens
    by_src = {}                      # model -> {source: tokens}
    per_month = {}                   # (model, "YYYY-MM") -> tokens
    months = set()
    for date in sorted(days):
        rec = days[date]
        mo = date[:7]
        months.add(mo)
        for source, payload in rec.items():
            if source == "partial" or not isinstance(payload, dict):
                continue
            for model, mp in (payload.get("models") or {}).items():
                t = mp.get("total") or 0
                if not t:
                    continue
                total[model] = total.get(model, 0) + t
                by_src.setdefault(model, {})
                by_src[model][source] = by_src[model].get(source, 0) + t
                per_month[(model, mo)] = per_month.get((model, mo), 0) + t
    return total, by_src, per_month, sorted(months)


def _ranked(total):
    """Models sorted by total desc, name asc for a stable deterministic order."""
    return sorted(total, key=lambda m: (-total[m], m))


def _dominant_source(by_src, model):
    return max(by_src[model].items(), key=lambda kv: kv[1])[0]


def _model_css(models):
    """Per-model fill classes for both color schemes, keyed by rank."""
    light, dark = MODEL_PALETTE["light"], MODEL_PALETTE["dark"]

    def vars_for(pal):
        return "".join("--mm{}:{};".format(i, pal[i % len(pal)]) for i in range(len(models)))

    css = "svg{" + vars_for(light) + "--mm-other:var(--muted);}"
    css += "@media (prefers-color-scheme:dark){svg{" + vars_for(dark) + "--mm-other:var(--muted);}}"
    css += "".join(".mm{}{{fill:var(--mm{})}}".format(i, i) for i in range(len(models)))
    css += ".mm-other{fill:var(--mm-other)}"
    return css


# ------------------------------------------------------------- leaderboard

def _build_leaderboard(days, generated):
    total, by_src, _, _ = _collect(days)
    if not total:
        return None
    ranked = _ranked(total)
    shown = ranked[:MAX_LEADERBOARD]
    grand = sum(total.values())

    header, row_h, foot = 118, 26, 42
    label_x, bar_x = 28, 300
    value_x = render.W - 28
    bar_w_max = value_x - 150 - bar_x
    bar_h = 13
    h = header + len(shown) * row_h + foot

    span = "{} – {}".format(min(days), max(days))
    title = "Tokens by model"
    subtitle = "{} · {} models · {} tokens".format(
        span, len(total), render.compact_tokens(grand))

    out = render.svg_start(render.W, h, title)
    add = out.append
    add('<text class="ts" x="{}" y="32" font-size="20" font-style="italic">{}</text>'.format(label_x, render.esc(title)))
    add('<text class="t2" x="{}" y="52" font-size="12">{}</text>'.format(label_x, render.esc(subtitle)))
    render.draw_legend(add, label_x, 64)      # the tool that ran each model

    peak = total[shown[0]] or 1
    for i, model in enumerate(shown):
        y = header + i * row_h
        cy = y + row_h / 2.0
        add('<line class="grid" x1="{}" y1="{}" x2="{}" y2="{}"/>'.format(
            label_x, y + row_h, value_x, y + row_h))
        name = model if len(model) <= 34 else model[:33] + "…"
        weight = ' font-weight="700"' if i == 0 else ""
        cls = "t" if i == 0 else "t2"
        add('<text class="{}" x="{}" y="{:.1f}" font-size="12.5"{}>{}</text>'.format(
            cls, label_x, cy + 4, weight, render.esc(name)))
        source = _dominant_source(by_src, model)
        w = max(1.0, bar_w_max * total[model] / float(peak))
        add('<path class="s-{}" d="{}"/>'.format(
            source, render.cap_path_h(bar_x, cy - bar_h / 2.0, w, bar_h, 6, 6)))
        add('<text class="tm" x="{}" y="{:.1f}" font-size="12" text-anchor="end">{}</text>'.format(
            value_x, cy + 4, render.compact_tokens(total[model])))
        add('<text class="tm" x="{}" y="{:.1f}" font-size="11" text-anchor="end">{}</text>'.format(
            value_x, cy + 16, "{:.1f}%".format(100.0 * total[model] / grand)))

    if len(ranked) > len(shown):
        add('<text class="tm" x="{}" y="{}" font-size="11">+{} more models ({} tokens)</text>'.format(
            label_x, header + len(shown) * row_h + 18, len(ranked) - len(shown),
            render.compact_tokens(sum(total[m] for m in ranked[MAX_LEADERBOARD:]))))
    add('<text class="tm" x="{}" y="{}" font-size="10.5">Generated {}</text>'.format(
        label_x, h - 14, render.esc(generated)))
    add("</svg>")
    return "\n".join(out)


# ---------------------------------------------------------- monthly by model

def _build_monthly(days, generated):
    total, _, per_month, months = _collect(days)
    if not total or not months:
        return None
    ranked = _ranked(total)
    top = ranked[:MAX_MONTH_STACKS]
    has_other = len(ranked) > len(top)

    # stable index per model (rank), so class mm<i> == color for model i
    idx = {m: i for i, m in enumerate(ranked)}
    css = _model_css(ranked)

    series = list(top) + (["\u0000other"] if has_other else [])
    def val(model, mo):
        if model == "\u0000other":
            return sum(per_month.get((m, mo), 0) for m in ranked[len(top):])
        return per_month.get((model, mo), 0)

    month_totals = {mo: sum(val(m, mo) for m in series) for mo in months}
    peak = max(list(month_totals.values()) + [1])

    pad_l, pad_r, pad_t, pad_b = 76, 28, 150, 52
    plot_h = 250
    w = render.W
    h = pad_t + plot_h + pad_b
    plot_w = w - pad_l - pad_r
    slot = plot_w / float(len(months))
    bar_w = min(48, slot * 0.62)
    ticks = render.nice_ticks(peak)
    top_tick = ticks[-1] or 1

    def y_of(v):
        return pad_t + plot_h - (v / float(top_tick)) * plot_h

    title = "Monthly tokens by model"
    subtitle = "{} – {} · top {} models{}".format(
        months[0], months[-1], len(top), " + Other" if has_other else "")

    out = render.svg_start(w, h, title, css)
    add = out.append
    add('<text class="ts" x="28" y="32" font-size="20" font-style="italic">{}</text>'.format(render.esc(title)))
    add('<text class="t2" x="28" y="52" font-size="12">{}</text>'.format(render.esc(subtitle)))

    # legend: model name + swatch, wrapped across rows
    lx, ly = 28, 78
    for m in series:
        label = "Other" if m == "\u0000other" else m
        cls = "mm-other" if m == "\u0000other" else "mm{}".format(idx[m])
        est = 22 + len(label) * 6.6
        if lx + est > w - 28:
            lx, ly = 28, ly + 18
        add('<rect class="{}" x="{}" y="{}" width="10" height="10" rx="2"/>'.format(cls, lx, ly))
        add('<text class="t2" x="{}" y="{}" font-size="12">{}</text>'.format(lx + 15, ly + 9, render.esc(label)))
        lx += est
    grid_top = ly + 28

    # grid + y ticks
    for tick in ticks:
        y = pad_t + plot_h - (tick / float(top_tick)) * plot_h
        if tick > 0:
            add('<line class="grid" x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}"/>'.format(pad_l, y, w - pad_r, y))
        add('<text class="tm" x="{}" y="{:.1f}" font-size="11" text-anchor="end">{}</text>'.format(
            pad_l - 10, y + 4, render.compact_tokens(tick)))
    base_y = y_of(0)
    add('<line class="axis" x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}"/>'.format(pad_l, base_y, w - pad_r, base_y))

    for i, mo in enumerate(months):
        cx = pad_l + slot * (i + 0.5)
        x = cx - bar_w / 2.0
        stack = 0.0
        drawn = [(m, val(m, mo)) for m in series if val(m, mo) > 0]
        for j, (m, v) in enumerate(drawn):
            y_top = y_of(stack + v)
            y_bot = y_of(stack)
            seg_h = y_bot - y_top
            is_top = (j == len(drawn) - 1)
            if not is_top:
                seg_h = max(0.0, seg_h - 2)
                y_top = y_bot - seg_h
            cls = "mm-other" if m == "\u0000other" else "mm{}".format(idx[m])
            add('<path class="{}" d="{}"/>'.format(cls, render.cap_path(x, y_top, bar_w, seg_h, 4 if is_top else 0)))
            stack += v
        add('<text class="tm" x="{:.1f}" y="{}" font-size="10.5" text-anchor="middle">{}</text>'.format(
            cx, pad_t + plot_h + 20, dt.date.fromisoformat(mo + "-01").strftime("%b %y")))
        add('<text class="tm" x="{:.1f}" y="{}" font-size="10" text-anchor="middle">{}</text>'.format(
            cx, pad_t + plot_h + 35, render.compact_tokens(month_totals[mo])))

    add('<text class="tm" x="28" y="{}" font-size="10.5">Generated {}</text>'.format(h - 14, render.esc(generated)))
    add("</svg>")
    return "\n".join(out)


def build_all(days, generated):
    """Returns [(relpath, svg_string)] for the model-breakdown charts."""
    out = []
    leader = _build_leaderboard(days, generated)
    if leader:
        out.append(("model/bar-tokens.svg", leader))
    monthly = _build_monthly(days, generated)
    if monthly:
        out.append(("model/monthly.svg", monthly))
    return out
