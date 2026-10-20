#!/usr/bin/env python3
"""
make_sequence_diagram.py - draws a UML sequence diagram of one large transfer
(scenario 2 of the demonstration, TRF-002) as docs/sequence_1_large_transfer.svg.

    python tools/make_sequence_diagram.py

The class diagrams show structure and the flowcharts show the order of the
checks; this diagram shows which OBJECTS talk to each other, in time order:
the signatory starts the payment, a second signatory approves it, the bank
holds it for review and compliance releases it. Every label is filled in from
the demonstration's own records (account, mandates, alert, dates), and the
script refuses to draw if the status changes shown differ from the payment's
recorded status trail, so the diagram cannot drift from the code.

Notation (UML 2): a solid arrow with a filled head is a call; a dashed arrow
with an open head is a return; a dashed arrow marked <<create>> creates an
object, whose box starts at that point; a narrow bar on :Bank shows it is busy
with one operation.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import banking_system as bs  # noqa: E402

DOCS = ROOT / "docs"
FONT = "Helvetica, Arial, sans-serif"
INK, MUTED, LINE, TEAL, LABEL = "#1D2B2A", "#5B6B69", "#34495E", "#0B4F4A", "#1D2B2A"
GAP, LEFT, TOP = 182, 110, 96          # lifeline spacing, x of the first lifeline, top of the heads
HEAD_W, HEAD_H = 176, 46
STEP, LINE_H = 34, 15                  # vertical space per message, extra per wrapped label line


def amount(m):
    return f"{m:,.0f}"


class SequenceDiagram:
    """Lifelines across the top and messages down the page, in the order they happen."""

    def __init__(self, title, subtitle):
        self.title, self.subtitle = title, subtitle
        self.lifelines = {}              # key -> (index, line 1, line 2, kind)
        self.events = []                 # (kind, ...) in time order
        self.note = ""                   # one line under the diagram

    def lifeline(self, key, name, cls, kind="object"):
        self.lifelines[key] = (len(self.lifelines), name, cls, kind)

    def call(self, src, dst, label):
        self.events.append(("call", src, dst, label))

    def reply(self, src, dst, label):
        self.events.append(("return", src, dst, label))

    def create(self, src, dst, label):
        self.events.append(("create", src, dst, label))

    def self_call(self, key, label):
        self.events.append(("self", key, label))

    def phase(self, label):
        self.events.append(("phase", label))

    def statuses(self):
        """The status changes this diagram shows, in order (checked against the records)."""
        out = []
        for event in self.events:
            label = event[-1]
            if event[0] == "create" and "INITIATED" in label:
                out.append("INITIATED")
            if "status → " in label:
                out.append(label.split("status → ")[1].split()[0])
        return out

    # ------------------------------------------------------------------ drawing
    def x(self, key):
        return LEFT + self.lifelines[key][0] * GAP

    @staticmethod
    def _label(x, y, text, anchor="start", size=12.5, colour=LABEL, italic=False):
        style = ' font-style="italic"' if italic else ""
        return (f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" font-size="{size}" fill="{colour}"'
                f'{style} stroke="#FFFFFF" stroke-width="4" paint-order="stroke">{html.escape(text)}</text>')

    def _head(self, key, y):
        _, name, cls, kind = self.lifelines[key]
        x = self.x(key)
        if kind == "actor":                     # UML actor: a stick figure, name underneath
            return (f'<circle cx="{x}" cy="{y + 8}" r="7" fill="#FFFFFF" stroke="{INK}" stroke-width="1.6"/>'
                    f'<line x1="{x}" y1="{y + 15}" x2="{x}" y2="{y + 30}" stroke="{INK}" stroke-width="1.6"/>'
                    f'<line x1="{x - 11}" y1="{y + 20}" x2="{x + 11}" y2="{y + 20}" stroke="{INK}" stroke-width="1.6"/>'
                    f'<line x1="{x}" y1="{y + 30}" x2="{x - 9}" y2="{y + 41}" stroke="{INK}" stroke-width="1.6"/>'
                    f'<line x1="{x}" y1="{y + 30}" x2="{x + 9}" y2="{y + 41}" stroke="{INK}" stroke-width="1.6"/>'
                    f'<text x="{x}" y="{y + 57}" text-anchor="middle" font-size="13" font-weight="bold" '
                    f'fill="{INK}">{html.escape(name)}</text>'
                    f'<text x="{x}" y="{y + 72}" text-anchor="middle" font-size="11.5" fill="{MUTED}">'
                    f'{html.escape(cls)}</text>')
        top = y
        text = f"{name}{cls}" if name.startswith(":") else f"{name} {cls}"
        return (f'<rect x="{x - HEAD_W / 2:.0f}" y="{top}" width="{HEAD_W}" height="{HEAD_H}" rx="4" '
                f'fill="#E8F0EE" stroke="{TEAL}" stroke-width="1.6"/>'
                f'<text x="{x}" y="{top + 28}" text-anchor="middle" font-size="12.5" font-weight="bold" '
                f'fill="{INK}" text-decoration="underline">{html.escape(text)}</text>')

    def svg(self):
        width = LEFT + (len(self.lifelines) - 1) * GAP + LEFT
        body, bars = [], []
        starts = {k: TOP for k in self.lifelines}          # where each lifeline begins
        y = TOP + 92
        busy_from = None
        for event in self.events:
            kind = event[0]
            label = event[-1]
            lines = label.split("\n")
            y += (len(lines) - 1) * LINE_H
            if kind == "phase":
                y += 10
                body.append(f'<line x1="20" y1="{y}" x2="{width - 20}" y2="{y}" stroke="#B8862F" '
                            f'stroke-width="1" stroke-dasharray="6 5"/>')
                body.append(f'<rect x="20" y="{y - 13}" width="{len(label) * 7.1 + 18:.0f}" height="24" rx="4" '
                            f'fill="#FBEFD9" stroke="#B8862F"/>')
                body.append(f'<text x="29" y="{y + 4}" font-size="12.5" font-weight="bold" fill="#8A5A00">'
                            f'{html.escape(label)}</text>')
                y += STEP + 4
                continue
            if kind == "self":
                key = event[1]
                x = self.x(key) + (6 if key == "bank" else 0)
                body.append(f'<polyline points="{x},{y - 6} {x + 34},{y - 6} {x + 34},{y + 10} {x + 2},{y + 10}" '
                            f'fill="none" stroke="{LINE}" stroke-width="1.4" marker-end="url(#call)"/>')
                for i, line in enumerate(lines):
                    body.append(self._label(x + 42, y - 9 - (len(lines) - 1 - i) * LINE_H + 12, line,
                                            italic=True, colour=MUTED))
                y += STEP + 6
                continue
            src, dst = event[1], event[2]
            x1, x2 = self.x(src), self.x(dst)
            if kind == "call" and src not in ("bank", "txn") and dst == "bank":
                busy_from = y                                  # an actor starts a Bank operation
            if kind == "create":
                starts[dst] = y - HEAD_H / 2
                body.append(self._head(dst, y - HEAD_H / 2))
                x2 += -HEAD_W / 2 if x2 > x1 else HEAD_W / 2
            step = 5 if x2 > x1 else -5                        # leave the activation bar, not the line
            x1 += step if src == "bank" else 0
            x2 -= step if dst == "bank" else 0
            dashed = ' stroke-dasharray="7 5"' if kind in ("return", "create") else ""
            marker = "call" if kind == "call" else "open"
            body.append(f'<line x1="{x1:.0f}" y1="{y}" x2="{x2:.0f}" y2="{y}" stroke="{LINE}" stroke-width="1.4"'
                        f'{dashed} marker-end="url(#{marker})"/>')
            lx, anchor = (min(x1, x2) + 10, "start")
            for i, line in enumerate(lines):
                body.append(self._label(lx, y - 6 - (len(lines) - 1 - i) * LINE_H, line, anchor,
                                        italic=kind == "return"))
            if kind == "return" and dst not in ("bank", "txn") and src == "bank" and busy_from is not None:
                bars.append((busy_from - 4, y + 4))
                busy_from = None
            y += STEP + (14 if kind == "create" else 0)
        bottom = y + 10
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{bottom + 130}" font-family="{FONT}">',
               '<rect width="100%" height="100%" fill="#FFFFFF"/>',
               '<defs><marker id="call" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="9" markerHeight="9" '
               f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker>'
               '<marker id="open" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="9" markerHeight="9" '
               f'orient="auto"><path d="M0,0 L10,5 L0,10" fill="none" stroke="{LINE}" stroke-width="1.5"/></marker></defs>',
               f'<text x="20" y="36" font-size="20" font-weight="bold" fill="{TEAL}">{html.escape(self.title)}</text>',
               f'<text x="20" y="60" font-size="12.5" fill="{MUTED}">{html.escape(self.subtitle)}</text>']
        for key, (_, _, _, kind) in self.lifelines.items():
            x, top = self.x(key), starts[key] + (76 if kind == "actor" else HEAD_H)
            out.append(f'<line x1="{x}" y1="{top:.0f}" x2="{x}" y2="{bottom}" stroke="#9AA9A6" stroke-width="1.2" '
                       f'stroke-dasharray="5 5"/>')
            if starts[key] == TOP:
                out.append(self._head(key, TOP))
        bx = self.x("bank")
        for a, b in bars:
            out.append(f'<rect x="{bx - 5}" y="{a:.0f}" width="10" height="{b - a:.0f}" fill="#E8F0EE" '
                       f'stroke="{TEAL}" stroke-width="1.2"/>')
        out += body
        notes = [self.note,
                 "Not drawn: the AuditEvent every operation writes (Bank._log), and the refusal path: if any check "
                 "fails, Bank._fail() marks the payment FAILED with the reason, and it is kept."]
        out.append(f'<path d="M20,{bottom + 18} h{width - 60} l20,20 v62 h-{width - 40} z" fill="#FFFBEF" '
                   f'stroke="#B8862F"/><path d="M{width - 40},{bottom + 18} v20 h20" fill="none" stroke="#B8862F"/>')
        for i, text in enumerate(notes):
            out.append(f'<text x="34" y="{bottom + 42 + i * 20}" font-size="12.5" fill="{INK}">'
                       f'{html.escape(text)}</text>')
        out.append(f'<text x="34" y="{bottom + 84}" font-size="12" fill="{MUTED}">Solid arrow: call. '
                   'Dashed arrow: return, or «create» a new object. Bar on :Bank: one operation in progress. '
                   'Every value is read from the demonstration’s records.</text>')
        out.append("</svg>")
        return "\n".join(out)


def large_transfer(bank):
    """Scenario 2: TRF-002 from its creation to its posting, labelled from the records."""
    txn = bank.transactions["TRF-002"]
    acct, org = txn.source_account, txn.source_account.holders[0]
    first, second = txn.mandate_used, txn.authorisations[0].mandate
    signatory, approver = txn.initiated_by, txn.authorisations[0].person
    alert = next(c for c in bank.cases.values() if getattr(c, "transaction", None) is txn)
    released = next(c for c in txn.status.changes if c.status == "RELEASED")
    clearing = next(e for e in txn.entries if e.account is not acct)
    amt, threshold = amount(txn.amount), amount(bank.LARGE_TRANSFER_REVIEW)

    d = SequenceDiagram(f"Sequence diagram 1 - A large transfer ({txn.txn_id}, scenario 2)",
                        "Dual control, then a compliance hold, then release: the objects involved and the "
                        "messages between them, in time order")
    d.lifeline("hamza", signatory.name, "signatory", "actor")
    d.lifeline("ayesha", approver.name, "2nd signatory", "actor")
    d.lifeline("kamran", released.by, "compliance", "actor")
    d.lifeline("bank", ":Bank", "")
    d.lifeline("org", org.name.replace(" (Pvt) Ltd", ""), f":{type(org).__name__}")
    d.lifeline("acct", acct.number, f":{type(acct).__name__}")
    d.lifeline("txn", txn.txn_id, f":{type(txn).__name__}")
    d.lifeline("alert", alert.case_id, f":{type(alert).__name__}")

    d.phase(f"{txn.initiated_on:%d %b %Y}  {signatory.name} starts the payment: initiate_transfer()")
    d.call("hamza", "bank", f"initiate_transfer({acct.number}, {txn.beneficiary.nickname}, {amt})")
    d.create("bank", "txn", "«create»  status INITIATED")
    d.self_call("bank", "payee active and saved by this customer?")
    d.call("bank", "org", f"find_mandate({signatory.name},\nPAYMENTS, {amt})")
    d.reply("org", "bank", f"{first.mandate_id} (limit {amount(first.limit)})")
    d.call("bank", "acct", f"check_debit({amt})")
    d.reply("acct", "bank", "ok: enough available")
    d.self_call("bank", f"{first.mandate_id}.needs_second_signatory(): above {amount(first.dual_control_above)}")
    d.call("bank", "txn", "status → AWAITING_AUTHORISATION")
    d.reply("bank", "hamza", f"{txn.txn_id} [AWAITING_AUTHORISATION]")

    d.phase(f"{txn.authorisations[0].on:%d %b %Y}  {approver.name} approves as second signatory: authorise_payment()")
    d.call("ayesha", "bank", f"authorise_payment({txn.txn_id}, {approver.name})")
    d.self_call("bank", "not the person who started it?")
    d.call("bank", "org", f"find_mandate({approver.name},\nPAYMENTS, {amt})")
    d.reply("org", "bank", second.mandate_id)
    d.call("bank", "txn", "add PaymentAuthorisation;  status → AUTHORISED")
    d.call("bank", "acct", f"check_debit({amt})  (funds checked again)")
    d.reply("acct", "bank", "ok")
    d.self_call("bank", f"_complete_transfer(): {amt} ≥ review threshold {threshold}")
    d.call("bank", "acct", f"holds.append(AccountHold {amt})")
    d.call("bank", "txn", "status → HELD_FOR_REVIEW")
    d.create("bank", "alert", f"«create»  raise_fraud_alert({alert.rule})")
    d.reply("bank", "ayesha", f"{txn.txn_id} [HELD_FOR_REVIEW]")

    d.phase(f"{released.on:%d %b %Y}  {released.by} (compliance) releases it: release_transaction()")
    d.call("kamran", "bank", f"release_transaction({txn.txn_id}, \"{released.reason.split(';')[0]}\")")
    d.self_call("bank", "_require_role(): compliance may release")
    d.call("bank", "acct", f"hold.release({released.on:%d %b})")
    d.call("bank", "acct", f"check_debit({amt})")
    d.reply("acct", "bank", "ok")
    d.call("bank", "txn", "status → RELEASED")
    d.call("bank", "txn", f"post([({acct.number}, -{amt}), (GL {clearing.account.number}, +{amt})])")
    d.call("txn", "acct", f"LedgerEntry -{amt}")
    d.self_call("txn", "status → POSTED")
    d.note = (f"Ledger: post() writes two entries, -{amt} on {acct.number} and +{amt} on the bank's clearing "
              f"account GL {clearing.account.number}; it refuses any legs that do not sum to zero.")
    d.reply("bank", "kamran", f"{txn.txn_id} [POSTED]")

    recorded = [c.status for c in txn.status.changes]
    if d.statuses() != recorded:
        sys.exit(f"the diagram shows {d.statuses()} but {txn.txn_id} recorded {recorded}")
    return d


def main():
    bank = bs.run_demo(bs.DemoLog(echo=False))
    path = DOCS / "sequence_1_large_transfer.svg"
    path.write_text(large_transfer(bank).svg(), encoding="utf-8")
    print("written", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
