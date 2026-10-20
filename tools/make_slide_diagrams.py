"""Draw large, simple diagrams for presenting on a projector (docs/slide_*.svg).

    python tools/make_slide_diagrams.py
    python tools/render_diagrams.py        # then turn them into PNGs

One 1600 x 900 (16:9) diagram per inheritance hierarchy, read from the classes in
banking_system.py so it always matches the code, plus an overview of the four
hierarchies and the standalone classes that connect them. Class names only, and one
short line saying what each level adds: the full detail stays in the UML diagrams.

Notation (UML): a hollow triangle points from a subclass to its parent; an italic
name marked <<abstract>> cannot be created; a plain line is an association.
"""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import banking_system as bs  # noqa: E402

DOCS = ROOT / "docs"
W, H = 1600, 900
FONT = "Helvetica, Arial, sans-serif"
INK, MUTED, LINE = "#1D2B2A", "#5B6B69", "#34495E"
FILLS = ["#E3EEF9", "#E4F2EC", "#FBEFD9"]          # one per level
STROKES = ["#3D5A80", "#2E7D5B", "#B8862F"]

# What each level adds, in a few words (the detail is in report section 6)
ADDS = {
    "Party": "identity, documents, checks, KYC", "Person": "date of birth",
    "Organization": "officers, owners, mandates", "Company": "needs a director", "Charity": "needs 2 trustees",
    "Arrangement": "product, pinned terms, holders", "DepositAccount": "ledger, holds, balances",
    "CurrentAccount": "overdraft limit", "SavingsAccount": "monthly withdrawal limit",
    "FixedTermDeposit": "term, rate, maturity", "FinancingAgreement": "principal, schedules",
    "BankTransaction": "amount, status, ledger entries", "CashTransaction": "teller, counter cash",
    "CustomerPayment": "mandate, 2nd signatory", "BillPayment": "biller, reference",
    "CardPayment": "card, merchant, refunds", "OwnAccountTransfer": "target account",
    "TransferPayment": "payee version, hold", "FeeCharge": "fee, terms version",
    "InterestCredit": "account, rate", "InternalTransfer": "bank's own books",
    "LoanTransaction": "financing agreement", "InterestCapitalisation": "interest to principal",
    "LoanDisbursement": "credit account, approval", "LoanRepayment": "allocations",
    "MerchantRefund": "merchant gives back", "Reversal": "original, reason, approval",
    "Chargeback": "dispute, reason code", "Case": "subject, status, notes, evidence",
    "CustomerCase": "channel, contact person", "Complaint": "category",
    "Dispute": "payment, amount, reason", "ServiceRequest": "request type",
    "RiskCase": "risk level, restrictions", "FraudAlert": "rule, transaction",
    "ComplianceInvestigation": "opened by compliance", "CollectionsCase": "overdue loan, promises",
}


def children(cls):
    return sorted((c for c in bs.domain_classes() if c.__bases__[0] is cls), key=lambda c: c.__name__)


def esc(text):
    return html.escape(str(text))


class Slide:
    """One 16:9 SVG drawing with a title, boxes and connectors."""

    def __init__(self, title, subtitle):
        self.parts = [f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
                      f'<text x="60" y="70" font-size="38" font-weight="bold" fill="#0B4F4A">{esc(title)}</text>',
                      f'<text x="60" y="108" font-size="20" fill="{MUTED}">{esc(subtitle)}</text>']

    def box(self, cls_or_name, x, y, w, h, level, note=None):
        """A class box; x, y is the top-left corner."""
        name = cls_or_name if isinstance(cls_or_name, str) else cls_or_name.__name__
        abstract = not isinstance(cls_or_name, str) and bs.is_abstract(cls_or_name)
        fill, stroke = FILLS[min(level, 2)], STROKES[min(level, 2)]
        self.parts.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="10" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>')
        cx, top = x + w / 2, y + 30
        if abstract:
            self.parts.append(f'<text x="{cx:.0f}" y="{y + 20:.0f}" text-anchor="middle" font-size="13" '
                              f'fill="{MUTED}">«abstract»</text>')
            top = y + 40
        size = 21 if w >= 220 else 18 if w >= 170 else 16
        while size > 12 and len(name) * size * 0.62 > w - 14:      # always fit the name inside its box
            size -= 1
        style = ' font-style="italic"' if abstract else ""
        self.parts.append(f'<text x="{cx:.0f}" y="{top:.0f}" text-anchor="middle" font-size="{size}" '
                          f'font-weight="bold" fill="{INK}"{style}>{esc(name)}</text>')
        note = ADDS.get(name) if note is None else note
        if note:
            self.parts.append(f'<text x="{cx:.0f}" y="{top + 22:.0f}" text-anchor="middle" font-size="14" '
                              f'fill="{MUTED}">{esc(note)}</text>')

    def line(self, *points, dash=False):
        pts = " ".join(f"{x:.0f},{y:.0f}" for x, y in points)
        extra = ' stroke-dasharray="7 6"' if dash else ""
        self.parts.append(f'<polyline points="{pts}" fill="none" stroke="{LINE}" stroke-width="2.2"{extra}/>')

    def triangle(self, x, y):
        """UML generalisation head, its tip touching the parent at (x, y), pointing up."""
        self.parts.append(f'<polygon points="{x:.0f},{y:.0f} {x - 11:.0f},{y + 18:.0f} {x + 11:.0f},{y + 18:.0f}" '
                          f'fill="#FFFFFF" stroke="{LINE}" stroke-width="2.2"/>')

    def label(self, x, y, text, anchor="middle"):
        self.parts.append(f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" font-size="16" '
                          f'font-style="italic" fill="#8A5A00">{esc(text)}</text>')

    def footer(self, text):
        self.parts.append(f'<text x="60" y="{H - 30}" font-size="16" fill="{MUTED}">{esc(text)}</text>')

    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
                f'font-family="{FONT}">' + "".join(self.parts) + "</svg>\n")


def hierarchy(root, title, subtitle):
    """Root at the top, its subclasses in a row, their subclasses stacked beneath each one."""
    s = Slide(title, subtitle)
    kids = children(root)
    rw, rh = 340, 84
    rx, ry = (W - rw) / 2, 150
    s.box(root, rx, ry, rw, rh, 0)
    n = len(kids)
    gap = 18
    cw = min(300, (W - 120 - gap * (n - 1)) / n)
    ch, cy = 84, 330
    total = n * cw + (n - 1) * gap
    x0 = (W - total) / 2
    centres = [x0 + i * (cw + gap) + cw / 2 for i in range(n)]
    bus = ry + rh + 46
    s.line((W / 2, ry + rh + 18), (W / 2, bus))
    s.triangle(W / 2, ry + rh)
    s.line((centres[0], bus), (centres[-1], bus))
    for i, kid in enumerate(kids):
        s.line((centres[i], bus), (centres[i], cy))
        s.box(kid, centres[i] - cw / 2, cy, cw, ch, 1)
        grand = children(kid)
        if not grand:
            continue
        spine = centres[i] - cw / 2 + 16
        # the row below is empty, so a stacked box may be wider than its parent (but stays on the slide)
        gw, gh = max(cw - 30, min(236, W - 24 - (spine + 14))), 76
        s.triangle(spine, cy + ch)
        last = None
        for k, g in enumerate(grand):
            gy = cy + ch + 40 + k * (gh + 16)
            s.box(g, spine + 14, gy, gw, gh, 2)
            s.line((spine, gy + gh / 2), (spine + 14, gy + gh / 2))
            last = gy + gh / 2
        s.line((spine, cy + ch + 18), (spine, last))
    return s


def overview():
    """The four hierarchies and the standalone classes that connect them."""
    s = Slide("The class model at a glance", "Four inheritance hierarchies, linked by association to standalone classes")
    roots = {"Party": (80, 170), "Arrangement": (1100, 170), "Case": (80, 560), "BankTransaction": (1100, 560)}
    bw, bh = 420, 230
    for name, (x, y) in roots.items():
        cls = getattr(bs, name)
        s.box(cls, x, y, bw, 84, 0, note="")
        subs = [c.__name__ for c in bs.domain_classes() if issubclass(c, cls) and c is not cls]
        lines, line = [], ""
        for sub in subs:
            if len(line) + len(sub) > 44:
                lines.append(line.rstrip(", "))
                line = ""
            line += sub + ", "
        lines.append(line.rstrip(", "))
        s.parts.append(f'<rect x="{x}" y="{y + 92}" width="{bw}" height="{bh - 92}" rx="10" fill="#F6F9F8" '
                       f'stroke="#C9D6D3"/>')
        for k, text in enumerate(lines[:5]):
            s.parts.append(f'<text x="{x + 16}" y="{y + 122 + k * 24}" font-size="16" fill="{INK}">{esc(text)}</text>')
    mid = [("Mandate", 590, 190), ("ProductDefinition", 590, 330), ("IssuedCard", 590, 470), ("Employee", 590, 610)]
    mw, mh = 420, 70
    for name, x, y in mid:
        s.box(name, x, y, mw, mh, 1, note={"Mandate": "who may act for an organisation, for a period",
                                          "ProductDefinition": "what the bank sells, versioned terms",
                                          "IssuedCard": "a card linked to an account; replacement chain",
                                          "Employee": "dated roles; approvals keep the role then"}[name])
    s.line((500, 225), (590, 225))
    s.label(545, 214, "acts for")
    s.line((290, 170), (290, 140), (1310, 140), (1310, 170), dash=True)
    s.label(800, 132, "holds (a customer holds arrangements)")
    s.line((1010, 365), (1100, 365))
    s.label(1055, 354, "sold as")
    s.line((1010, 490), (1100, 390))
    s.label(1032, 425, "linked to", "start")
    s.line((1010, 520), (1100, 610))
    s.label(1032, 588, "used by", "start")
    s.line((290, 400), (290, 560))
    s.label(300, 485, "about a party", "start")
    s.line((500, 632), (590, 632))
    s.label(545, 621, "handled by")
    s.line((1010, 662), (1100, 662), (1100, 644))
    s.label(1032, 690, "approves", "start")
    s.line((1310, 400), (1310, 560))
    s.label(1320, 485, "posts to the ledger", "start")
    s.footer("Inheritance only for a true \"is-a\"; everything else is an association. "
             "Detail: class_diagram.png and the UML diagrams.")
    return s


def main():
    slides = {
        "slide_overview": overview(),
        "slide_parties": hierarchy(bs.Party, "Parties: one record per real person or organisation",
                                   "Customer, director and signatory are roles (dated objects), not subclasses"),
        "slide_arrangements": hierarchy(bs.Arrangement, "Arrangements: what a customer holds",
                                        "Deposit accounts hold the customer's money; financing is money owed"),
        "slide_transactions": hierarchy(bs.BankTransaction, "Transactions: nothing is edited or deleted",
                                        "Reversals and chargebacks are new records linked to the original"),
        "slide_cases": hierarchy(bs.Case, "Cases: customer, risk and collections work",
                                 "Shared history at the top; who handles it and how it closes differ below"),
    }
    for name, slide in slides.items():
        path = DOCS / f"{name}.svg"
        path.write_text(slide.svg(), encoding="utf-8")
        print("written", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
