#!/usr/bin/env python3
"""
make_state_diagrams.py - draws UML state machine diagrams from the LIFECYCLE
declarations in banking_system.py, so the diagrams cannot drift from the code.

UML state machine notation:

    initial pseudostate   small filled circle        where a new record starts
    state                 rounded rectangle          a status the record can be in
    transition            arrow labelled with the operation that causes it
    final state           circle with a ring         the record's story is over

States are coloured by the class that introduced them, which shows the state
machines being inherited and extended (BankTransaction -> CustomerPayment ->
TransferPayment).  Only the positions are chosen here; every state, move and
label comes from the classes, and the script stops if the two disagree.

    python tools/make_state_diagrams.py         # writes docs/state_*.svg

Then run tools/render_diagrams.py to refresh the PNGs.
"""
from __future__ import annotations

import html
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import banking_system as bs  # noqa: E402

DOCS = ROOT / "docs"
CW, RH = 250, 120            # one grid unit (px)
MX, MY = 30, 110             # left margin, top of the grid
BW, BH = 204, 44             # state box
FONT = "Helvetica, Arial, sans-serif"
INK, MUTED, LINE, LABEL = "#1D2B2A", "#5B6B69", "#34495E", "#8A5A00"
LEVEL_FILLS = ["#E3EEF9", "#E4F2EC", "#FBEFD9", "#F1E6F5"]     # one per class level
LEVEL_STROKES = ["#3D5A80", "#2E7D5B", "#B8862F", "#6A4C93"]


def xy(col, row):
    return MX + col * CW, MY + row * RH


def clip(cx, cy, tx, ty, w=BW, h=BH):
    """Point where the line from a box centre towards (tx, ty) leaves the box."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    scale = min((w / 2) / abs(dx) if dx else math.inf, (h / 2) / abs(dy) if dy else math.inf)
    return cx + dx * scale, cy + dy * scale


class StateDiagram:
    """One or more state machines (each from a class's LIFECYCLE) on a hand-placed grid."""

    def __init__(self, name, title, subtitle):
        self.name, self.title, self.subtitle = name, title, subtitle
        self.machines = []            # (cls, attr, layout, initial_pos, finals, label_at, caption)

    def machine(self, cls, layout, initial, finals, attr="LIFECYCLE", label_at=None, caption=None):
        lifecycle = getattr(cls, attr)
        if set(layout) != set(lifecycle.states):
            raise SystemExit(f"{cls.__name__}: layout {sorted(layout)} does not match the "
                             f"lifecycle states {sorted(lifecycle.states)}")
        if set(finals) != set(lifecycle.final):
            raise SystemExit(f"{cls.__name__}: final markers {sorted(finals)} != {sorted(lifecycle.final)}")
        self.machines.append((cls, attr, layout, initial, finals, label_at or {}, caption))

    # ------------------------------------------------------------------ levels
    @staticmethod
    def levels(cls, attr):
        """For each state, the index of the highest ancestor whose lifecycle has it. Only
        ancestors whose moves are all kept count: a replaced lifecycle is not inherited."""
        mine = getattr(cls, attr).transitions

        def inherited(lc):
            return all(set(moves) <= set(mine.get(frm, {})) for frm, moves in lc.transitions.items())
        chain = [k for k in reversed(cls.__mro__)
                 if isinstance(k.__dict__.get(attr), bs.Lifecycle) and inherited(k.__dict__[attr])]
        owner = {}
        for i, k in enumerate(chain):
            for st in k.__dict__[attr].states:
                owner.setdefault(st, i)
        return chain, owner

    # ------------------------------------------------------------------ drawing
    def svg(self):
        pts = [p for m in self.machines for p in list(m[2].values()) + [m[3]] + list(m[4].values())]
        width = MX + max(c for c, _ in pts) * CW + BW / 2 + 40
        height = MY + max(r for _, r in pts) * RH + BH / 2 + 30
        legend_rows = []
        body, labels = [], []
        for cls, attr, layout, initial, finals, label_at, caption in self.machines:
            lifecycle = getattr(cls, attr)
            chain, owner = self.levels(cls, attr)
            base = len(legend_rows)
            if len(chain) > 1:                        # only an inherited machine needs a colour key
                for i, k in enumerate(chain):
                    legend_rows.append((base + i, f"states added by {k.__name__}"))
            centre = {st: xy(*pos) for st, pos in layout.items()}
            if caption:
                cx, cy = xy(*caption[0])
                body.append(f'<text x="{cx:.0f}" y="{cy:.0f}" font-size="14" font-weight="bold" fill="{INK}">'
                            f'{html.escape(caption[1])}</text>')
            # initial pseudostate
            ix, iy = xy(*initial)
            sx, sy = centre[lifecycle.initial]
            ex, ey = clip(sx, sy, ix, iy)
            body.append(f'<circle cx="{ix:.0f}" cy="{iy:.0f}" r="9" fill="{INK}"/>')
            body.append(self._arrow(*clip(ix, iy, sx, sy, 18, 18), ex, ey))
            # transitions
            for frm, moves in lifecycle.transitions.items():
                for to, trigger in moves.items():
                    if frm == to:
                        body.append(self._self_loop(*centre[frm]))
                        x, y = centre[frm]
                        labels.append(self._label(x, y - BH / 2 - 40, trigger, "middle"))
                        continue
                    (x1, y1), (x2, y2) = centre[frm], centre[to]
                    back = to in lifecycle.transitions and frm in lifecycle.transitions[to]
                    ox = oy = 0.0
                    if back:                          # two-way pair: draw the arrows side by side
                        length = math.hypot(x2 - x1, y2 - y1)
                        ox, oy = -(y2 - y1) / length * 7, (x2 - x1) / length * 7
                    a = clip(x1, y1, x2, y2)
                    b = clip(x2, y2, x1, y1)
                    body.append(self._arrow(a[0] + ox, a[1] + oy, b[0] + ox, b[1] + oy))
                    t, anchor = label_at.get((frm, to), 0.5), "middle"
                    if isinstance(t, tuple):          # (position along the line, text anchor)
                        t, anchor = t
                    lx, ly = a[0] + (b[0] - a[0]) * t + ox * 2.2, a[1] + (b[1] - a[1]) * t + oy * 2.2
                    if anchor != "middle":            # beside the line, on the chosen side
                        labels.append(self._label(lx + (8 if anchor == "start" else -8), ly + 4, trigger, anchor))
                    elif abs(b[0] - a[0]) < 4:        # vertical line: label beside it, not across it
                        labels.append(self._label(lx + 7, ly + 4, trigger, "start"))
                    else:
                        labels.append(self._label(lx, ly + 4, trigger, "middle"))
            # final states
            for st, pos in finals.items():
                fx, fy = xy(*pos)
                x, y = centre[st]
                body.append(self._arrow(*clip(x, y, fx, fy), *clip(fx, fy, x, y, 26, 26)))
                body.append(f'<circle cx="{fx:.0f}" cy="{fy:.0f}" r="12" fill="#FFFFFF" stroke="{INK}" '
                            f'stroke-width="1.6"/><circle cx="{fx:.0f}" cy="{fy:.0f}" r="7" fill="{INK}"/>')
            # states on top of the lines
            for st, (x, y) in centre.items():
                lvl = base + owner[st]
                body.append(f'<rect x="{x - BW / 2:.0f}" y="{y - BH / 2:.0f}" width="{BW}" height="{BH}" '
                            f'rx="14" fill="{LEVEL_FILLS[lvl % 4]}" stroke="{LEVEL_STROKES[lvl % 4]}" '
                            f'stroke-width="1.6"/>')
                size = 12 if len(st) <= 22 else 10.5
                body.append(f'<text x="{x:.0f}" y="{y + 4:.0f}" text-anchor="middle" font-size="{size}" '
                            f'font-weight="bold" fill="{INK}">{st}</text>')
        width = max(width, 820)
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
               f'font-family="{FONT}">',
               '<rect width="100%" height="100%" fill="#FFFFFF"/>',
               '<defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="9" '
               f'markerHeight="9" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker></defs>',
               f'<text x="{MX}" y="34" font-size="20" font-weight="bold" fill="#0B4F4A">{html.escape(self.title)}</text>',
               f'<text x="{MX}" y="56" font-size="12.5" fill="{MUTED}">{html.escape(self.subtitle)}</text>']
        out += self._legend(legend_rows)
        out += body + labels + ["</svg>"]
        return "\n".join(out)

    @staticmethod
    def _arrow(x1, y1, x2, y2):
        return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{LINE}" '
                f'stroke-width="1.4" marker-end="url(#arrow)"/>')

    @staticmethod
    def _self_loop(x, y):
        t = y - BH / 2                                # a loop over the top edge of the box
        return (f'<path d="M{x - 26:.0f},{t:.0f} C{x - 34:.0f},{t - 44:.0f} {x + 34:.0f},{t - 44:.0f} '
                f'{x + 26:.0f},{t:.0f}" fill="none" stroke="{LINE}" stroke-width="1.4" marker-end="url(#arrow)"/>')

    @staticmethod
    def _label(x, y, text, anchor):
        return (f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" font-size="11" fill="{LABEL}" '
                f'stroke="#FFFFFF" stroke-width="3.5" paint-order="stroke">{html.escape(text)}</text>')

    @staticmethod
    def _legend(rows):
        """A one-line key under the subtitle: notation, then one swatch per class level."""
        y, out, x = 80, [], MX
        items = [("initial", "initial state"), ("final", "final state")] + [(i, t) for i, t in rows]
        for kind, text in items:
            if kind == "initial":
                out.append(f'<circle cx="{x + 7}" cy="{y - 4}" r="6" fill="{INK}"/>')
            elif kind == "final":
                out.append(f'<circle cx="{x + 7}" cy="{y - 4}" r="8" fill="#FFFFFF" stroke="{INK}" '
                           f'stroke-width="1.4"/><circle cx="{x + 7}" cy="{y - 4}" r="4.5" fill="{INK}"/>')
            else:
                out.append(f'<rect x="{x}" y="{y - 12}" width="22" height="16" rx="5" '
                           f'fill="{LEVEL_FILLS[kind % 4]}" stroke="{LEVEL_STROKES[kind % 4]}"/>')
            out.append(f'<text x="{x + 28}" y="{y}" font-size="11.5" fill="{INK}">{html.escape(text)}</text>')
            x += 38 + int(len(text) * 6.4)
        return out


# =============================================================================
# The diagrams (positions only; states, moves and labels come from the classes)
# =============================================================================
def payment():
    d = StateDiagram("state_1_payment", "State machine 1 - TransferPayment (inherited from BankTransaction "
                     "and CustomerPayment)",
                     "Each colour is the class level that introduced the state. CardPayment extends "
                     "CustomerPayment with DECLINED instead of the review hold.")
    d.machine(bs.TransferPayment, {
        "INITIATED": (3, 1),
        "AWAITING_AUTHORISATION": (1.3, 2.3), "CANCELLED": (0.45, 3.5),
        "HELD_FOR_REVIEW": (4.8, 2.3),
        "AUTHORISED": (1.3, 3.5), "FAILED": (3, 3.5),
        "RELEASED": (4.3, 4.5), "REJECTED": (5.6, 3.5),
        "POSTED": (2.2, 5.3),
        "PARTIALLY_REVERSED": (1.2, 6.6), "REVERSED": (3.2, 6.6),
    }, initial=(3, 0.25), finals={
        "CANCELLED": (0.45, 4.35), "FAILED": (3, 4.35), "REJECTED": (5.6, 4.35), "REVERSED": (4.15, 6.6),
    }, label_at={("AUTHORISED", "HELD_FOR_REVIEW"): 0.18, ("INITIATED", "POSTED"): 0.78,
                 ("HELD_FOR_REVIEW", "FAILED"): 0.45, ("AUTHORISED", "POSTED"): 0.5,
                 ("INITIATED", "FAILED"): 0.45})
    return d


def card():
    d = StateDiagram("state_2_card", "State machine 2 - IssuedCard",
                     "A card is a credential, not an account: once DESTROYED or CANCELLED it can never "
                     "be used again; a replacement is a new card.")
    d.machine(bs.IssuedCard, {
        "ACTIVE": (2, 1), "CANCELLED": (3.6, 1),
        "BLOCKED_LOST": (0.7, 2.6), "BLOCKED_STOLEN": (2, 2.6), "BLOCKED_DAMAGED": (3.3, 2.6),
        "DESTROYED": (2, 4),
    }, initial=(2, 0.25), finals={"CANCELLED": (4.4, 1), "DESTROYED": (2, 4.8)},
        label_at={("ACTIVE", "BLOCKED_STOLEN"): 0.3, ("ACTIVE", "BLOCKED_DAMAGED"): 0.62})
    return d


def financing():
    d = StateDiagram("state_3_financing", "State machine 3 - FinancingApplication and FinancingAgreement",
                     "disburse_financing moves the application to DISBURSED and creates the agreement. "
                     "FinancingAgreement replaces Arrangement's lifecycle instead of extending it.")
    d.machine(bs.FinancingApplication, {
        "SUBMITTED": (1.2, 1.3), "DECLINED": (2.5, 1.3),
        "APPROVED": (0.5, 2.7), "APPROVED_WITH_CONDITIONS": (1.9, 2.7),
        "DISBURSED": (1.2, 4.1),
    }, initial=(1.2, 0.55), finals={"DECLINED": (2.5, 2.05), "DISBURSED": (1.2, 4.9)},
        caption=((0.1, 0.3), "FinancingApplication"))
    d.machine(bs.FinancingAgreement, {
        "ACTIVE": (4.6, 1.3), "IN_ARREARS": (3.8, 2.9), "SETTLED": (4.6, 4.1),
    }, initial=(4.6, 0.55), finals={"SETTLED": (4.6, 4.9)},
        caption=((3.4, 0.3), "FinancingAgreement"),
        label_at={("ACTIVE", "SETTLED"): 0.68, ("IN_ARREARS", "ACTIVE"): (0.3, "start"),
                  ("ACTIVE", "IN_ARREARS"): (0.62, "end")})
    return d


def others():
    d = StateDiagram("state_4_other_records", "State machine 4 - the other records with a lifecycle",
                     "Nothing is deleted: closing, ending or cancelling is a move to a final state, and the "
                     "history keeps every earlier status.")
    blocks = [
        (bs.Arrangement, "LIFECYCLE", "Deposit accounts (Arrangement)"),
        (bs.Case, "LIFECYCLE", "Cases (Case)"),
        (bs.StandingOrder, "LIFECYCLE", "StandingOrder"),
        (bs.CustomerRelationship, "LIFECYCLE", "CustomerRelationship"),
        (bs.Beneficiary, "LIFECYCLE", "Beneficiary"),
        (bs.RepaymentSchedule, "LIFECYCLE", "RepaymentSchedule"),
        (bs.PromiseToPay, "LIFECYCLE", "PromiseToPay"),
        (bs.ProductDefinition, "SALE_LIFECYCLE", "ProductDefinition (sale status)"),
        (bs.Employee, "LIFECYCLE", "Employee"),
        (bs.Branch, "LIFECYCLE", "Branch"),
        (bs.Biller, "LIFECYCLE", "Biller"),
    ]
    per_row, bw, bh = 4, 2.3, 3.9
    for i, (cls, attr, caption) in enumerate(blocks):
        lc = getattr(cls, attr)
        ox, oy = 0.95 + (i % per_row) * bw, 0.15 + (i // per_row) * bh
        others_ = [s for s in lc.states if s != lc.initial]
        layout = {lc.initial: (ox + 0.25, oy + 1.2)}
        firsts = list(lc.transitions[lc.initial])
        label_at = {}
        for j, st in enumerate(firsts):
            layout[st] = (ox + 0.25 + (j - (len(firsts) - 1) / 2) * 1.3, oy + 2.4)
            if len(firsts) > 1:                       # a fan-out: each label on the outer side
                label_at[(lc.initial, st)] = (0.5, "end" if j == 0 else "start")
        for st in others_:
            layout.setdefault(st, (ox + 0.25, oy + 3.4))
        finals = {st: (layout[st][0], layout[st][1] + 0.62) for st in sorted(lc.final)}
        d.machine(cls, layout, initial=(ox + 0.25, oy + 0.6), finals=finals, attr=attr,
                  caption=((ox - 0.35, oy + 0.2), caption), label_at=label_at)
    return d


def main():
    for build in (payment, card, financing, others):
        d = build()
        path = DOCS / f"{d.name}.svg"
        path.write_text(d.svg(), encoding="utf-8")
        print("written", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
