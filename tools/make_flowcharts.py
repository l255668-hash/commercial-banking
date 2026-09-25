#!/usr/bin/env python3
"""
make_flowcharts.py - draws the project's flowcharts as SVG, using the standard
flowchart shapes (ISO 5807 / ANSI conventions):

    terminator         rounded "stadium"        start and end of a flow
    process            rectangle                an action or a step
    decision           diamond                  a yes/no question
    input / output     parallelogram            data coming in or going out
    predefined process rectangle, double sides  a named operation defined elsewhere
    data store         cylinder                 stored data (ledger, audit log)

Each chart is traced from the code it describes (the decision order follows
the checks in banking_system.py / banking_gui.py). Run from the repository root:

    python tools/make_flowcharts.py            # writes docs/flowchart_*.svg

Standard library only.
"""
from __future__ import annotations

import html
import math
import textwrap
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"

CW, RH = 290, 136            # grid cell width and height (px)
MX, MY = 40, 96              # left margin, top of the grid
FONT = "Helvetica, Arial, sans-serif"

# shape: (width, height, fill, stroke, text colour, usable text width)
SHAPES = {
    "start":      (220, 46, "#0B4F4A", "#0B4F4A", "#FFFFFF", 190),
    "end":        (220, 46, "#0B4F4A", "#0B4F4A", "#FFFFFF", 190),
    "stop":       (230, 50, "#A33A1A", "#A33A1A", "#FFFFFF", 200),     # ends because a rule refused
    "process":    (240, 62, "#FFFFFF", "#34495E", "#1D2B2A", 222),
    "decision":   (262, 100, "#FFF3D6", "#B8862F", "#1D2B2A", 150),
    "io":         (250, 58, "#E6EEF9", "#3D5A80", "#1D2B2A", 200),
    "predefined": (250, 62, "#EEF4F2", "#0B4F4A", "#1D2B2A", 206),
    "datastore":  (230, 66, "#F1EAF7", "#6A4C93", "#1D2B2A", 200),
}
SKEW = 16                    # parallelogram slant


class Chart:
    """A flowchart: nodes on a grid and orthogonal connectors between their ports."""

    def __init__(self, name, title, subtitle):
        self.name, self.title, self.subtitle = name, title, subtitle
        self.nodes, self.edges = {}, []

    def node(self, key, shape, col, row, text):
        self.nodes[key] = (shape, col, row, text)

    def edge(self, a, b, label="", src="bottom", dst="top", via=()):
        self.edges.append((a, b, label, src, dst, list(via)))

    # --------------------------------------------------------------- geometry
    @staticmethod
    def centre(col, row):
        return MX + col * CW + CW / 2, MY + row * RH + RH / 2

    def port(self, key, side):
        shape, col, row, _ = self.nodes[key]
        w, h = SHAPES[shape][:2]
        x, y = self.centre(col, row)
        return {"top": (x, y - h / 2), "bottom": (x, y + h / 2),
                "left": (x - w / 2 + (SKEW / 2 if shape == "io" else 0), y),
                "right": (x + w / 2 - (SKEW / 2 if shape == "io" else 0), y)}[side]

    def route(self, a, b, src, dst, via):
        """Orthogonal polyline from port to port, through optional grid waypoints."""
        start, end = self.port(a, src), self.port(b, dst)
        pts = [start] + [self.centre(c, r) for c, r in via] + [end]
        out = [pts[0]]
        for i in range(1, len(pts)):
            (x1, y1), (x2, y2) = out[-1], pts[i]
            if abs(x1 - x2) > 0.5 and abs(y1 - y2) > 0.5:
                first, last = i == 1, i == len(pts) - 1
                leave_vertical = src in ("top", "bottom") if first else abs(out[-1][0] - (out[-2][0] if len(out) > 1 else x1)) < 0.5
                arrive_vertical = dst in ("top", "bottom")
                if first and last and leave_vertical and arrive_vertical:
                    ym = (y1 + y2) / 2
                    out += [(x1, ym), (x2, ym)]
                elif first and last and not leave_vertical and not arrive_vertical:
                    xm = (x1 + x2) / 2
                    out += [(xm, y1), (xm, y2)]
                elif (first and leave_vertical) or (last and not arrive_vertical):
                    out.append((x1, y2))
                else:
                    out.append((x2, y1))
            out.append(pts[i])
        return out

    # --------------------------------------------------------------- drawing
    def _text(self, x, y, text, colour, width_px, size=11.5, bold=False):
        chars = max(8, int(width_px / (size * 0.56)))
        lines = []
        for part in text.split("\n"):
            lines += textwrap.wrap(part, chars) or [""]
        top = y - (len(lines) - 1) * (size + 2) / 2 + size * 0.35
        weight = ' font-weight="bold"' if bold else ""
        return "".join(
            f'<text x="{x:.0f}" y="{top + i * (size + 2):.0f}" text-anchor="middle" font-size="{size}" '
            f'fill="{colour}"{weight}>{html.escape(line)}</text>' for i, line in enumerate(lines))

    def _shape(self, shape, x, y):
        w, h, fill, stroke = SHAPES[shape][:4]
        l, r, t, b = x - w / 2, x + w / 2, y - h / 2, y + h / 2
        if shape in ("start", "end", "stop"):
            return (f'<rect x="{l:.0f}" y="{t:.0f}" width="{w}" height="{h}" rx="{h / 2}" fill="{fill}" '
                    f'stroke="{stroke}" stroke-width="1.5"/>')
        if shape == "decision":
            return (f'<polygon points="{x:.0f},{t:.0f} {r:.0f},{y:.0f} {x:.0f},{b:.0f} {l:.0f},{y:.0f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        if shape == "io":
            return (f'<polygon points="{l + SKEW:.0f},{t:.0f} {r:.0f},{t:.0f} {r - SKEW:.0f},{b:.0f} {l:.0f},{b:.0f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        if shape == "predefined":
            return (f'<rect x="{l:.0f}" y="{t:.0f}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" '
                    f'stroke-width="1.5"/><line x1="{l + 12:.0f}" y1="{t:.0f}" x2="{l + 12:.0f}" y2="{b:.0f}" '
                    f'stroke="{stroke}" stroke-width="1.5"/><line x1="{r - 12:.0f}" y1="{t:.0f}" x2="{r - 12:.0f}" '
                    f'y2="{b:.0f}" stroke="{stroke}" stroke-width="1.5"/>')
        if shape == "datastore":
            e = 9
            return (f'<path d="M{l:.0f},{t + e:.0f} A{w / 2:.0f},{e} 0 0 1 {r:.0f},{t + e:.0f} L{r:.0f},{b - e:.0f} '
                    f'A{w / 2:.0f},{e} 0 0 1 {l:.0f},{b - e:.0f} Z" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
                    f'<path d="M{l:.0f},{t + e:.0f} A{w / 2:.0f},{e} 0 0 0 {r:.0f},{t + e:.0f}" fill="none" '
                    f'stroke="{stroke}" stroke-width="1.5"/>')
        return (f'<rect x="{l:.0f}" y="{t:.0f}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" '
                f'stroke-width="1.5"/>')

    def legend(self, x, y):
        items = [("start", "Terminator: start / end"), ("stop", "Terminator: ended by a rule"),
                 ("process", "Process: a step"), ("decision", "Decision: yes / no"),
                 ("io", "Input / output"), ("predefined", "Predefined process"),
                 ("datastore", "Data store")]
        out = [f'<rect x="{x}" y="{y}" width="250" height="{34 + len(items) * 30}" rx="6" fill="#FFFFFF" '
               f'stroke="#D5E0DD"/>',
               f'<text x="{x + 12}" y="{y + 22}" font-size="12" font-weight="bold" fill="#0B4F4A">Symbols</text>']
        for i, (shape, label) in enumerate(items):
            cy = y + 46 + i * 30
            w, h, fill, stroke = SHAPES[shape][:4]
            sx, sy = 0.22, 0.34
            out.append(f'<g transform="translate({x + 34},{cy}) scale({sx},{sy}) translate({-0},{-0})">'
                       f'{self._shape(shape, 0, 0)}</g>')
            out.append(f'<text x="{x + 72}" y="{cy + 4}" font-size="11" fill="#1D2B2A">{html.escape(label)}</text>')
        return "".join(out)

    def svg(self):
        furthest = max([c for _, c, _, _ in self.nodes.values()] + [c for *_, via in self.edges for c, _ in via])
        cols = math.ceil(furthest + 0.5)          # waypoints between columns widen the chart too
        rows = max(r for _, _, r, _ in self.nodes.values()) + 1
        width = MX + cols * CW + 290
        height = max(MY + rows * RH + 30, MY + 300)
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
               f'font-family="{FONT}">',
               '<rect width="100%" height="100%" fill="#FFFFFF"/>',
               '<defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="9" markerHeight="9" '
               'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#34495E"/></marker></defs>',
               f'<text x="{MX}" y="36" font-size="20" font-weight="bold" fill="#0B4F4A">{html.escape(self.title)}</text>',
               f'<text x="{MX}" y="60" font-size="12.5" fill="#5B6B69">{html.escape(self.subtitle)}</text>']
        labels = []                                  # drawn last, so no shape can hide them
        for a, b, label, src, dst, via in self.edges:
            pts = self.route(a, b, src, dst, via)
            path = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
            out.append(f'<polyline points="{path}" fill="none" stroke="#34495E" stroke-width="1.4" '
                       f'marker-end="url(#arrow)"/>')
            if label:
                (x1, y1), (x2, y2) = pts[0], pts[1]
                if abs(x1 - x2) < 0.5:          # leaves vertically: label to the right of the line
                    lx, ly, anchor = x1 + 7, y1 + 16 * (1 if y2 > y1 else -1) + 4, "start"
                else:                            # leaves horizontally: label above the line
                    lx, ly, anchor = x1 + 10 * (1 if x2 > x1 else -1), y1 - 6, "start" if x2 > x1 else "end"
                labels.append(f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="{anchor}" font-size="11.5" '
                              f'font-weight="bold" fill="#8A5A00" stroke="#FFFFFF" stroke-width="3" '
                              f'paint-order="stroke">{html.escape(label)}</text>')
        for key, (shape, col, row, text) in self.nodes.items():
            x, y = self.centre(col, row)
            out.append(self._shape(shape, x, y))
            colour, usable = SHAPES[shape][4], SHAPES[shape][5]
            out.append(self._text(x, y, text, colour, usable, bold=shape in ("start", "end", "stop")))
        out += labels
        out.append(self.legend(MX + cols * CW + 20, MY))
        out.append("</svg>")
        return "\n".join(out)


# =============================================================================
# The charts
# =============================================================================
def program_overview():
    c = Chart("flowchart_1_program", "Flowchart 1 - Program overview (banking_system.py)",
              "main(): what happens for each command-line option; the default runs the seeded demonstration")
    c.node("s", "start", 0, 0, "Start: python banking_system.py [option]")
    c.node("opt", "io", 0, 1, "Read the command-line option")
    c.node("dt", "decision", 0, 2, "--test ?")
    c.node("pt", "predefined", 1, 2, "Run the 73 unittest tests (a fresh small bank per test)")
    c.node("ot", "io", 2, 2, "Print test results (OK / FAILED)")
    c.node("dc", "decision", 0, 3, "--classes ?")
    c.node("pc", "process", 1, 3, "Walk the domain classes: inheritance tree, class and operation counts")
    c.node("oc", "io", 2, 3, "Print tree: 71 business + 6 supporting classes, 98 operations")
    c.node("dd", "decision", 0, 4, "--diagram DIR ?")
    c.node("pd", "process", 1, 4, "Read classes and source code: class, UML hierarchy and association diagrams")
    c.node("od", "io", 2, 4, "Write SVG files into DIR")
    c.node("seed", "predefined", 0, 5, "run_demo(): seed branches, staff, products, customers")
    c.node("scen", "process", 0, 6, "Run 16 scenarios; advance_to() runs the end-of-day batch for each simulated day")
    c.node("rule", "decision", 0, 7, "Did an operation break a business rule?")
    c.node("ref", "process", 1, 7, "Refusal: BankingError raised, or transaction kept as FAILED / DECLINED; printed as [BLOCKED]")
    c.node("ds", "datastore", 0, 8, "Ledger entries and audit log (append-only)")
    c.node("rep", "io", 0, 9, "Print statement, daily audit report and trial balance (total 0.00)")
    c.node("e", "end", 0, 10, "End")
    c.edge("s", "opt"); c.edge("opt", "dt")
    c.edge("dt", "pt", "Yes", "right", "left"); c.edge("pt", "ot", "", "right", "left")
    c.edge("dt", "dc", "No"); c.edge("dc", "pc", "Yes", "right", "left"); c.edge("pc", "oc", "", "right", "left")
    c.edge("dc", "dd", "No"); c.edge("dd", "pd", "Yes", "right", "left"); c.edge("pd", "od", "", "right", "left")
    c.edge("dd", "seed", "No"); c.edge("seed", "scen"); c.edge("scen", "rule")
    c.edge("rule", "ref", "Yes", "right", "left"); c.edge("ref", "ds", "", "bottom", "right")
    c.edge("rule", "ds", "No"); c.edge("ds", "rep"); c.edge("rep", "e")
    for k, r in (("ot", 2), ("oc", 3), ("od", 4)):
        c.edge(k, "e", "", "right", "right", via=[(2.72, r), (2.72, 10)])
    return c


def onboarding():
    c = Chart("flowchart_2_onboarding", "Flowchart 2 - Customer onboarding and account opening",
              "verify_party(), appoint_officer(), become_customer() and open_deposit_account()")
    c.node("s", "start", 0, 0, "Start: a new person or organisation approaches the bank")
    c.node("reg", "io", 0, 1, "Register the party: Person, Company or Charity (one record per real identity)")
    c.node("doc", "process", 0, 2, "File identity documents (CNIC, passport, incorporation certificate...)")
    c.node("ver", "predefined", 0, 3, "verify_party(): branch or compliance staff check one document")
    c.node("dv", "decision", 0, 4, "Document issued and not expired today?")
    c.node("fail", "process", 1, 4, "Record a FAIL check (kept, never deleted)")
    c.node("pass", "process", 0, 5, "Record a PASS check")
    c.node("org", "decision", 0, 6, "Is the party an organisation?")
    c.node("off", "process", 1, 6, "Appoint directors / trustees, record owners (25% threshold) and verify each person")
    c.node("onb", "predefined", 0, 7, "become_customer(): by a branch employee, with a segment")
    c.node("dr", "decision", 0, 8, "Branch role? Segment valid for this party? Sole trader has a trading name?")
    c.node("er", "stop", 1, 8, "AuthorityError / BankingError")
    c.node("dk", "decision", 0, 9, "Any KYC gap today? (party, directors, owners, structure, EDD for PRIVATE)")
    c.node("ek", "process", 1, 9, "KycIncomplete: onboarding blocked and logged")
    c.node("rel", "process", 0, 10, "Create CustomerRelationship with dated home branch and relationship manager")
    c.node("open", "predefined", 0, 11, "open_deposit_account(): current, savings or term deposit")
    c.node("dp", "decision", 0, 12, "Product on sale and right type? Holders onboarded and verified?")
    c.node("ep", "stop", 1, 12, "ProductNotAvailable / KycIncomplete")
    c.node("acct", "process", 0, 13, "Account opened; the product terms version in force is pinned")
    c.node("ds", "datastore", 0, 14, "Audit log")
    c.node("e", "end", 0, 15, "End: the customer can transact")
    c.edge("s", "reg"); c.edge("reg", "doc"); c.edge("doc", "ver"); c.edge("ver", "dv")
    c.edge("dv", "fail", "No", "right", "left"); c.edge("fail", "doc", "", "top", "right")
    c.edge("dv", "pass", "Yes"); c.edge("pass", "org")
    c.edge("org", "off", "Yes", "right", "left"); c.edge("off", "onb", "", "bottom", "right")
    c.edge("org", "onb", "No"); c.edge("onb", "dr")
    c.edge("dr", "er", "No", "right", "left"); c.edge("dr", "dk", "Yes")
    c.edge("dk", "ek", "Yes", "right", "left")
    c.edge("ek", "doc", "fix and re-verify", "right", "right", via=[(1.66, 9), (1.66, 2)])
    c.edge("dk", "rel", "No"); c.edge("rel", "open"); c.edge("open", "dp")
    c.edge("dp", "ep", "No", "right", "left"); c.edge("dp", "acct", "Yes"); c.edge("acct", "ds"); c.edge("ds", "e")
    return c


def transfer():
    c = Chart("flowchart_3_transfer", "Flowchart 3 - Transfer payment",
              "initiate_transfer(), authorise_payment(), _complete_transfer() and release_transaction()")
    c.node("s", "start", 1, 0, "Start: customer instructs a transfer")
    c.node("in", "io", 1, 1, "Account, beneficiary, amount, person instructing, channel")
    c.node("cr", "process", 1, 2, "Create TransferPayment; snapshot the beneficiary's current version")
    c.node("db", "decision", 1, 3, "Beneficiary active and owned by the account holder?")
    c.node("dso", "decision", 1, 4, "Standing-order run?")
    c.node("so", "process", 0, 4, "Use the mandate checked when the order was set up")
    c.node("da", "decision", 1, 5, "Person restricted, or no live PAYMENTS mandate within limit?")
    c.node("df", "decision", 1, 6, "Account active, not restricted, enough available balance?")
    c.node("failed", "stop", 2, 5, "FAILED: kept with the reason")
    c.node("dd", "decision", 1, 7, "Mandate needs a second signatory for this amount?")
    c.node("aw", "process", 0, 7, "AWAITING_AUTHORISATION")
    c.node("dsig", "decision", 0, 8, "A different person with a valid mandate authorises; funds still there?")
    c.node("esig", "stop", 0, 9, "AuthorityError (stays pending) or FAILED")
    c.node("dl", "decision", 1, 8, "Amount >= PKR 1,000,000 and not a standing order?")
    c.node("hold", "process", 2, 8, "Place a hold; HELD_FOR_REVIEW; raise a FraudAlert")
    c.node("dc", "decision", 2, 9, "Compliance employee releases? (a teller is refused)")
    c.node("rej", "stop", 3, 9, "REJECTED: hold released")
    c.node("rel", "process", 2, 10, "Hold released, funds re-checked, RELEASED")
    c.node("post", "predefined", 1, 11, "post(): debit the account, credit clearing 2100 (legs sum to zero)")
    c.node("ds", "datastore", 1, 12, "Ledger entries and audit log")
    c.node("e", "end", 1, 13, "End: POSTED")
    c.edge("s", "in"); c.edge("in", "cr"); c.edge("cr", "db")
    c.edge("db", "failed", "No", "right", "top"); c.edge("db", "dso", "Yes")
    c.edge("dso", "so", "Yes", "left", "right"); c.edge("so", "df", "", "bottom", "left")
    c.edge("dso", "da", "No"); c.edge("da", "failed", "Yes", "right", "left"); c.edge("da", "df", "No")
    c.edge("df", "failed", "No", "right", "bottom"); c.edge("df", "dd", "Yes")
    c.edge("dd", "aw", "Yes", "left", "right"); c.edge("aw", "dsig")
    c.edge("dsig", "esig", "No"); c.edge("dsig", "dl", "Yes", "right", "left")
    c.edge("dd", "dl", "No")
    c.edge("dl", "hold", "Yes", "right", "left"); c.edge("hold", "dc")
    c.edge("dc", "rej", "No", "right", "left"); c.edge("dc", "rel", "Yes")
    c.edge("rel", "post", "", "bottom", "right")
    c.edge("dl", "post", "No"); c.edge("post", "ds"); c.edge("ds", "e")
    return c


def card_purchase():
    c = Chart("flowchart_4_card_purchase", "Flowchart 4 - Card purchase",
              "Bank.card_purchase(): the checks run in this order; any failure keeps the payment as DECLINED")
    c.node("s", "start", 1, 0, "Start: the card network sends a purchase")
    c.node("in", "io", 1, 1, "Card, merchant, amount, channel (POS / ONLINE / ATM), country, merchant category")
    c.node("cr", "process", 1, 2, "Create CardPayment; remember the exact card used")
    c.node("d1", "decision", 1, 3, "Card ACTIVE and not expired?")
    c.node("d2", "decision", 1, 4, "A card control in force blocks this channel, country or category?")
    c.node("d3", "decision", 1, 5, "Today's spend + amount within the daily limit?")
    c.node("d4", "decision", 1, 6, "Cardholder is a holder or has a live CARD mandate?")
    c.node("d5", "decision", 1, 7, "Account usable and enough available balance?")
    c.node("dec", "stop", 2, 5, "DECLINED: kept with the reason")
    c.node("post", "predefined", 1, 8, "post(): debit the account, credit card settlement 2200")
    c.node("ds", "datastore", 1, 9, "Card payment history and audit log")
    c.node("e", "end", 1, 10, "End: POSTED")
    c.edge("s", "in"); c.edge("in", "cr"); c.edge("cr", "d1")
    c.edge("d1", "dec", "No", "right", "top"); c.edge("d1", "d2", "Yes")
    c.edge("d2", "dec", "Yes", "right", "top"); c.edge("d2", "d3", "No")
    c.edge("d3", "dec", "No", "right", "left"); c.edge("d3", "d4", "Yes")
    c.edge("d4", "dec", "No", "right", "bottom"); c.edge("d4", "d5", "Yes")
    c.edge("d5", "dec", "No", "right", "bottom"); c.edge("d5", "post", "Yes")
    c.edge("post", "ds"); c.edge("ds", "e")
    return c


def financing():
    c = Chart("flowchart_5_financing", "Flowchart 5 - Financing lifecycle",
              "application, delegated approval, conditions, disbursement, arrears and collections, restructure, settlement")
    c.node("s", "start", 1, 0, "Start: the customer applies for financing")
    c.node("app", "predefined", 1, 1, "submit_financing_application(): needs a live BORROWING mandate")
    c.node("dlim", "decision", 1, 2, "Amount within the credit employee's delegated limit?")
    c.node("refer", "process", 0, 2, "AuthorityError: refer to a higher authority (e.g. credit manager)")
    c.node("dap", "decision", 1, 3, "Approve?")
    c.node("decl", "stop", 2, 3, "DECLINED (application kept)")
    c.node("appr", "process", 1, 4, "APPROVED or APPROVED_WITH_CONDITIONS; Approval freezes the role held")
    c.node("dcon", "decision", 1, 5, "All pre-disbursement conditions satisfied?")
    c.node("sat", "process", 0, 5, "Disbursement blocked: satisfy the conditions with evidence")
    c.node("disb", "predefined", 1, 6, "disburse_financing(): agreement and schedule v1; credit settlement account, debit loans receivable")
    c.node("rep", "process", 1, 7, "Repayments allocated: oldest installment first, interest before principal")
    c.node("dov", "decision", 1, 8, "Daily batch: an installment overdue?")
    c.node("arr", "process", 2, 8, "IN_ARREARS; CollectionsCase opened; notice sent")
    c.node("prom", "process", 2, 9, "Collections officer records the contact and a promise to pay")
    c.node("dpr", "decision", 2, 10, "Promise kept by the promised date? (marked KEPT / BROKEN)")
    c.node("restr", "predefined", 3, 10, "restructure_financing(): schedule v2, overdue interest capitalised, v1 SUPERSEDED")
    c.node("dset", "decision", 1, 10, "Settle early, or last installment paid?")
    c.node("set", "process", 1, 11, "Pay principal and interest due; future interest waived; schedule CLOSED")
    c.node("e", "end", 1, 12, "End: SETTLED (every version and payment kept)")
    c.edge("s", "app"); c.edge("app", "dlim")
    c.edge("dlim", "refer", "No", "left", "right"); c.edge("refer", "app", "", "top", "left")
    c.edge("dlim", "dap", "Yes")
    c.edge("dap", "decl", "No", "right", "left"); c.edge("dap", "appr", "Yes"); c.edge("appr", "dcon")
    c.edge("dcon", "sat", "No", "left", "right"); c.edge("sat", "appr", "", "top", "left")
    c.edge("dcon", "disb", "Yes"); c.edge("disb", "rep"); c.edge("rep", "dov")
    c.edge("dov", "arr", "Yes", "right", "left"); c.edge("arr", "prom"); c.edge("prom", "dpr")
    c.edge("dpr", "restr", "No", "right", "left"); c.edge("restr", "rep", "", "top", "right")
    c.edge("dpr", "dset", "Yes", "left", "right")
    c.edge("dov", "dset", "No")
    c.edge("dset", "rep", "No", "left", "left", via=[(0.2, 10), (0.2, 7)])
    c.edge("dset", "set", "Yes"); c.edge("set", "e")
    return c


def gui():
    c = Chart("flowchart_6_gui", "Flowchart 6 - Desktop console interaction (banking_gui.py)",
              "every action calls one Bank operation; the result decides the banner colour")
    c.node("s", "start", 1, 0, "Start: python banking_gui.py")
    c.node("dtk", "decision", 1, 1, "Tkinter installed and a display available?")
    c.node("msg", "io", 2, 1, "Print how to install Tkinter or use the text demo")
    c.node("x", "stop", 3, 1, "Exit")
    c.node("seed", "predefined", 1, 2, "BankController.reset(): run the demo quietly to seed the bank")
    c.node("win", "process", 1, 3, "Build the window: sidebar (bank screens, teaching screens), top bar; show Overview")
    c.node("user", "io", 1, 4, "User picks a screen, a form, a guided check, or a top-bar action")
    c.node("dk", "decision", 1, 5, "An operation or a check?")
    c.node("scr", "process", 2, 5, "page.refresh(): read the model and redraw the screen")
    c.node("call", "predefined", 1, 6, "BankController.run(): call ONE Bank operation (all rules live in the model)")
    c.node("de", "decision", 1, 7, "BankingError raised?")
    c.node("red", "io", 3, 7, "Red banner: the error class and message")
    c.node("dr", "decision", 1, 8, "Transaction kept as FAILED or DECLINED?")
    c.node("amb", "io", 2, 8, "Amber banner: refused, kept on record")
    c.node("grn", "io", 1, 9, "Green banner: done, with the transaction story")
    c.node("ref", "process", 1, 10, "Refresh the page and the top bar (business date, books balance)")
    c.node("dcl", "decision", 1, 11, "Window closed?")
    c.node("e", "end", 1, 12, "End")
    c.edge("s", "dtk"); c.edge("dtk", "msg", "No", "right", "left"); c.edge("msg", "x", "", "right", "left")
    c.edge("dtk", "seed", "Yes"); c.edge("seed", "win"); c.edge("win", "user"); c.edge("user", "dk")
    c.edge("dk", "scr", "No", "right", "left"); c.edge("scr", "user", "", "top", "right")
    c.edge("dk", "call", "Yes"); c.edge("call", "de")
    c.edge("de", "red", "Yes", "right", "left"); c.edge("red", "ref", "", "bottom", "right")
    c.edge("de", "dr", "No"); c.edge("dr", "amb", "Yes", "right", "left"); c.edge("amb", "ref", "", "bottom", "right")
    c.edge("dr", "grn", "No"); c.edge("grn", "ref"); c.edge("ref", "dcl")
    c.edge("dcl", "user", "No", "left", "left", via=[(0.2, 11), (0.2, 4)])
    c.edge("dcl", "e", "Yes")
    return c


CHARTS = [program_overview, onboarding, transfer, card_purchase, financing, gui]


def main():
    DOCS.mkdir(exist_ok=True)
    for make in CHARTS:
        chart = make()
        path = DOCS / f"{chart.name}.svg"
        path.write_text(chart.svg(), encoding="utf-8")
        print("written", path.relative_to(DOCS.parent))


if __name__ == "__main__":
    main()
