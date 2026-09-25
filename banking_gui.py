#!/usr/bin/env python3
"""
banking_gui.py
==============
Desktop front end for the Problem 4 banking model (banking_system.py).

Pure Python: Tkinter / ttk from the standard library, nothing to install
(on Linux the OS package "python3-tk" may be needed). Run:

    python banking_gui.py                 # opens on the sign-in screen
    python banking_gui.py --no-sign-in    # straight into the console, nobody signed in

Two ways in
-----------
* Staff console - sign in as a member of staff. Forms fill in who is acting
  and show what that role may do; the sidebar separates the bank's screens
  from two teaching and simulation aids (Class model, Scenario log).
* Digital banking - sign in as a customer or company signatory. They see
  their own accounts and the companies they may act for, pay and transfer,
  approve colleagues' payments, manage their cards and raise disputes.

Design rules
------------
* The GUI never changes a domain object directly. Every button calls one
  ``Bank`` operation, so every business rule, refusal and audit event is the
  model's own; a view-only signatory is refused by the model, not hidden by
  the screen. Refusals name the model's error class.
* The GUI is itself built from classes and inheritance:

      tk.Tk        -> BankingApp              the window: sign-in, staff console or digital banking
      tk.Frame     -> SignInScreen, DigitalBanking, Panel, StatCard, Banner
      ttk.Frame    -> Page                    a console screen with a title and refresh()
                        -> DashboardPage, OperationsPage, BooksPage, ReportsPage, ScenarioLogPage
                        -> MasterDetailPage   list on the left, details on the right
                             -> CustomersPage, AccountsPage, TransactionsPage, CardsPage,
                                CounterpartiesPage, CasesPage, StaffPage, ProductsPage, ClassModelPage
      ttk.Frame    -> CustomerView            a digital-banking screen for the signed-in person
                        -> HomeView, PayView, ApprovalsView, CardsView, HelpView
      tk.Canvas    -> Chart -> BarChart, ColumnChart, DonutChart
      tk.Canvas    -> TimelineCanvas, IconBadge, Avatar
      ttk.Frame    -> DataTable, DetailView, ScrollFrame
      BankController                          the only object that talks to the model
      Theme, Icons                            colours, fonts, ttk styles and line icons
"""
from __future__ import annotations

import contextlib
import gc
import inspect
import io
import re
import sys
from datetime import date, timedelta

try:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import messagebox, ttk
except ImportError:                                   # pragma: no cover - depends on the OS
    sys.exit("Tkinter is not installed. Windows/macOS: reinstall Python with 'tcl/tk' ticked. "
             "Linux: sudo apt install python3-tk")

import banking_system as bs


# =============================================================================
# Theme
# =============================================================================
class Theme:
    """Colours, fonts and ttk styles. One place, so every screen looks the same."""

    SIDEBAR = "#0D2B29"          # deep green-teal navigation
    SIDEBAR_HOVER = "#163F3B"
    SIDEBAR_ACTIVE = "#1E5A53"
    SIDEBAR_TEXT = "#D7E6E3"
    SIDEBAR_MUTED = "#86A6A1"
    TEAL = "#0E6B63"             # primary
    TEAL_2 = "#12544E"
    TEAL_3 = "#1C7A71"
    MIST = "#E8F2F0"
    CARD = "#FFFFFF"
    BG = "#F1F4F4"
    LINE = "#DCE5E3"
    INK = "#15201F"
    MUTED = "#5F6F6D"
    BRASS = "#C8932B"            # accent
    OK = "#1E7B3C"
    OK_BG = "#E3F3E8"
    BAD = "#B23A1E"
    BAD_BG = "#FBE9E3"
    WARN = "#946000"
    WARN_BG = "#FFF3D6"
    INFO = "#2F5D8A"
    INFO_BG = "#E6EEF7"
    SELECT = "#CFE8E3"
    CHART = ["#0E6B63", "#C8932B", "#2F5D8A", "#8E5BA8", "#B23A1E", "#6A8E3A", "#5F6F6D"]

    def __init__(self, root):
        families = set(tkfont.families(root))
        self.family = self._first(families, ["Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter",
                                             "Noto Sans", "DejaVu Sans", "Liberation Sans", "Arial"], "TkDefaultFont")
        self.mono = self._first(families, ["Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono",
                                           "Liberation Mono", "Courier New"], "TkFixedFont")
        # DejaVu / Liberation are wider than Segoe UI or Helvetica, so they get one size less
        base = 9 if self.family in ("DejaVu Sans", "Liberation Sans", "Noto Sans") else 10
        self.f_body = (self.family, base)
        self.f_small = (self.family, base - 1)
        self.f_bold = (self.family, base, "bold")
        self.f_h1 = (self.family, base + 9, "bold")
        self.f_h2 = (self.family, base + 2, "bold")
        self.f_stat = (self.family, base + 9, "bold")
        self.f_big = (self.family, base + 15, "bold")
        self.f_mono = (self.mono, base - 1)
        self._styles(root)

    @staticmethod
    def _first(available, wanted, fallback):
        return next((f for f in wanted if f in available), fallback)

    def _styles(self, root):
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=self.f_body, background=self.BG, foreground=self.INK)
        style.configure("TFrame", background=self.BG)
        style.configure("Card.TFrame", background=self.CARD)
        style.configure("TLabel", background=self.BG, foreground=self.INK)
        style.configure("Card.TLabel", background=self.CARD)
        style.configure("Muted.TLabel", background=self.BG, foreground=self.MUTED)
        style.configure("Treeview", background=self.CARD, fieldbackground=self.CARD, foreground=self.INK,
                        rowheight=30, borderwidth=0, font=self.f_body)
        style.configure("Treeview.Heading", background="#F4F7F6", foreground=self.MUTED, font=self.f_bold,
                        relief="flat", padding=(8, 7), bordercolor=self.LINE)
        style.map("Treeview", background=[("selected", self.SELECT)], foreground=[("selected", self.INK)])
        style.map("Treeview.Heading", background=[("active", self.MIST)])
        style.configure("TButton", padding=(14, 7), font=self.f_bold, background="#F4F7F6",
                        foreground=self.TEAL, bordercolor=self.LINE, focusthickness=0, relief="flat")
        style.map("TButton", background=[("active", self.MIST)], bordercolor=[("active", self.TEAL_3)])
        style.configure("Accent.TButton", background=self.TEAL, foreground="#FFFFFF", bordercolor=self.TEAL)
        style.map("Accent.TButton", background=[("active", self.TEAL_3), ("disabled", self.LINE)],
                  foreground=[("disabled", self.MUTED)])
        style.configure("Danger.TButton", background=self.CARD, foreground=self.BAD, bordercolor="#E7C3B8")
        style.map("Danger.TButton", background=[("active", self.BAD_BG)])
        style.configure("Link.TButton", background=self.CARD, foreground=self.TEAL, bordercolor=self.CARD,
                        padding=(6, 3))
        style.map("Link.TButton", background=[("active", self.MIST)])
        style.configure("TCombobox", padding=5, fieldbackground=self.CARD, background=self.CARD,
                        arrowcolor=self.TEAL, bordercolor=self.LINE)
        style.map("TCombobox", fieldbackground=[("readonly", self.CARD)], selectbackground=[("readonly", self.CARD)],
                  selectforeground=[("readonly", self.INK)], bordercolor=[("focus", self.TEAL_3)])
        style.configure("TEntry", padding=5, fieldbackground=self.CARD, bordercolor=self.LINE)
        style.map("TEntry", bordercolor=[("focus", self.TEAL_3)])
        style.configure("TCheckbutton", background=self.CARD, foreground=self.INK)
        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 7), font=self.f_bold, background="#E4EBEA",
                        foreground=self.MUTED, borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", self.CARD)], foreground=[("selected", self.TEAL)])
        for orient in ("Vertical", "Horizontal"):
            style.configure(f"{orient}.TScrollbar", background="#E4EBEA", troughcolor=self.BG, bordercolor=self.BG,
                            arrowcolor=self.MUTED, relief="flat")


# =============================================================================
# Words for people: status codes and audit actions in plain language
# =============================================================================
NICE = {
    "AWAITING_AUTHORISATION": "Awaiting 2nd signatory", "HELD_FOR_REVIEW": "Held for review",
    "PARTIALLY_REVERSED": "Partly reversed", "APPROVED_WITH_CONDITIONS": "Approved with conditions",
    "CLOSED_TO_NEW": "Closed to new sales", "IN_ARREARS": "In arrears", "ON_SALE": "On sale",
    "BLOCKED_LOST": "Blocked (lost)", "BLOCKED_STOLEN": "Blocked (stolen)", "BLOCKED_DAMAGED": "Blocked (damaged)",
    "CASH_WITHDRAWAL": "Cash withdrawal", "MERCHANT_CATEGORY": "Merchant category", "DEBIT_BLOCK": "Debit block",
    "FULL_FREEZE": "Full freeze", "NON_PROFIT": "Non-profit", "SOLE_TRADER": "Sole trader",
    "TERM_DEPOSIT": "Term deposit", "DEBIT_CARD": "Debit card", "ONLINE_MARKETPLACE": "Online marketplace",
}
_ACRONYMS = {"SME", "KYC", "CNIC", "ATM", "POS", "PKR", "EDD", "NTN", "HBL", "UBL", "FBR"}
_CODE_WORDS = set()
for _cls, _attr, _lc in bs.lifecycle_classes():
    _CODE_WORDS |= set(_lc.states)
_CODE_WORDS |= (bs.Bank.BRANCH_ROLES | bs.Bank.COMPLIANCE_ROLES | bs.Bank.CREDIT_ROLES | bs.Bank.CARD_ROLES
                | bs.Bank.COLLECTIONS_ROLES | bs.Bank.AUDIT_ROLES | set(bs.Bank.SEGMENTS)
                | set(bs.ProductDefinition.CATEGORIES) | {"KEPT", "BROKEN", "PASS", "FAIL", "UPHELD", "REJECTED",
                                                          "DIGITAL", "BRANCH", "PHONE", "ONLINE", "INTERNATIONAL"})
_CODE_WORDS -= _ACRONYMS
_CODE_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b|\b[A-Z]{3,}\b")


def nice(text):
    """'AWAITING_AUTHORISATION' -> 'Awaiting 2nd signatory', 'RELATIONSHIP_MANAGER' -> 'Relationship
    manager'. Only status, role and category codes change; IDs such as TRF-026 stay as they are."""
    def swap(m):
        word = m.group(0)
        if word in NICE:
            return NICE[word]
        if "_" in word or word in _CODE_WORDS:
            return word.replace("_", " ").capitalize()
        return word
    return _CODE_RE.sub(swap, str(text))


ACTIONS = {
    "CARD_PAYMENT": "paid by card", "TRANSFER": "made a transfer", "TXN_HELD": "held a payment for review",
    "TXN_PENDING_2ND_SIGNATORY": "started a payment that needs a 2nd signatory", "AUTHORISE_PAYMENT": "authorised a payment",
    "RELEASE_TXN": "released a held payment", "REJECT_TXN": "rejected a held payment", "TXN_FAILED": "refused a payment",
    "TXN_DECLINED": "declined a card payment", "FRAUD_ALERT": "raised a fraud alert", "OPEN_DISPUTE": "opened a dispute",
    "RESOLVE_DISPUTE": "resolved a dispute", "CHARGEBACK": "posted a chargeback", "REVERSAL": "posted a reversal",
    "MERCHANT_REFUND": "received a merchant refund", "BILL_PAYMENT": "paid a bill", "CASH_DEPOSIT": "took a cash deposit",
    "CASH_WITHDRAWAL": "paid out cash", "OPEN_ACCOUNT": "opened an account", "CLOSE_ACCOUNT": "closed an account",
    "ONBOARD": "onboarded a customer", "GRANT_MANDATE": "granted a mandate", "REVOKE_MANDATE": "revoked a mandate",
    "ARCHIVE": "archived a record", "DELETION_REFUSED": "refused a deletion request", "AUDIT_REVIEW": "ran the audit report",
    "STATEMENT": "produced a statement", "ADD_BENEFICIARY": "added a payee", "DELETE_BENEFICIARY": "deleted an unused payee",
    "CARD_CONTROL_ON": "switched on a card control", "CARD_CONTROL_OFF": "switched off a card control",
}


def action_text(code):
    return ACTIONS.get(code, code.replace("_", " ").lower())


def initials(name):
    parts = [p for p in str(name).replace("(", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


# =============================================================================
# Icons drawn with canvas shapes (no image files, identical on every platform)
# =============================================================================
class Icons:
    """Small line icons for the sidebar and the tiles, drawn from primitives."""

    @staticmethod
    def draw(c, name, x, y, s, col):
        w = max(1.4, s / 11)
        L = lambda *pts: c.create_line(*pts, fill=col, width=w, capstyle="round", joinstyle="round")
        R = lambda x1, y1, x2, y2, fill="": c.create_rectangle(x1, y1, x2, y2, outline=col, width=w, fill=fill)
        O = lambda x1, y1, x2, y2, fill="": c.create_oval(x1, y1, x2, y2, outline=col, width=w, fill=fill)
        u = s / 16
        X = lambda v: x + v * u
        Y = lambda v: y + v * u
        if name == "overview":
            for a, b in ((1, 1), (9, 1), (1, 9), (9, 9)):
                R(X(a), Y(b), X(a + 6), Y(b + 6))
        elif name == "operations":
            O(X(1), Y(1), X(15), Y(15))
            c.create_polygon(X(6), Y(4.5), X(12), Y(8), X(6), Y(11.5), fill=col, outline=col)
        elif name in ("customers", "user"):
            O(X(5), Y(1), X(11), Y(7))
            c.create_arc(X(2), Y(8), X(14), Y(20), start=0, extent=180, style="arc", outline=col, width=w)
        elif name == "accounts":
            R(X(1), Y(4), X(15), Y(14))
            L(X(1), Y(7), X(15), Y(7))
            O(X(10), Y(9), X(12.5), Y(11.5), fill=col)
        elif name == "transactions":
            L(X(2), Y(5), X(14), Y(5)); L(X(11), Y(2), X(14), Y(5), X(11), Y(8))
            L(X(14), Y(11), X(2), Y(11)); L(X(5), Y(8), X(2), Y(11), X(5), Y(14))
        elif name == "cards":
            R(X(1), Y(3), X(15), Y(13))
            c.create_rectangle(X(1), Y(5.5), X(15), Y(7.5), fill=col, outline=col)
            L(X(3), Y(10.5), X(7), Y(10.5))
        elif name == "counterparties":
            L(X(1), Y(6), X(3), Y(2), X(13), Y(2), X(15), Y(6), X(1), Y(6))
            R(X(2.5), Y(6), X(13.5), Y(15))
            R(X(6.5), Y(10), X(9.5), Y(15))
        elif name == "cases":
            L(X(1), Y(4), X(6), Y(4), X(7.5), Y(6), X(15), Y(6), X(15), Y(14), X(1), Y(14), X(1), Y(4))
        elif name == "staff":
            O(X(2), Y(2), X(7), Y(7)); O(X(9), Y(2), X(14), Y(7))
            c.create_arc(X(0), Y(8), X(9), Y(18), start=0, extent=180, style="arc", outline=col, width=w)
            c.create_arc(X(7), Y(8), X(16), Y(18), start=0, extent=180, style="arc", outline=col, width=w)
        elif name == "products":
            L(X(8), Y(1), X(15), Y(4.5), X(15), Y(11.5), X(8), Y(15), X(1), Y(11.5), X(1), Y(4.5), X(8), Y(1))
            L(X(1), Y(4.5), X(8), Y(8), X(15), Y(4.5)); L(X(8), Y(8), X(8), Y(15))
        elif name == "books":
            R(X(2), Y(1), X(14), Y(15)); L(X(5), Y(1), X(5), Y(15))
            L(X(7.5), Y(5), X(12), Y(5)); L(X(7.5), Y(8), X(12), Y(8))
        elif name == "reports":
            L(X(1), Y(15), X(15), Y(15))
            for a, h in ((2, 7), (6.5, 11), (11, 4)):
                c.create_rectangle(X(a), Y(15 - h), X(a + 3), Y(14.2), fill=col, outline=col)
        elif name == "classes":
            O(X(6), Y(1), X(10), Y(5)); O(X(1), Y(11), X(5), Y(15)); O(X(11), Y(11), X(15), Y(15))
            L(X(8), Y(5), X(8), Y(8), X(3), Y(8), X(3), Y(11)); L(X(8), Y(8), X(13), Y(8), X(13), Y(11))
        elif name == "log":
            R(X(3), Y(1), X(13), Y(15))
            for v in (5, 8, 11):
                L(X(5.5), Y(v), X(10.5), Y(v))
        elif name == "money":
            O(X(1), Y(1), X(15), Y(15))
            c.create_text(X(8), Y(8.3), text="Rs", fill=col, font=("TkDefaultFont", max(6, int(s / 2.6)), "bold"))
        elif name == "alert":
            L(X(8), Y(1), X(15), Y(14), X(1), Y(14), X(8), Y(1))
            L(X(8), Y(6), X(8), Y(9.5)); O(X(7.4), Y(11.3), X(8.6), Y(12.5), fill=col)
        elif name == "check":
            O(X(1), Y(1), X(15), Y(15)); L(X(4.5), Y(8.5), X(7), Y(11), X(11.5), Y(5.5))
        elif name == "lending":
            L(X(1), Y(14), X(15), Y(14)); L(X(2), Y(11), X(6), Y(7), X(9), Y(9.5), X(14), Y(3))
            L(X(10.5), Y(3), X(14), Y(3), X(14), Y(6.5))
        elif name == "phone":
            R(X(4), Y(1), X(12), Y(15)); L(X(7), Y(12.5), X(9), Y(12.5))
        else:
            O(X(3), Y(3), X(13), Y(13))


class IconBadge(tk.Canvas):
    """An icon inside a soft coloured circle (dashboard tiles)."""

    def __init__(self, parent, name, colour, bg, size=40):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        tint = _tint(colour, 0.86)
        self.create_oval(1, 1, size - 1, size - 1, fill=tint, outline=tint)
        Icons.draw(self, name, size * 0.25, size * 0.25, size * 0.5, colour)


class Avatar(tk.Canvas):
    """A person's initials in a circle."""

    def __init__(self, parent, name, bg, colour="#0E6B63", size=34):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self.create_oval(1, 1, size - 1, size - 1, fill=colour, outline=colour)
        self.create_text(size / 2, size / 2, text=initials(name), fill="#FFFFFF",
                         font=("TkDefaultFont", max(8, size // 3), "bold"))


def _autohide(bar):
    """A scroll command that shows the scrollbar only when there is something to scroll."""
    def set_(first, last):
        if float(first) <= 0.0 and float(last) >= 1.0:
            bar.grid_remove()
        else:
            bar.grid()
        bar.set(first, last)
    return set_


def _tint(hex_colour, amount):
    """Mix a colour with white (amount 0 = colour, 1 = white)."""
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    mix = lambda v: int(v + (255 - v) * amount)
    return f"#{mix(r):02x}{mix(g):02x}{mix(b):02x}"


# =============================================================================
# Controller: the only object that talks to the domain model
# =============================================================================
class Outcome:
    """The result of one operation, in words the screen can show."""

    def __init__(self, kind, title, detail=""):
        self.kind, self.title, self.detail = kind, title, detail      # kind: ok | refused | blocked


class CurrentBank:
    """Stands in for ``controller.bank`` inside long-lived callbacks.

    The operation forms are built once, but "Reset data" replaces the Bank
    object.  Capturing ``controller.bank`` directly would leave every form
    acting on the discarded bank; this proxy looks the current one up on each
    attribute access instead.
    """

    def __init__(self, controller):
        self._controller = controller

    def __getattr__(self, name):
        return getattr(self._controller.bank, name)


class BankController:
    """Builds the seeded bank, looks records up for the screens and runs operations."""

    def __init__(self):
        self.bank = None
        self.scenario_log = ""
        self.reset()

    # ------------------------------------------------------------------ lifecycle
    def reset(self):
        """Rebuild the seeded bank by running the demonstration (its output is kept)."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.bank = bs.run_demo()
        self.scenario_log = buffer.getvalue()

    def run(self, label, action):
        """Run one Bank operation and translate the result for the screen."""
        try:
            result = action()
        except bs.BankingError as e:
            return Outcome("blocked", f"{label}: refused by {type(e).__name__}", str(e))
        if isinstance(result, bs.BankTransaction):
            story = "\n".join(self.bank.transaction_story(result))
            if result.status.current in ("FAILED", "DECLINED"):
                return Outcome("refused", f"{label}: refused by a rule, kept on record as "
                                          f"{result.status.current}", story)
            return Outcome("ok", f"{label}: {result.txn_id} {result.status.current}", story)
        if isinstance(result, (list, tuple)):
            return Outcome("ok", f"{label}: done", "\n".join(map(str, result)))
        if isinstance(result, bs.VerificationCheck) and result.result != "PASS":
            return Outcome("refused", f"{label}: check recorded as {result.result} ({result.note})", label_of(result))
        if result is None:
            return Outcome("ok", f"{label}: done")
        return Outcome("ok", f"{label}: done", label_of(result) if not isinstance(result, str) else result)

    def advance(self, days):
        self.bank.advance_to(self.bank.today + timedelta(days=days))

    # ------------------------------------------------------------------ look-ups
    @property
    def today(self):
        return self.bank.today

    def persons(self):
        return sorted((p for p in self.bank.parties.values() if isinstance(p, bs.Person)), key=lambda p: p.name)

    def customers(self):
        return sorted((p for p in self.bank.parties.values() if p.relationship), key=lambda p: p.name)

    def staff(self, roles=None):
        out = []
        for e in self.bank.employees.values():
            a = e.current_assignment()
            if a and (roles is None or a.role in roles):
                out.append(e)
        return sorted(out, key=lambda e: e.person.name)

    def deposit_accounts(self, active=True):
        return [a for a in self.bank.arrangements.values() if isinstance(a, bs.DepositAccount)
                and (not active or a.status.current == "ACTIVE")]

    def financing(self, active=True):
        return [a for a in self.bank.arrangements.values() if isinstance(a, bs.FinancingAgreement)
                and (not active or a.status.current in a.USABLE_STATUSES)]

    def payments_in(self, *statuses):
        return [t for t in self.bank.transactions.values()
                if isinstance(t, bs.CustomerPayment) and t.status.current in statuses]

    def live_restrictions(self):
        out = []
        for owner in list(self.bank.parties.values()) + list(self.bank.arrangements.values()):
            out += [r for r in owner.restrictions if r.period.end is None]
        return out

    def live_controls(self):
        return [c for card in self.bank.cards.values() for c in card.controls if c.period.end is None]

    def open_cases(self):
        return [c for c in self.bank.cases.values() if c.is_open]

    # ------------------------------------------------------------ digital banking (a person's view)
    def digital_people(self):
        """People who can sign in to digital banking: customers and live organisation signatories."""
        out = []
        for p in self.persons():
            rel = p.relationship
            mandates = self.mandates_of(p)
            if (rel and rel.status.current == "ACTIVE") or mandates:
                out.append(p)
        return out

    def mandates_of(self, person):
        return [m for org in self.bank.parties.values() if isinstance(org, bs.Organization)
                for m in org.mandates if m.person is person and m.period.contains(self.today)]

    def access_for(self, person):
        """(account, capacity, capabilities, mandate) for every open account this person may see:
        their own as holder, and each organisation's under a live mandate."""
        rows = []
        for a in self.deposit_accounts():
            if person in a.holders:
                rows.append((a, "Personal", {"VIEW", "PAYMENTS", "CARD", "BORROWING"}, None))
        for m in self.mandates_of(person):
            for a in self.deposit_accounts():
                if m.organization in a.holders:
                    rows.append((a, m.organization.name, set(m.capabilities), m))
        return rows

    def cards_of(self, person):
        return [c for c in self.bank.cards.values() if c.cardholder is person]

    def awaiting_my_signature(self, person):
        """Payments waiting for a 2nd signatory that this person could approve."""
        orgs = {m.organization for m in self.mandates_of(person) if "PAYMENTS" in m.capabilities}
        return [t for t in self.payments_in("AWAITING_AUTHORISATION")
                if t.source_account.holders[0] in orgs and t.initiated_by is not person]

    def find_person(self, name):
        return next(p for p in self.bank.parties.values() if p.name == name)

    def find_employee(self, name):
        return next(e for e in self.bank.employees.values() if e.person.name == name)

    def total_deposits(self):
        return sum((a.ledger_balance() for a in self.deposit_accounts(active=False)), bs.ZERO)

    def total_lending(self):
        return sum((f.outstanding_principal() for f in self.financing()), bs.ZERO)

    def books_balance(self):
        return self.bank.trial_balance()[1] == 0

    def timeline_items(self, party):
        """(label, kind, start, end) rows for the validity-period ribbons of a party."""
        rows = []
        if isinstance(party, bs.Organization):
            rows += [(f"{r.title}: {r.person.name}", "office", r.period.start, r.period.end) for r in party.officers]
            rows += [(f"Owner {o.percent}%: {o.person.name}", "owner", o.period.start, o.period.end)
                     for o in party.owners]
            rows += [(f"Mandate {m.person.name} ({','.join(sorted(m.capabilities))})", "mandate",
                      m.period.start, m.period.end) for m in party.mandates]
        else:
            for org in self.bank.parties.values():
                if isinstance(org, bs.Organization):
                    rows += [(f"{r.title} of {org.name}", "office", r.period.start, r.period.end)
                             for r in org.officers if r.person is party]
                    rows += [(f"Mandate for {org.name}", "mandate", m.period.start, m.period.end)
                             for m in org.mandates if m.person is party]
                    rows += [(f"Owner {o.percent}% of {org.name}", "owner", o.period.start, o.period.end)
                             for o in org.owners if o.person is party]
        if party.relationship:
            rows += [(f"Home branch {b.code}", "branch", p.start, p.end) for p, b in party.relationship.branch_history]
            rows += [(f"RM {e}", "rm", p.start, p.end) for p, e in party.relationship.rm_history]
        rows += [(f"Restriction {r.scope}", "restriction", r.period.start, r.period.end) for r in party.restrictions]
        return rows

    def instance_counts(self):
        """Live objects per domain class, counted in memory (for the class model screen)."""
        counts = {}
        classes = tuple(bs.domain_classes())
        for obj in gc.get_objects():
            if isinstance(obj, classes):
                counts[type(obj)] = counts.get(type(obj), 0) + 1
        return counts


def class_path(cls):
    """Root-to-leaf inheritance chain of a domain class, e.g. Party > Organization > Company
    (Python's own ABC and object are left out)."""
    return " > ".join(k.__name__ for k in reversed(cls.__mro__) if k.__module__ == bs.__name__)


def label_of(obj):
    """A short human label for any domain object (used in lists and dropdowns)."""
    if obj is None:
        return ""
    if isinstance(obj, bs.Employee):
        a = obj.current_assignment()
        return f"{obj.person.name} ({a.role if a else 'left'})"
    if isinstance(obj, bs.Party):
        return obj.name
    if isinstance(obj, bs.Arrangement):
        return f"{obj.number} {obj.product.name} - {', '.join(h.name for h in obj.holders)}"
    if isinstance(obj, bs.BankTransaction):
        return f"{obj.txn_id} {bs.fmt(obj.amount)} {obj.narrative}"
    if isinstance(obj, bs.IssuedCard):
        return f"{obj.card_id} {obj.masked_number} {obj.cardholder.name} [{obj.status.current}]"
    if isinstance(obj, bs.Beneficiary):
        return f"{obj.nickname} ({obj.owner.name})"
    if isinstance(obj, bs.Merchant):
        return str(obj)
    if isinstance(obj, bs.Biller):
        return obj.name
    if isinstance(obj, bs.Restriction):
        return f"{obj.restriction_id} {obj.scope} on {obj.target_label}"
    if isinstance(obj, bs.CardControl):
        return f"{obj.control_id} {obj.card.card_id} {obj.control_type}{'=' + obj.value if obj.value else ''}"
    if isinstance(obj, bs.Case):
        return f"{obj.case_id} {obj.summary}"
    if isinstance(obj, bs.VerificationCheck):
        return f"{obj.check_id} {obj.result} for {obj.party.name} against {obj.document}"
    if isinstance(obj, bs.CustomerRelationship):
        return f"{obj.party.name}: {obj.segment} customer since {obj.since}, home branch {obj.branch_history[-1][1]}"
    if isinstance(obj, bs.IdentityDocument):
        return f"{obj.document_id} {obj.doc_type} {obj.number} - {obj.party.name}"
    if isinstance(obj, bs.Mandate):
        return f"{obj.mandate_id} {obj.person.name} for {obj.organization.name}"
    if isinstance(obj, bs.ProductDefinition):
        return f"{obj.code} {obj.name} ({obj.category})"
    if isinstance(obj, bs.StandingOrder):
        return f"{obj.order_id} {bs.fmt(obj.amount)} to {obj.beneficiary.nickname} on day {obj.day_of_month}"
    if isinstance(obj, bs.ApprovalCondition):
        return f"{obj.condition_id} {obj.description} ({obj.application.application_id})"
    if isinstance(obj, bs.FinancingApplication):
        return f"{obj.application_id} {obj.applicant.name} {bs.fmt(obj.requested_amount)} [{obj.status.current}]"
    return str(obj)


# =============================================================================
# Reusable widgets
# =============================================================================
class Panel(tk.Frame):
    """A white card with a title, used to group content on a page."""

    def __init__(self, parent, theme, title, subtitle=None, icon=None):
        super().__init__(parent, bg=theme.CARD, highlightbackground=theme.LINE, highlightthickness=1)
        head = tk.Frame(self, bg=theme.CARD)
        head.pack(fill="x", padx=16, pady=(12, 6))
        if icon:
            c = tk.Canvas(head, width=18, height=18, bg=theme.CARD, highlightthickness=0)
            Icons.draw(c, icon, 1, 1, 16, theme.TEAL)
            c.pack(side="left", padx=(0, 8))
        tk.Label(head, text=title, font=theme.f_h2, fg=theme.INK, bg=theme.CARD).pack(side="left")
        if subtitle:
            tk.Label(head, text=subtitle, font=theme.f_small, fg=theme.MUTED, bg=theme.CARD).pack(side="left", padx=10)
        self.head = head
        self.body = tk.Frame(self, bg=theme.CARD)
        self.body.pack(fill="both", expand=True, padx=16, pady=(0, 14))


class StatCard(tk.Frame):
    """A dashboard tile: an icon badge, a large number and a caption."""

    def __init__(self, parent, theme, caption, icon="overview", colour=None):
        super().__init__(parent, bg=theme.CARD, highlightbackground=theme.LINE, highlightthickness=1)
        self.theme = theme
        colour = colour or theme.TEAL
        IconBadge(self, icon, colour, theme.CARD, 40).pack(side="left", padx=(14, 10), pady=12)
        text = tk.Frame(self, bg=theme.CARD)
        text.pack(side="left", fill="x", expand=True, pady=10)
        self.value = tk.Label(text, text="-", font=theme.f_stat, fg=theme.INK, bg=theme.CARD, anchor="w")
        self.value.pack(fill="x")
        self.caption = tk.Label(text, text=caption, font=theme.f_small, fg=theme.MUTED, bg=theme.CARD, anchor="w")
        self.caption.pack(fill="x")

    def set(self, value, colour=None):
        self.value.config(text=value, fg=colour or self.theme.INK)


class DataTable(ttk.Frame):
    """A Treeview with scrollbars, striped rows, plain-language status words and columns that
    size themselves to their content. rows are (object, [cell, ...], optional tag)."""

    MAX_COL = 420

    def __init__(self, parent, theme, columns, on_select=None, height=12):
        super().__init__(parent, style="Card.TFrame")
        self.theme, self.on_select, self.objects = theme, on_select, {}
        self.base_widths = dict(columns)
        names = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=names, show="headings", height=height, selectmode="browse")
        for i, (name, width) in enumerate(columns):
            self.tree.heading(name, text=name)
            # only the last column stretches: the others keep their fitted width and the table
            # scrolls sideways when it is too narrow, instead of cutting every column short
            self.tree.column(name, width=width, minwidth=40, stretch=i == len(columns) - 1, anchor="w")
        ys = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=_autohide(ys), xscrollcommand=_autohide(xs))
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.tag_configure("odd", background="#F8FAFA")
        self.tree.tag_configure("bad", foreground=theme.BAD)
        self.tree.tag_configure("warn", foreground=theme.WARN)
        self.tree.tag_configure("ok", foreground=theme.OK)
        self.tree.tag_configure("muted", foreground=theme.MUTED)
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        self.tree.bind("<Double-1>", self._show_full_row)
        self._font = tkfont.Font(font=theme.f_body)
        self._head_font = tkfont.Font(font=theme.f_bold)

    def set_rows(self, rows, keep_selection=True):
        chosen = self.selected()
        self.tree.delete(*self.tree.get_children())
        self.objects = {}
        texts = []
        for i, row in enumerate(rows):
            obj, cells = row[0], [nice(c) for c in row[1]]
            tags = ["odd"] if i % 2 else []
            if len(row) > 2 and row[2]:
                tags.append(row[2])
            iid = str(i)
            self.objects[iid] = obj
            self.tree.insert("", "end", iid=iid, values=cells, tags=tags)
            if i < 300:
                texts.append(cells)
        self._fit(texts)
        if keep_selection and chosen is not None:
            for iid, obj in self.objects.items():
                if obj is chosen:
                    self.tree.selection_set(iid)
                    self.tree.see(iid)
                    break

    def _fit(self, texts):
        """Size each column to its widest cell (within limits) so nothing is cut off."""
        for i, name in enumerate(self.tree["columns"]):
            widest = self._head_font.measure(name)
            for cells in texts:
                if i < len(cells):
                    widest = max(widest, self._font.measure(cells[i]))
            fitted = min(self.MAX_COL, max(56, widest + 30))
            last = i == len(self.tree["columns"]) - 1
            self.tree.column(name, width=fitted, minwidth=fitted if last else 40)

    def selected(self):
        sel = self.tree.selection()
        return self.objects.get(sel[0]) if sel else None

    def select_first(self):
        kids = self.tree.get_children()
        if kids:
            self.tree.selection_set(kids[0])

    def _show_full_row(self, _event=None):
        """Double-click: show every cell of the row untruncated."""
        sel = self.tree.selection()
        if sel:
            cols = self.tree["columns"]
            vals = self.tree.item(sel[0], "values")
            messagebox.showinfo("Row details", "\n".join(f"{c}: {v}" for c, v in zip(cols, vals)))

    def _selected(self, _event=None):
        if self.on_select:
            self.on_select(self.selected())


class Chart(tk.Canvas):
    """Base class for the small dashboard charts: a title, redraw on resize, an empty state.
    Subclasses implement draw(data, width, height)."""

    def __init__(self, parent, theme, title, height=210):
        super().__init__(parent, height=height, bg=theme.CARD, highlightthickness=0)
        self.theme, self.title, self.data = theme, title, []
        self.bind("<Configure>", lambda _e: self._redraw())

    def set_data(self, data):
        self.data = data
        self._redraw()

    def _redraw(self):
        self.delete("all")
        w, h = max(self.winfo_width(), 200), max(self.winfo_height(), 120)
        self.create_text(4, 12, text=self.title, anchor="w", font=self.theme.f_bold, fill=self.theme.INK)
        if not self.data:
            self.create_text(w / 2, h / 2, text="No data yet", fill=self.theme.MUTED, font=self.theme.f_body)
            return
        self.draw(self.data, w, h)

    def draw(self, data, w, h):
        raise NotImplementedError

    def money_short(self, v):
        v = float(v)
        return f"{v / 1e6:,.1f}m" if abs(v) >= 1e6 else f"{v / 1e3:,.0f}k" if abs(v) >= 1e3 else f"{v:,.0f}"


class BarChart(Chart):
    """Horizontal bars: [(label, value), ...]."""

    def draw(self, data, w, h):
        t, top, left = self.theme, 34, 128
        peak = max(v for _, v in data) or 1
        row = min(30, (h - top - 6) / len(data))
        for i, (label, value) in enumerate(data):
            y = top + i * row
            self.create_text(left - 10, y + row / 2, text=label, anchor="e", fill=t.MUTED, font=t.f_small)
            length = (w - left - 70) * float(value) / float(peak)
            self.create_rectangle(left, y + 5, left + (w - left - 70), y + row - 5, fill="#F0F4F3", outline="")
            self.create_rectangle(left, y + 5, left + max(3, length), y + row - 5,
                                  fill=t.CHART[i % len(t.CHART)], outline="")
            self.create_text(left + max(3, length) + 6, y + row / 2, text=self.money_short(value), anchor="w",
                             fill=t.INK, font=t.f_small)


class ColumnChart(Chart):
    """Vertical columns: [(label, value), ...], e.g. payments per month."""

    def draw(self, data, w, h):
        t, top, bottom, left = self.theme, 34, 24, 10
        peak = max(v for _, v in data) or 1
        slot = (w - left * 2) / len(data)
        bar = max(4, min(26, slot * 0.6))
        base = h - bottom
        self.create_line(left, base, w - left, base, fill=t.LINE)
        for i, (label, value) in enumerate(data):
            x = left + i * slot + slot / 2
            height = (base - top - 14) * value / peak
            self.create_rectangle(x - bar / 2, base - height, x + bar / 2, base, fill=t.TEAL if value else t.LINE,
                                  outline="")
            if value:
                self.create_text(x, base - height - 7, text=str(value), fill=t.MUTED, font=t.f_small)
            if len(data) <= 12 or i % 2 == 0:
                self.create_text(x, base + 11, text=label, fill=t.MUTED, font=t.f_small)


class DonutChart(Chart):
    """A ring divided into parts, with a legend: [(label, value), ...]."""

    def draw(self, data, w, h):
        t = self.theme
        total = sum(v for _, v in data) or 1
        size = min(h - 44, w * 0.45)
        x0, y0 = 10, 32
        start = 90
        for i, (label, value) in enumerate(data):
            extent = -360 * value / total
            if value:
                self.create_arc(x0, y0, x0 + size, y0 + size, start=start, extent=extent - 0.01 if value == total else extent,
                                fill=t.CHART[i % len(t.CHART)], outline=t.CARD, width=2)
            start += extent
        inner = size * 0.28
        cx, cy = x0 + size / 2, y0 + size / 2
        self.create_oval(cx - size / 2 + inner, cy - size / 2 + inner, cx + size / 2 - inner, cy + size / 2 - inner,
                         fill=t.CARD, outline=t.CARD)
        self.create_text(cx, cy - 6, text=str(total), font=t.f_h2, fill=t.INK)
        self.create_text(cx, cy + 12, text="payments", font=t.f_small, fill=t.MUTED)
        lx = x0 + size + 20
        for i, (label, value) in enumerate(data):
            y = y0 + 8 + i * 22
            self.create_rectangle(lx, y - 5, lx + 11, y + 6, fill=t.CHART[i % len(t.CHART)], outline="")
            self.create_text(lx + 18, y, text=f"{label}  {value}", anchor="w", fill=t.INK, font=t.f_small)


class Banner(tk.Frame):
    """The coloured result strip shown after every action (shared by both views)."""

    STYLES = {"ok": ("OK_BG", "OK", "Done"), "refused": ("WARN_BG", "WARN", "Refused, kept on record"),
              "blocked": ("BAD_BG", "BAD", "Not allowed"), "info": ("INFO_BG", "INFO", "Note")}

    def __init__(self, parent, theme):
        super().__init__(parent, bg=theme.BG)
        self.theme = theme

    def show(self, outcome):
        t = self.theme
        for w in self.winfo_children():
            w.destroy()
        bg_name, fg_name, tag = self.STYLES[outcome.kind]
        bg, fg = getattr(t, bg_name), getattr(t, fg_name)
        box = tk.Frame(self, bg=bg, highlightbackground=_tint(fg, 0.55), highlightthickness=1)
        box.pack(fill="x", padx=24, pady=(12, 0))
        tk.Label(box, text=tag, bg=fg, fg="#FFFFFF", font=t.f_bold, padx=12).pack(side="left", fill="y")
        text = tk.Frame(box, bg=bg)
        text.pack(side="left", fill="x", expand=True, padx=12, pady=7)
        tk.Label(text, text=nice(outcome.title), bg=bg, fg=fg, font=t.f_bold, anchor="w", justify="left",
                 wraplength=980).pack(fill="x")
        if outcome.detail:
            tk.Label(text, text=nice(outcome.detail[:600]), bg=bg, fg=t.INK, font=t.f_small, anchor="w",
                     justify="left", wraplength=980).pack(fill="x")
        close = tk.Label(box, text="\u00d7", bg=bg, fg=fg, font=t.f_h2, padx=12, cursor="hand2")
        close.pack(side="right", fill="y")
        close.bind("<Button-1>", lambda _e: self.clear())

    def clear(self):
        for w in self.winfo_children():
            w.destroy()


class DetailView(ttk.Frame):
    """A read-only rich-text pane with heading, key-value, table and status styles."""

    def __init__(self, parent, theme):
        super().__init__(parent, style="Card.TFrame")
        self.theme = theme
        self.text = tk.Text(self, wrap="word", relief="flat", bd=0, bg=theme.CARD, fg=theme.INK,
                            font=theme.f_body, padx=18, pady=14, cursor="arrow", spacing1=1, spacing3=2)
        ys = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=ys.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        t = self.text
        t.tag_configure("h1", font=theme.f_h1, foreground=theme.TEAL, spacing3=4)
        t.tag_configure("sub", font=theme.f_body, foreground=theme.MUTED, spacing3=8)
        t.tag_configure("h2", font=theme.f_h2, foreground=theme.TEAL, spacing1=12, spacing3=4)
        t.tag_configure("key", font=theme.f_bold, foreground=theme.MUTED)
        t.tag_configure("mono", font=theme.f_mono)
        t.tag_configure("ok", foreground=theme.OK, font=theme.f_bold)
        t.tag_configure("bad", foreground=theme.BAD, font=theme.f_bold)
        t.tag_configure("warn", foreground=theme.WARN, font=theme.f_bold)
        t.tag_configure("muted", foreground=theme.MUTED)
        t.tag_configure("chip", background=theme.MIST, foreground=theme.TEAL, font=theme.f_bold)
        t.configure(state="disabled")

    # writing helpers -------------------------------------------------------
    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

    def done(self):
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)

    def write(self, text, *tags):
        self.text.insert("end", text, tags)

    def h1(self, text, sub=None):
        self.write(text + "\n", "h1")
        if sub:
            self.write(sub + "\n", "sub")

    def h2(self, text):
        self.write(text + "\n", "h2")

    def kv(self, key, value, tag=None):
        self.write(f"{key}:  ", "key")
        self.write(f"{value}\n", *( [tag] if tag else []))

    def line(self, text="", tag=None):
        self.write(text + "\n", *([tag] if tag else []))

    def table(self, header, rows):
        """A monospaced table; widths are fitted to the content."""
        rows = [[str(c) for c in r] for r in rows]
        widths = [max([len(header[i])] + [len(r[i]) for r in rows]) for i in range(len(header))]
        fmt_row = lambda r: "  ".join(c.ljust(widths[i]) for i, c in enumerate(r))
        self.write(fmt_row(header) + "\n", "mono", "key")
        for r in rows:
            self.write(fmt_row(r) + "\n", "mono")
        if not rows:
            self.write("(none)\n", "muted")

    def embed(self, widget):
        self.text.window_create("end", window=widget)
        self.write("\n")


class ScrollFrame(ttk.Frame):
    """A vertically scrollable area; put child widgets into .inner (mouse wheel supported)."""

    def __init__(self, parent, theme):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=theme.BG, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._wheel, add="+")

    def _wheel(self, event):
        if not self.winfo_ismapped():
            return
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget is None or not str(widget).startswith(str(self)):
            return
        step = -1 if (getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0) else 1
        self.canvas.yview_scroll(step, "units")


class TimelineCanvas(tk.Canvas):
    """Validity periods (offices, ownerships, mandates, restrictions...) drawn as ribbons on
    a shared time axis, with 'today' marked. Open-ended periods run to today."""

    COLOURS = {"office": "#146861", "owner": "#6A8E3A", "mandate": "#B8862F", "branch": "#5B7C99",
               "rm": "#7A6AA6", "restriction": "#A33A1A"}

    def __init__(self, parent, theme, items, today, width=760):
        row_h, left, top = 22, 250, 30
        height = top + max(1, len(items)) * row_h + 16
        super().__init__(parent, width=width, height=height, bg=theme.CARD, highlightthickness=0)
        if not items:
            self.create_text(10, 20, text="No dated roles", anchor="w", fill=theme.MUTED, font=theme.f_body)
            return
        start = min(i[2] for i in items)
        end = max([today] + [i[3] for i in items if i[3]]) + timedelta(days=15)
        span = max(1, (end - start).days)
        x_of = lambda d: left + (d - start).days / span * (width - left - 20)
        # month ticks
        d = date(start.year, start.month, 1)
        while d <= end:
            if d >= start:
                x = x_of(d)
                self.create_line(x, top - 6, x, height - 10, fill=theme.LINE)
                if d.month in (1, 4, 7, 10):
                    self.create_text(x + 2, top - 14, text=d.strftime("%b %Y"), anchor="w",
                                     fill=theme.MUTED, font=theme.f_small)
            d = bs.add_months(d, 1)
        tx = x_of(today)
        self.create_line(tx, top - 8, tx, height - 8, fill=theme.BRASS, width=2, dash=(4, 2))
        self.create_text(tx + 3, height - 6, text="today", anchor="sw", fill=theme.BRASS, font=theme.f_small)
        for i, (label, kind, s, e) in enumerate(items):
            y = top + i * row_h
            self.create_text(left - 10, y + 9, text=label[:38], anchor="e", fill=theme.INK, font=theme.f_small)
            x1, x2 = x_of(s), x_of(e or today)
            colour = self.COLOURS.get(kind, theme.TEAL)
            self.create_rectangle(x1, y + 2, max(x2, x1 + 3), y + 16, fill=colour, outline="")
            if e is None:
                self.create_polygon(x2, y + 2, x2 + 8, y + 9, x2, y + 16, fill=colour, outline="")
            else:
                self.create_text(min(x2 + 4, width - 60), y + 9, text=f"ended {e}", anchor="w",
                                 fill=theme.MUTED, font=theme.f_small)


# =============================================================================
# Pages
# =============================================================================
class Page(ttk.Frame):
    """A screen of the console: a title, a subtitle and a refresh() that re-reads the model."""

    title = "Page"
    subtitle = ""

    def __init__(self, parent, app):
        super().__init__(parent, style="TFrame", padding=(20, 16))
        self.app, self.theme, self.ctl = app, app.theme, app.ctl
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 14))
        self.title_label = tk.Label(head, text=self.title, font=self.theme.f_h1, fg=self.theme.INK, bg=self.theme.BG)
        self.title_label.pack(anchor="w")
        self.subtitle_label = tk.Label(head, text=self.subtitle, font=self.theme.f_body, fg=self.theme.MUTED,
                                       bg=self.theme.BG)
        if self.subtitle:
            self.subtitle_label.pack(anchor="w")
        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.build()

    def build(self):
        """Create the page's widgets (overridden by each page)."""

    def refresh(self):
        """Re-read the model and redraw (overridden by each page)."""


class MasterDetailPage(Page):
    """A list of records on the left and the selected record's details on the right.
    Subclasses declare the columns and implement rows() and show()."""

    columns = [("Item", 200)]
    pane_weights = (2, 3)

    def build(self):
        self.toolbar = ttk.Frame(self.content)
        self.toolbar.pack(fill="x", pady=(0, 8))
        self.build_toolbar(self.toolbar)
        panes = self.panes = ttk.PanedWindow(self.content, orient="horizontal")
        panes.pack(fill="both", expand=True)
        self._sash_set = False
        left = tk.Frame(panes, bg=self.theme.CARD, highlightbackground=self.theme.LINE, highlightthickness=1)
        right = tk.Frame(panes, bg=self.theme.CARD, highlightbackground=self.theme.LINE, highlightthickness=1)
        panes.add(left, weight=self.pane_weights[0])
        panes.add(right, weight=self.pane_weights[1])
        self.table = DataTable(left, self.theme, self.columns, self._show_selected, height=20)
        self.table.pack(fill="both", expand=True)
        self.detail = DetailView(right, self.theme)
        self.detail.pack(fill="both", expand=True)

    def build_toolbar(self, bar):
        """Optional filters above the list (overridden where needed)."""

    def rows(self):
        return []

    def refresh(self):
        self.table.set_rows(self.rows())
        if self.table.selected() is None:
            self.table.select_first()
        self._show_selected(self.table.selected())
        if not self._sash_set:
            self.after_idle(self._place_sash)

    def _place_sash(self):
        """Split the list and the details in the page's proportions once the page has a size."""
        width = self.panes.winfo_width()
        if width > 100:
            a, b = self.pane_weights
            self.panes.sashpos(0, int(width * a / (a + b)))
            self._sash_set = True

    def _show_selected(self, obj):
        self.detail.clear()
        if obj is None:
            self.detail.line("Select a record on the left.", "muted")
        else:
            self.show(obj)
        self.detail.done()

    def show(self, obj):
        """Write the selected object's details into self.detail."""


# ----------------------------------------------------------------------------- dashboard
class DashboardPage(Page):
    title = "Overview"
    subtitle = "The bank today: balances, work that needs attention, and whether the books balance"

    TILES = [("Active customers", "customers", "TEAL"), ("Deposits (PKR)", "money", "TEAL"),
             ("Financing (PKR)", "lending", "BRASS"), ("Open cases", "cases", "INFO"),
             ("Needs attention", "alert", "WARN"), ("Trial balance", "check", "OK")]

    def build(self):
        t = self.theme
        tiles = ttk.Frame(self.content)
        tiles.pack(fill="x")
        self.tiles = []
        for i, (caption, icon, colour) in enumerate(self.TILES):
            card = StatCard(tiles, t, caption, icon, getattr(t, colour))
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            tiles.columnconfigure(i, weight=[3, 4, 3, 3, 3, 3][i], uniform="tiles")
            self.tiles.append(card)

        charts = ttk.Frame(self.content)
        charts.pack(fill="x", pady=(14, 0))
        self.charts = []
        for i, (cls, title) in enumerate([(BarChart, "Largest depositors (PKR)"),
                                          (ColumnChart, "Customer payments per month"),
                                          (DonutChart, "Customer payment outcomes")]):
            box = tk.Frame(charts, bg=t.CARD, highlightbackground=t.LINE, highlightthickness=1)
            box.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            charts.columnconfigure(i, weight=1, uniform="charts")
            chart = cls(box, t, title, height=200)
            chart.pack(fill="both", expand=True, padx=14, pady=10)
            self.charts.append(chart)

        lower = ttk.Frame(self.content)
        lower.pack(fill="both", expand=True, pady=(14, 0))
        lower.columnconfigure(0, weight=5, uniform="lower")
        lower.columnconfigure(1, weight=4, uniform="lower")
        lower.rowconfigure(0, weight=1)

        queue = Panel(lower, t, "Needs attention", "payments waiting for a 2nd signatory or held for review",
                      icon="alert")
        queue.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.queue = DataTable(queue.body, t, [("Reference", 80), ("Payment", 200), ("Amount", 120),
                                               ("Status", 170)], height=4)
        self.queue.pack(fill="both", expand=True)
        actions = tk.Frame(queue.body, bg=t.CARD)
        actions.pack(fill="x", pady=(10, 0))
        tk.Label(actions, text="Customer's 2nd signatory", bg=t.CARD, fg=t.MUTED, font=t.f_small).pack(side="left")
        self.signatory = ttk.Combobox(actions, state="readonly", width=16)
        self.signatory.pack(side="left", padx=8)
        ttk.Button(actions, text="Authorise", command=self._authorise).pack(side="left")
        review = tk.Frame(queue.body, bg=t.CARD)
        review.pack(fill="x", pady=(8, 0))
        ttk.Button(review, text="Release held payment", style="Accent.TButton", command=self._release).pack(side="left")
        ttk.Button(review, text="Reject", style="Danger.TButton", command=self._reject).pack(side="left", padx=8)
        self.release_note = tk.Label(review, text="", bg=t.CARD, fg=t.MUTED, font=t.f_small, anchor="w")
        self.release_note.pack(side="left", fill="x", padx=4)

        recent = Panel(lower, t, "Recent activity", "from the audit log, newest first", icon="log")
        recent.grid(row=0, column=1, sticky="nsew")
        self.feed = tk.Text(recent.body, wrap="word", relief="flat", bd=0, bg=t.CARD, fg=t.INK, font=t.f_body,
                            height=8, cursor="arrow", spacing1=3, spacing3=3)
        self.feed.pack(fill="both", expand=True)
        self.feed.tag_configure("date", foreground=t.MUTED, font=t.f_small)
        self.feed.tag_configure("who", font=t.f_bold)
        self.feed.tag_configure("ref", foreground=t.TEAL, font=t.f_small)
        self.feed.tag_configure("bad", foreground=t.BAD)

    def refresh(self):
        ctl, t = self.ctl, self.theme
        bank = ctl.bank
        user = self.app.user
        if isinstance(user, bs.Employee):
            self.title_label.config(text=f"Welcome, {user.person.name.split()[0]}")
        waiting = ctl.payments_in("AWAITING_AUTHORISATION", "HELD_FOR_REVIEW")
        balanced = ctl.books_balance()
        values = [len(bank.active_customers()), f"{ctl.total_deposits():,.0f}", f"{ctl.total_lending():,.0f}",
                  len(ctl.open_cases()), len(waiting), f"{bank.trial_balance()[1]:,.2f}"]
        for tile, v in zip(self.tiles, values):
            tile.set(v)
        self.tiles[4].set(values[4], t.WARN if waiting else t.INK)
        self.tiles[5].set(values[5], t.OK if balanced else t.BAD)

        holders = {}
        for a in bank.arrangements.values():
            if isinstance(a, bs.DepositAccount) and a.status.current == "ACTIVE":
                name = a.holders[0].name.replace(" (Pvt) Ltd", "")
                holders[name] = holders.get(name, 0) + max(0, float(a.ledger_balance()))
        self.charts[0].set_data(sorted(holders.items(), key=lambda kv: -kv[1])[:5])
        payments = [x for x in bank.transactions.values() if isinstance(x, bs.CustomerPayment)]
        months = []
        d = date(ctl.today.year, ctl.today.month, 1)
        for _ in range(12):
            months.insert(0, d)
            d = bs.add_months(d, -1)
        counts = [(m.strftime("%b"), sum(1 for x in payments if x.initiated_on.year == m.year
                                         and x.initiated_on.month == m.month)) for m in months]
        self.charts[1].set_data(counts)
        groups = {"Completed": {"POSTED", "RELEASED"}, "Refused": {"FAILED", "DECLINED", "REJECTED", "CANCELLED"},
                  "Pending": {"INITIATED", "AWAITING_AUTHORISATION", "AUTHORISED", "HELD_FOR_REVIEW"},
                  "Reversed": {"REVERSED", "PARTIALLY_REVERSED"}}
        self.charts[2].set_data([(g, sum(1 for x in payments if x.status.current in states))
                                 for g, states in groups.items()])

        self.queue.set_rows([(x, [x.txn_id, x.narrative, bs.fmt(x.amount), x.status.current],
                              "warn" if x.status.current == "HELD_FOR_REVIEW" else None) for x in waiting])
        signatories = sorted({m.person.name for p in bank.parties.values() if isinstance(p, bs.Organization)
                              for m in p.mandates if m.period.end is None and "PAYMENTS" in m.capabilities})
        self.signatory["values"] = signatories
        if self.signatory.get() not in signatories and signatories:
            self.signatory.set("Ayesha Khan" if "Ayesha Khan" in signatories else signatories[0])
        officer = self._officer()
        self.release_note.config(text=f"as {officer.person.name}" if officer else "")

        self.feed.configure(state="normal")
        self.feed.delete("1.0", "end")
        for e in reversed(bank.audit[-40:]):
            refused = any(w in e.action for w in ("FAILED", "DECLINED", "REFUSED", "BLOCKED"))
            self.feed.insert("end", f"{e.on:%d %b}   ", "date")
            self.feed.insert("end", e.actor.split(" [")[0], "who")
            self.feed.insert("end", f" {action_text(e.action)} ", "bad" if refused else ())
            self.feed.insert("end", f"{e.subject}\n", "ref")
        self.feed.configure(state="disabled")

    def _officer(self):
        """Release/reject act as the signed-in employee; without a sign-in, the first compliance officer."""
        user = self.app.user
        if isinstance(user, bs.Employee):
            return user
        staff = self.ctl.staff(bs.Bank.COMPLIANCE_ROLES)
        return staff[0] if staff else None

    def _selected_payment(self):
        txn = self.queue.selected()
        if txn is None:
            messagebox.showinfo("Select a payment", "Select a payment in the list first.")
        return txn

    def _authorise(self):
        txn = self._selected_payment()
        if txn:
            person = self.ctl.find_person(self.signatory.get())
            self.app.show_outcome(self.ctl.run("Authorise payment",
                                               lambda: self.ctl.bank.authorise_payment(txn, person)))

    def _release(self):
        txn = self._selected_payment()
        if txn:
            officer = self._officer()
            self.app.show_outcome(self.ctl.run(
                "Release held payment", lambda: self.ctl.bank.release_transaction(txn, officer, "released after review")))

    def _reject(self):
        txn = self._selected_payment()
        if txn:
            officer = self._officer()
            self.app.show_outcome(self.ctl.run(
                "Reject held payment", lambda: self.ctl.bank.reject_held_transaction(txn, officer, "rejected after review")))


# ----------------------------------------------------------------------------- customers
class CustomersPage(MasterDetailPage):
    title = "Customers and parties"
    subtitle = "One record per real person or organisation; roles are dated objects, never subclasses"
    columns = [("Name", 175), ("Type", 75), ("Segment", 100), ("Status", 70)]

    def build_toolbar(self, bar):
        ttk.Label(bar, text="Time machine - show the bank's view as at (YYYY-MM-DD):").pack(side="left")
        self.as_at = ttk.Entry(bar, width=12)
        self.as_at.pack(side="left", padx=8)
        self.as_at.insert(0, "2026-04-11")
        ttk.Button(bar, text="Show", command=self.refresh).pack(side="left")

    def rows(self):
        out = []
        for p in sorted(self.ctl.bank.parties.values(), key=lambda p: (not p.relationship, p.name)):
            rel = p.relationship
            status = rel.status.current if rel else "-"
            tag = "muted" if not rel or status != "ACTIVE" else None
            out.append((p, [p.name, type(p).__name__, rel.segment if rel else "-", status], tag))
        return out

    def show(self, p):
        d, bank = self.detail, self.ctl.bank
        path = class_path(type(p))
        d.h1(p.name, f"{p.party_id}   class path: {path}")
        if isinstance(p, bs.Organization):
            d.kv("Registration", p.registration_no)
            d.kv("Registered address", p.detail("registered_address"))
        if p.detail("trading_name"):
            d.kv("Trading name", p.detail("trading_name"))
        gaps = p.kyc_gaps(bank.today)
        d.kv("KYC today", "complete" if not gaps else "; ".join(gaps), "ok" if not gaps else "bad")
        d.h2("Capacities (one person, many roles)")
        caps = bank.capacities_of(p) if isinstance(p, bs.Person) else []
        if isinstance(p, bs.Organization) or not caps:
            caps = caps or [f"{r.title}: {r.person.name} {r.period}" for r in getattr(p, "officers", [])]
        for c in caps or ["(none)"]:
            d.line("  - " + c)
        d.h2("Dated roles and periods")
        d.embed(TimelineCanvas(d.text, self.theme, self.ctl.timeline_items(p), bank.today))
        if isinstance(p, bs.Organization):
            d.h2("Mandates")
            d.table(["Mandate", "Person", "Can", "Limit", "Valid"],
                    [[m.mandate_id, m.person.name, ",".join(sorted(m.capabilities)),
                      bs.fmt(m.limit) if m.limit is not None else "unlimited", str(m.period)] for m in p.mandates])
        d.h2("Identity checks (kept, never overwritten)")
        d.table(["Check", "On", "Result", "Document", "By"],
                [[c.check_id, c.performed_on, c.result, str(c.document), c.performed_by] for c in p.checks])
        if p.corrections:
            d.h2("Corrections")
            for c in p.corrections:
                d.line(f"  {c.on} {c.field}: '{c.old_value}' -> '{c.new_value}' ({c.reason}; by {c.by})")
        holdings = [a for a in bank.arrangements.values() if p in a.holders]
        if holdings:
            d.h2("Products held")
            d.table(["Number", "Product", "Status"], [[a.number, a.product.name, a.status.current] for a in holdings])
        if p.relationship:
            d.h2("Relationship history")
            for line in bank.relationship_history(p):
                d.line("  " + line, "mono")
        try:
            as_at = date.fromisoformat(self.as_at.get().strip())
        except ValueError:
            as_at = None
        if as_at:
            d.h2(f"Time machine: the bank's view on {as_at}")
            for line in bank.party_snapshot(p, as_at):
                d.line("  " + line)


# ----------------------------------------------------------------------------- accounts
class AccountsPage(MasterDetailPage):
    title = "Accounts and financing"
    subtitle = "Customer arrangements: each keeps the terms version it was sold under"
    columns = [("Number", 70), ("Class", 135), ("Holder", 150), ("Balance", 125), ("Status", 85)]
    pane_weights = (1, 1)

    def rows(self):
        out = []
        for a in self.ctl.bank.arrangements.values():
            amount, meaning = a.position()          # polymorphic: held for deposits, owed for financing
            bal = bs.fmt(amount) + (" owed" if meaning == "owed" else "")
            tag = "muted" if a.status.current in ("CLOSED", "SETTLED") else (
                "bad" if a.status.current == "IN_ARREARS" else None)
            out.append((a, [a.number, type(a).__name__, ", ".join(h.name for h in a.holders), bal,
                            a.status.current + (" (archived)" if a.archived_on else "")], tag))
        return out

    def show(self, a):
        d, bank = self.detail, self.ctl.bank
        path = class_path(type(a))
        d.h1(f"{a.number}  {a.product.name}", f"class path: {path}")
        d.kv("Holders", ", ".join(h.name for h in a.holders))
        d.kv("Status trail", a.status.trail())
        d.kv("Opened", f"{a.opened_on} at {a.opened_at_branch}")
        d.kv("Servicing branch history", "; ".join(f"{b.code} {p}" for p, b in a.servicing_history))
        d.kv("Terms in force", f"v{a.terms.version_no}  " + (", ".join(f"{k}={v}" for k, v in a.terms.terms.items())
                                                               or "no fees or rates"))
        d.kv("Terms history", "; ".join(f"from {s}: v{v.version_no}" for s, v in a.terms_history))
        if a.archived_on:
            d.kv("Archived", f"{a.archived_on}; retain until {bank.retention_until(a)}", "warn")
        if isinstance(a, bs.DepositAccount):
            d.h2("Balances")
            d.kv("Ledger balance", bs.fmt(a.ledger_balance()))
            if a.status.current == "ACTIVE":
                d.kv("Available today", bs.fmt(a.available_balance(bank.today)))
            if isinstance(a, bs.FixedTermDeposit):
                d.kv("Term", f"{a.term_months} months at {a.annual_rate:.2%}, maturity {a.maturity_on}")
                d.kv("Pays out to", a.payout_account.number if a.payout_account else "-")
            holds = [h for h in a.holds]
            if holds:
                d.h2("Holds")
                d.table(["Placed", "Amount", "Released", "Reason"],
                        [[h.placed_on, bs.fmt(h.amount), h.released_on or "active", h.reason] for h in holds])
            d.h2("Ledger (balances are derived from these entries, never stored)")
            running, rows = bs.ZERO, []
            for e in a.entries:
                running += e.amount
                rows.append([e.posted_on, f"{e.amount:,.2f}", f"{running:,.2f}", e.transaction.txn_id,
                             e.transaction.narrative[:48]])
            d.table(["Date", "Amount", "Balance", "Txn", "Narrative"], rows[-60:])
            cards = [c for c in bank.cards.values() if c.account is a]
            if cards:
                d.h2("Cards drawing on this account")
                for c in cards:
                    d.line("  " + label_of(c))
        else:
            app = a.application
            d.h2("Financing")
            d.kv("Principal", bs.fmt(a.principal))
            d.kv("Outstanding principal", bs.fmt(a.outstanding_principal()))
            d.kv("Credit decision", str(app.decision))
            d.kv("Conditions", "; ".join(f"{c.description} ({'met ' + str(c.satisfied_on) if c.is_met() else 'open'})"
                                         for c in app.conditions) or "none")
            for s in a.schedules:
                d.h2(f"Schedule v{s.version} [{s.status.current}] - {s.reason}")
                d.table(["#", "Due", "Principal", "Interest", "Outstanding", "Status"],
                        [[i.seq, i.due_on, f"{i.principal:,.2f}", f"{i.interest:,.2f}", f"{i.outstanding:,.2f}",
                          i.status_on(bank.today)] for i in s.installments])


# ----------------------------------------------------------------------------- transactions
class TransactionsPage(MasterDetailPage):
    title = "Transactions"
    subtitle = "Nothing is edited or deleted: reversals and corrections are new, linked records"
    columns = [("Reference", 85), ("Class", 125), ("Date", 80), ("Amount", 115), ("Status", 165)]
    pane_weights = (5, 4)

    KINDS = ["All", "CustomerPayment", "TransferPayment", "CardPayment", "BillPayment", "OwnAccountTransfer",
             "CashTransaction", "LoanTransaction", "FeeCharge", "InterestCredit", "Reversal", "InternalTransfer"]

    def build_toolbar(self, bar):
        ttk.Label(bar, text="Class").pack(side="left")
        self.kind = ttk.Combobox(bar, values=self.KINDS, state="readonly", width=18)
        self.kind.set("All")
        self.kind.pack(side="left", padx=(6, 14))
        ttk.Label(bar, text="Status").pack(side="left")
        self.status = ttk.Combobox(bar, state="readonly", width=22)
        self.status.set("All")
        self.status.pack(side="left", padx=(6, 14))
        ttk.Label(bar, text="Search").pack(side="left")
        self.search = ttk.Entry(bar, width=22)
        self.search.pack(side="left", padx=6)
        for w in (self.kind, self.status):
            w.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.search.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(bar, text="Filter", command=self.refresh).pack(side="left", padx=6)

    def rows(self):
        txns = list(self.ctl.bank.transactions.values())
        self.status["values"] = ["All"] + sorted({t.status.current for t in txns})
        kind = self.kind.get()
        cls = getattr(bs, kind, None) if kind != "All" else None
        term = self.search.get().strip().lower()
        out = []
        for t in reversed(txns):
            if cls and not isinstance(t, cls):
                continue
            if self.status.get() not in ("", "All") and t.status.current != self.status.get():
                continue
            if term and term not in (t.txn_id + " " + t.narrative).lower():
                continue
            st = t.status.current
            tag = "bad" if st in ("FAILED", "DECLINED", "REJECTED") else (
                "warn" if st in ("AWAITING_AUTHORISATION", "HELD_FOR_REVIEW") else None)
            out.append((t, [t.txn_id, t.kind, t.initiated_on, bs.fmt(t.amount), st], tag))
        return out

    def show(self, t):
        d, bank = self.detail, self.ctl.bank
        path = class_path(type(t))
        d.h1(f"{t.txn_id}  {bs.fmt(t.amount)}", f"class path: {path}")
        d.kv("Counterparty", t.counterparty())
        st = t.status.current
        d.kv("Status", st, "bad" if st in ("FAILED", "DECLINED") else "ok" if st == "POSTED" else "warn")
        if t.failure_reason:
            d.kv("Refused because", t.failure_reason, "bad")
        d.h2("Story")
        for line in bank.transaction_story(t):
            d.line(line)
        if isinstance(t, bs.TransferPayment):
            d.h2("Beneficiary: as sent vs today")
            d.kv("Sent to", str(t.beneficiary_version))
            d.kv("Today", str(t.beneficiary.current_version),
                 "warn" if t.beneficiary.current_version is not t.beneficiary_version else None)
        if isinstance(t, bs.CardPayment):
            d.kv("Channel / country / category", f"{t.card_channel} / {t.country} / {t.merchant_category}")
        if isinstance(t, bs.BillPayment):
            d.kv("Biller / reference", f"{t.biller.name} / {t.consumer_reference}")
        d.h2("Double-entry legs (sum to zero)")
        d.table(["Account", "Amount", "Posted"],
                [[getattr(e.account, "number", "?"), f"{e.amount:,.2f}", e.posted_on] for e in t.entries])


# ----------------------------------------------------------------------------- cards
class CardsPage(MasterDetailPage):
    title = "Cards"
    subtitle = "A card is a credential linked to an account; replacements form a searchable chain"
    columns = [("Card", 75), ("Number", 150), ("Cardholder", 130), ("Status", 130)]

    def rows(self):
        return [(c, [c.card_id, c.masked_number, c.cardholder.name, c.status.current],
                 None if c.status.current == "ACTIVE" else "muted") for c in self.ctl.bank.cards.values()]

    def show(self, c):
        d, bank = self.detail, self.ctl.bank
        d.h1(f"{c.card_id}  {c.masked_number}", f"{c.cardholder.name} on {c.account.number}")
        d.kv("Status trail", c.status.trail())
        d.kv("Daily limit history", "; ".join(f"from {s}: {bs.fmt(l)}" for s, l in c.limit_history))
        d.h2("Replacement chain")
        for x in c.lineage():
            tag = "chip" if x is c else None
            d.line(f"  {x.card_id} {x.masked_number} [{x.status.current}] issued {x.issued_on}", tag)
        if c.controls:
            d.h2("Card controls (each with its period)")
            d.table(["Control", "Type", "Value", "Period"],
                    [[k.control_id, k.control_type, k.value or "", str(k.period)] for k in c.controls])
        d.h2("Payments across the whole chain (search_transactions)")
        hits = bank.search_transactions(card=c)
        d.table(["Txn", "Date", "Card", "Amount", "Status", "Merchant"],
                [[t.txn_id, t.initiated_on, t.card.card_id, f"{t.amount:,.2f}", t.status.current, t.merchant.name]
                 for t in hits])
        if c.events:
            d.h2("Events")
            for on, text in c.events:
                d.line(f"  {on}  {text}")


# ----------------------------------------------------------------------------- cases
class CasesPage(MasterDetailPage):
    title = "Cases"
    subtitle = "Customer cases, risk cases and collections are separate records that can be linked"
    columns = [("Case", 80), ("Class", 170), ("Opened", 85), ("Status", 120)]
    pane_weights = (1, 1)

    def rows(self):
        return [(c, [c.case_id, c.kind, c.opened_on, c.status.current + (" (archived)" if c.archived_on else "")],
                 None if c.is_open else "muted") for c in reversed(list(self.ctl.bank.cases.values()))]

    def show(self, c):
        d = self.detail
        path = class_path(type(c))
        d.h1(f"{c.case_id}", f"class path: {path}")
        d.kv("Summary", c.summary)
        d.kv("Subject", label_of(c.subject))
        d.kv("Status trail", c.status.trail())
        if c.outcome:
            d.kv("Outcome", c.outcome)
        if c.assignments:
            d.kv("Assigned", "; ".join(f"{on} {e}" for on, e in c.assignments))
        if c.linked_cases:
            d.kv("Linked", ", ".join(x.case_id for x in c.linked_cases))
        if isinstance(c, bs.Dispute):
            d.kv("Disputed", f"{c.transaction.txn_id} {bs.fmt(c.disputed_amount)}")
            if c.refund:
                d.kv("Refund", f"{c.refund.txn_id} {bs.fmt(c.refund.amount)}")
        if isinstance(c, bs.RiskCase) and c.restrictions:
            d.h2("Restrictions imposed by this case")
            d.table(["Restriction", "Scope", "Period", "Reason"],
                    [[r.restriction_id, r.scope, str(r.period), r.reason] for r in c.restrictions])
        if isinstance(c, bs.CollectionsCase) and c.promises:
            d.h2("Promises to pay")
            d.table(["Amount", "Due", "Status"],
                    [[bs.fmt(p.amount), p.due_on, p.status.current] for p in c.promises])
        if c.evidence:
            d.h2("Evidence snapshots (never rewritten by later corrections)")
            for ev in c.evidence:
                d.line(f"  {ev.evidence_id} captured {ev.captured_on} by {ev.captured_by}: {ev.description}", "key")
                for k, v in ev.snapshot.items():
                    now = ev.source.detail(k) if hasattr(ev.source, "detail") else None
                    d.write(f"      {k}: {v}")
                    if now is not None and now != v:
                        d.write(f"   (record today: {now})", "warn")
                    d.write("\n")
        if c.notes:
            d.h2("Notes")
            for n in c.notes:
                d.line(f"  {n.on} {n.by}: {n.text}")


# ----------------------------------------------------------------------------- staff and products
class StaffPage(MasterDetailPage):
    title = "Staff"
    subtitle = "Roles are dated assignments; every approval keeps the role held when it was made"
    columns = [("Employee", 160), ("Role now", 160), ("Branch", 80), ("Status", 80)]

    def rows(self):
        out = []
        for e in sorted(self.ctl.bank.employees.values(), key=lambda e: e.person.name):
            a = e.current_assignment()
            out.append((e, [e.person.name, a.role if a else "-", a.branch.code if a else "-", e.status.current],
                        None if a else "muted"))
        return out

    def show(self, e):
        d, bank = self.detail, self.ctl.bank
        d.h1(e.person.name, f"{e.employee_no}, hired {e.hired_on}")
        d.kv("Employment", e.status.trail())
        d.h2("Role history")
        d.table(["Role", "Branch", "Period"], [[a.role, a.branch.code, str(a.period)] for a in e.assignments])
        approvals = [a for a in bank.approvals if a.approver is e]
        d.h2("Approvals made (role frozen at the time)")
        d.table(["Approval", "Decision", "Subject", "Role then", "On"],
                [[a.approval_id, a.decision, a.subject, a.role_at_time, a.decided_on] for a in approvals])
        managed = [p.name for p in bank.parties.values()
                   if p.relationship and p.relationship.manager_on(bank.today) is e]
        if managed:
            d.h2("Customers managed today")
            d.line("  " + ", ".join(managed))


class ProductsPage(MasterDetailPage):
    title = "Products and branches"
    subtitle = "Withdrawn products stay valid for existing holders; closed branches keep their history"
    columns = [("Code", 110), ("Name", 200), ("Kind", 90), ("Status", 110)]

    def rows(self):
        out = [(p, [p.code, p.name, p.category, p.sale_status.current],
                None if p.sale_status.current == "ON_SALE" else "warn") for p in self.ctl.bank.products.values()]
        out += [(b, [b.code, b.name, "BRANCH", b.status.current], None if b.is_open else "muted")
                for b in self.ctl.bank.branches.values()]
        return out

    def show(self, x):
        d, bank = self.detail, self.ctl.bank
        if isinstance(x, bs.Branch):
            d.h1(str(x), x.city)
            d.kv("Status trail", x.status.trail())
            if x.merged_into:
                d.kv("Merged into", str(x.merged_into))
            d.kv("Vault cash", bs.fmt(-x.vault.ledger_balance()))
            staff = [e for e in bank.employees.values() if any(a.branch is x for a in e.assignments)]
            d.h2("Staff who ever worked here")
            d.table(["Employee", "Role", "Period"],
                    [[e.person.name, a.role, str(a.period)] for e in staff for a in e.assignments if a.branch is x])
            return
        d.h1(x.name, f"{x.code}  ({x.category})")
        d.kv("Sale status", x.sale_status.trail())
        d.h2("Terms versions")
        d.table(["Version", "From", "Terms"], [[f"v{v.version_no}", v.effective_from,
                                                ", ".join(f"{k}={val}" for k, val in v.terms.items())]
                                               for v in x.terms_versions])
        holders = [a for a in bank.arrangements.values() if a.product is x]
        d.h2("Held by")
        d.table(["Arrangement", "Holder", "Pinned terms", "Status"],
                [[a.number, ", ".join(h.name for h in a.holders), f"v{a.terms.version_no}", a.status.current]
                 for a in holders])


class ClassModelPage(MasterDetailPage):
    title = "Class model"
    subtitle = ("Teaching view, not a bank screen: the inheritance tree read from the code at runtime, "
                "what each level adds, lifecycles and live object counts")
    columns = [("Class", 240), ("Level", 55), ("Live objects", 95)]

    def rows(self):
        own = self.ctl.instance_counts()
        classes = bs.domain_classes()
        counts = {c: sum(n for k, n in own.items() if issubclass(k, c)) for c in classes}
        local = set(classes)
        children = {c: sorted((s for s in classes if s.__bases__[0] is c), key=lambda s: s.__name__) for c in classes}
        out = []

        def walk(c, depth):
            name = c.__name__ + ("  «abstract»" if inspect.isabstract(c) else "")
            out.append((c, [("    " * depth) + ("-> " if depth else "") + name, depth + 1,
                            counts.get(c, 0)], None if depth else "ok"))
            for s in children[c]:
                walk(s, depth + 1)
        for c in classes:
            if c.__bases__[0] not in local and children[c]:
                walk(c, 0)
        for c in sorted((c for c in classes if c.__bases__[0] not in local and not children[c]),
                        key=lambda c: c.__name__):
            out.append((c, [c.__name__ + "  (standalone)", 1, counts.get(c, 0)], "muted"))
        return out

    def show(self, c):
        d = self.detail
        chain = class_path(c)
        d.h1(c.__name__, f"inheritance: {chain}")
        d.line(inspect.cleandoc(c.__doc__ or ""))
        if inspect.isabstract(c):
            d.kv("Abstract", "cannot be created; subclasses must implement "
                 + ", ".join(sorted(m + "()" for m in c.__abstractmethods__)), "warn")
        consts, methods = bs._own_members(c)
        attrs = bs._own_attributes(c)
        d.h2("Added at this level")
        d.kv("Class constants", ", ".join(consts) or "-")
        d.kv("Attributes", ", ".join(attrs) or "(inherits all attributes)")
        d.kv("Methods", ", ".join(m for m in methods) or "(no new methods)")
        for attr in ("LIFECYCLE", "SALE_LIFECYCLE"):
            lifecycle = getattr(c, attr, None)
            if isinstance(lifecycle, bs.Lifecycle):
                own = "declared here" if attr in c.__dict__ else "inherited"
                d.h2(f"Lifecycle ({own}; enforced on every status change)")
                for frm, moves in lifecycle.transitions.items():
                    for to, trigger in moves.items():
                        d.line(f"{frm} -> {to}   ({trigger})")
                d.kv("Final", ", ".join(sorted(lifecycle.final)))
        subs = [s.__name__ for s in bs.domain_classes() if s.__bases__[0] is c]
        if subs:
            d.kv("Subclasses", ", ".join(subs))


# ----------------------------------------------------------------------------- operations
class _Fixed:
    """Stands in for an input widget whose value is fixed (the signed-in member of staff)."""

    def __init__(self, text):
        self.text = text

    def get(self):
        return self.text


class OperationSpec:
    """One console operation: a label, its input fields and the Bank call that performs it.

    A field of kind ("actor", roles) is the member of staff performing the operation: when
    someone is signed in it is filled in with them and not asked for. Those roles also
    decide who sees the form by default; forms without an actor are customer instructions
    that any member of staff may key in."""

    def __init__(self, group, label, fields, call, hint=""):
        self.group, self.label, self.fields, self.call, self.hint = group, label, fields, call, hint
        actors = [k for _n, k in fields if isinstance(k, tuple) and k[0] == "actor"]
        self.roles = actors[0][1] if actors else None

    def allowed_for(self, employee, on):
        """True if this employee's role may perform the operation (or if nobody is signed in)."""
        if not isinstance(employee, bs.Employee) or self.roles is None:
            return True
        assignment = employee.role_on(on)
        return assignment is not None and assignment.role in self.roles


def _date(text, required=True):
    """Parse YYYY-MM-DD from a form field (blank allowed when not required)."""
    text = text.strip()
    if not text and not required:
        return None
    return date.fromisoformat(text)


def _optional_money(text):
    return bs.money(text) if text.strip() else None


def _terms(text):
    """Parse 'monthly_fee=500, annual_rate=0.05' into keyword arguments (numbers stay text
    so the model's Decimal handling applies)."""
    out = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        if "=" not in part:
            raise ValueError(f"'{part}' is not key=value")
        key, value = (x.strip() for x in part.split("=", 1))
        out[key] = value
    return out


ALL_ROLES = sorted(bs.Bank.BRANCH_ROLES | bs.Bank.COMPLIANCE_ROLES | bs.Bank.CREDIT_ROLES | bs.Bank.CARD_ROLES
                   | bs.Bank.COLLECTIONS_ROLES | bs.Bank.AUDIT_ROLES)


class OperationsPage(Page):
    title = "Operations"
    subtitle = "Every form calls one Bank operation; refusals show the model's own rule"

    def build(self):
        tabs = ttk.Notebook(self.content)
        tabs.pack(fill="both", expand=True)
        forms = ttk.Frame(tabs, padding=12)
        checks = ttk.Frame(tabs, padding=12)
        tabs.add(forms, text="  Operation forms  ")
        tabs.add(checks, text="  Guided rule checks  ")
        self._build_forms(forms)
        self._build_checks(checks)

    # --------------------------------------------------------------- forms
    def _specs(self):
        b = CurrentBank(self.ctl)          # "Reset data" swaps the bank; the forms must follow
        amt = bs.money
        branch = ("actor", bs.Bank.BRANCH_ROLES)
        credit = ("actor", bs.Bank.CREDIT_ROLES)
        compliance = ("actor", bs.Bank.COMPLIANCE_ROLES)
        cards = ("actor", bs.Bank.CARD_ROLES)
        return [
            OperationSpec("Customers", "Register a person",
                          [("Full name", "text"), ("Date of birth (YYYY-MM-DD)", "text"), ("Registered by", branch)],
                          lambda v: b.register_person(v[0], _date(v[1]), v[2]),
                          "Creates one Person record; roles are added later, never as subclasses."),
            OperationSpec("Customers", "Register a company",
                          [("Legal name", "text"), ("Registration number", "text"), ("Registered address", "text"),
                           ("Incorporated on (YYYY-MM-DD)", "text"), ("Registered by", branch)],
                          lambda v: b.register_company(v[0], v[1], v[2], _date(v[3]), v[4])),
            OperationSpec("Customers", "Add an identity document",
                          [("Party", "party"), ("Document type", ("choice", ["CNIC", "PASSPORT", "INCORPORATION_CERT",
                                                                              "TRUST_DEED", "SOURCE_OF_WEALTH"])),
                           ("Number", "text"), ("Issued on (YYYY-MM-DD)", "text"),
                           ("Expires on (blank = never)", "text"), ("Filed by", branch)],
                          lambda v: b.add_identity_document(v[0], v[1], v[2], _date(v[3]), _date(v[4], False), v[5])),
            OperationSpec("Customers", "Verify a party against a document",
                          [("Document", "document"), ("Checked by", branch)],
                          lambda v: b.verify_party(v[0].party, v[0], v[1]),
                          "PASS only if the document is valid today; a FAIL is kept too."),
            OperationSpec("Customers", "Appoint a director / trustee",
                          [("Organisation", "org"), ("Person", "person"), ("Recorded by", branch)],
                          lambda v: b.appoint_officer(v[0], v[1], v[2])),
            OperationSpec("Customers", "Onboard as a customer",
                          [("Party", "party"), ("Segment", ("choice", sorted(bs.Bank.SEGMENTS))),
                           ("Trading name (sole traders)", "text"), ("Branch employee", branch)],
                          lambda v: b.become_customer(v[0], v[3], v[1], v[2] or None),
                          "Refused if the party or its directors/owners are not verified today."),
            OperationSpec("Customers", "Open an account",
                          [("Account type", ("choice", ["CurrentAccount", "SavingsAccount"])),
                           ("Product", "deposit_product"), ("Holder", "customer"), ("Branch employee", branch)],
                          lambda v: b.open_deposit_account(getattr(bs, v[0]), v[1], [v[2]], v[3])),
            OperationSpec("Customers", "Grant a mandate",
                          [("Organisation", "org"), ("Person", "person"),
                           ("Capabilities", ("choice", ["PAYMENTS", "PAYMENTS,CARD", "PAYMENTS,BORROWING,CARD",
                                                        "CARD", "VIEW"])),
                           ("Limit (blank = unlimited)", "text"), ("Second signatory above (blank = never)", "text"),
                           ("Granted by", branch)],
                          lambda v: b.grant_mandate(v[0], v[1], set(v[2].split(",")), _optional_money(v[3]), v[5],
                                                    _optional_money(v[4]))),
            OperationSpec("Customers", "Revoke a mandate",
                          [("Mandate", "mandate"), ("Reason", "text"), ("Recorded by", branch)],
                          lambda v: b.revoke_mandate(v[0], v[1] or "authority withdrawn", v[2]),
                          "The mandate's period closes; payments made under it stay provable."),
            OperationSpec("Customers", "Register a charity / trust",
                          [("Name", "text"), ("Registration number", "text"), ("Address", "text"), ("Registered by", branch)],
                          lambda v: b.register_charity(v[0] or "Console Trust", v[1] or "TR-0000", v[2] or "Lahore", v[3]),
                          "A charity needs two verified trustees before it can be onboarded."),
            OperationSpec("Customers", "Record a beneficial owner",
                          [("Organisation", "org"), ("Person", "person"), ("Percentage", "text"), ("Recorded by", branch)],
                          lambda v: b.record_beneficial_owner(v[0], v[1], v[2] or "25", v[3]),
                          "Owners at or above 25% must be verified before the organisation is."),
            OperationSpec("Customers", "End a director / trustee role",
                          [("Organisation", "org"), ("Person", "person"), ("Reason", "text"), ("Recorded by", branch)],
                          lambda v: b.end_officer_role(v[0], v[1], v[2] or "resigned", v[3]),
                          "The office record stays with its dates; only its period closes."),
            OperationSpec("Customers", "Correct a recorded detail",
                          [("Party", "party"), ("Detail", ("choice", ["registered_address", "name"])),
                           ("Correct value", "text"), ("Reason", "text"), ("Corrected by", branch)],
                          lambda v: b.correct_party_detail(v[0], v[1], v[2] or "corrected value", v[3] or "data correction", v[4]),
                          "The old value is kept; case evidence captured before keeps showing it."),
            OperationSpec("Customers", "Assign a relationship manager",
                          [("Customer", "customer"), ("Relationship manager", ("staff", {"RELATIONSHIP_MANAGER"})),
                           ("Assigned by", branch)],
                          lambda v: b.assign_relationship_manager(v[0], v[1], v[2])),
            OperationSpec("Customers", "End a customer relationship",
                          [("Customer", "customer"), ("Reason", "text"), ("Recorded by", branch)],
                          lambda v: b.end_relationship(v[0], v[1] or "customer request", v[2]),
                          "Refused while the customer still holds open products."),
            OperationSpec("Accounts", "Open a term deposit",
                          [("Term-deposit product", "term_product"), ("Payout account", "account"), ("Branch employee", branch)],
                          lambda v: b.open_deposit_account(bs.FixedTermDeposit, v[0], list(v[1].holders), v[2], v[1]),
                          "Same holders as the payout account; fund it with an own-account transfer."),
            OperationSpec("Accounts", "Break a term deposit early",
                          [("Term deposit", "term_deposit"), ("Reason", "text"), ("Branch employee", branch)],
                          lambda v: b.break_term_deposit(v[0], v[2], v[1] or "customer needs the funds"),
                          "Interest is forfeited and the penalty in the pinned terms is charged."),
            OperationSpec("Accounts", "Close an account",
                          [("Account", "account"), ("Reason", "text"), ("Branch employee", branch)],
                          lambda v: b.close_account(v[0], v[1] or "customer request", v[2]),
                          "Needs a zero balance, no holds, no payment in progress and no live financing."),
            OperationSpec("Accounts", "Charge a fee",
                          [("Account", "account"), ("Fee code", "text"), ("Amount", "amount")],
                          lambda v: b.charge_fee(v[0], v[1] or "SERVICE", amt(v[2]))),
            OperationSpec("Accounts", "Produce a statement",
                          [("Account", "account"), ("From (YYYY-MM-DD)", "text"), ("To (YYYY-MM-DD)", "text")],
                          lambda v: b.generate_statement(v[0], _date(v[1]), _date(v[2])).render()),
            OperationSpec("Accounts", "Move an account to the latest terms",
                          [("Account", "any_arrangement"), ("Branch employee", branch)],
                          lambda v: b.migrate_terms(v[0], v[1]),
                          "Only on request: old customers keep their pinned terms otherwise."),
            OperationSpec("Payments", "Add a beneficiary",
                          [("Owner (customer)", "customer"), ("Nickname", "text"), ("Bank", "text"),
                           ("Account number", "text"), ("Account title", "text"), ("Added by", "person")],
                          lambda v: b.add_beneficiary(v[0], v[1] or "New payee", v[2] or "HBL", v[3] or "0000000000",
                                                      v[4] or v[1] or "New payee", v[5])),
            OperationSpec("Payments", "Transfer to a beneficiary",
                          [("From account", "account"), ("Beneficiary", "beneficiary"), ("Amount", "amount"),
                           ("Instructed by", "person")],
                          lambda v: b.initiate_transfer(v[0], v[1], amt(v[2]), v[3]),
                          "Checks the mandate, restrictions, funds, dual control and the review threshold."),
            OperationSpec("Payments", "Pay a bill",
                          [("From account", "account"), ("Biller", "biller"), ("Consumer reference", "text"),
                           ("Amount", "amount"), ("Instructed by", "person")],
                          lambda v: b.pay_bill(v[0], v[1], v[2], amt(v[3]), v[4])),
            OperationSpec("Payments", "Own-account transfer",
                          [("From account", "account"), ("To account", "account"), ("Amount", "amount"),
                           ("Instructed by", "person")],
                          lambda v: b.transfer_between_accounts(v[0], v[1], amt(v[2]), v[3])),
            OperationSpec("Payments", "Authorise a pending payment",
                          [("Payment", "awaiting"), ("Second signatory", "person")],
                          lambda v: b.authorise_payment(v[0], v[1])),
            OperationSpec("Payments", "Release a held payment",
                          [("Payment", "held"), ("Compliance employee", ("actor", bs.Bank.COMPLIANCE_ROLES))],
                          lambda v: b.release_transaction(v[0], v[1], "released from the console")),
            OperationSpec("Payments", "Reverse (refund) a transaction",
                          [("Transaction", "posted"), ("Amount (blank = all)", "text"), ("Reason", "text"),
                           ("Employee", ("actor", bs.Bank.REVERSAL_ROLES))],
                          lambda v: b.reverse_transaction(v[0], amt(v[1]) if v[1] else None, v[2] or "console", v[3])),
            OperationSpec("Payments", "Cancel a pending payment",
                          [("Payment", "awaiting"), ("Cancelled by (signatory)", "person"), ("Reason", "text")],
                          lambda v: b.cancel_pending_payment(v[0], v[1], v[2] or "no longer needed")),
            OperationSpec("Payments", "Reject a held payment",
                          [("Payment", "held"), ("Compliance employee", compliance), ("Reason", "text")],
                          lambda v: b.reject_held_transaction(v[0], v[1], v[2] or "rejected after review")),
            OperationSpec("Payments", "Amend a beneficiary",
                          [("Beneficiary", "all_beneficiary"), ("New bank", "text"), ("New account number", "text"),
                           ("New account title", "text"), ("Changed by", "person")],
                          lambda v: b.amend_beneficiary(v[0], v[1] or "HBL", v[2] or "1111222233", v[3] or v[0].nickname, v[4]),
                          "A new version; transfers already sent keep the version they used."),
            OperationSpec("Payments", "Deactivate a beneficiary",
                          [("Beneficiary", "beneficiary"), ("Reason", "text"), ("By", "person")],
                          lambda v: b.deactivate_beneficiary(v[0], v[1] or "no longer used", v[2])),
            OperationSpec("Payments", "Create a standing order",
                          [("From account", "account"), ("Beneficiary", "beneficiary"), ("Amount", "amount"),
                           ("Day of month (1-28)", "text"), ("Created by", "person")],
                          lambda v: b.create_standing_order(v[0], v[1], amt(v[2]), int(v[3] or 1), v[4]),
                          "Authority is checked now, once; the daily batch pays it each month."),
            OperationSpec("Payments", "Cancel a standing order",
                          [("Standing order", "standing_order"), ("Cancelled by", "person"), ("Reason", "text")],
                          lambda v: b.cancel_standing_order(v[0], v[1], v[2] or "customer request")),
            OperationSpec("Payments", "Register a biller",
                          [("Code", "text"), ("Name", "text"), ("Category", ("choice", sorted(bs.Biller.CATEGORIES)))],
                          lambda v: b.register_biller(v[0] or "CONSOLE", v[1] or "Console Biller", v[2])),
            OperationSpec("Payments", "Deactivate a biller",
                          [("Biller", "biller"), ("Reason", "text")],
                          lambda v: b.deactivate_biller(v[0], v[1] or "collection agreement ended")),
            OperationSpec("Cash", "Deposit cash",
                          [("Account", "account"), ("Amount", "amount"), ("Teller", ("actor", {"TELLER"}))],
                          lambda v: b.deposit_cash(v[0], amt(v[1]), v[2])),
            OperationSpec("Cash", "Withdraw cash",
                          [("Account", "account"), ("Amount", "amount"), ("Teller", ("actor", {"TELLER"})),
                           ("Presented by", "person")],
                          lambda v: b.withdraw_cash(v[0], amt(v[1]), v[2], v[3])),
            OperationSpec("Cards", "Card purchase",
                          [("Card", "card"), ("Merchant", "merchant"), ("Amount", "amount"),
                           ("Channel", ("choice", ["POS", "ONLINE", "ATM"]))],
                          lambda v: b.card_purchase(v[0], v[1], amt(v[2]), v[3])),
            OperationSpec("Cards", "Record a merchant",
                          [("Merchant name", "text"),
                           ("Category", ("choice", sorted(bs.Merchant.CATEGORIES))),
                           ("Country", ("choice", ["PK", "AE", "GB", "US"]))],
                          lambda v: b.record_merchant(v[0] or "Console merchant", v[1], v[2]),
                          "As the card network presents it; card controls check its category and country."),
            OperationSpec("Cards", "Issue a card",
                          [("Card product", "card_product"), ("Account", "account"), ("Cardholder", "person"),
                           ("Daily limit (blank = product default)", "text"), ("Card operations", cards)],
                          lambda v: b.issue_card(v[0], v[1], v[2], v[4], _optional_money(v[3])),
                          "The cardholder must hold the account or have a live CARD mandate."),
            OperationSpec("Cards", "Change a daily limit",
                          [("Card", "card"), ("New daily limit", "amount"), ("Card operations", cards)],
                          lambda v: b.change_card_limit(v[0], amt(v[1]), v[2]),
                          "From today; earlier payments were checked against the limit of their day."),
            OperationSpec("Cards", "Record a found card",
                          [("Card", "card"), ("Card operations", cards), ("Note", "text")],
                          lambda v: b.record_card_found(v[0], v[1], v[2] or "card handed in; destroyed")),
            OperationSpec("Cards", "Reactivate a lost card",
                          [("Card", "card"), ("Card operations", cards)],
                          lambda v: b.reactivate_card(v[0], v[1]),
                          "Only a LOST card that was never replaced; stolen or replaced cards never."),
            OperationSpec("Cards", "Merchant refund",
                          [("Card payment", "card_payment"), ("Amount", "amount"), ("Reason", "text")],
                          lambda v: b.merchant_refund(v[0], amt(v[1]), v[2] or "goods returned"),
                          "A new credit from the merchant; the purchase stays POSTED."),
            OperationSpec("Cards", "Correct a card payment (re-post)",
                          [("Card payment", "card_payment"), ("Corrected amount", "amount"), ("Reason", "text"),
                           ("Card operations", cards)],
                          lambda v: b.repost_card_payment(v[0], amt(v[1]), v[2] or "merchant corrected amount", v[3]),
                          "Full reversal of the original plus a new, linked payment."),
            OperationSpec("Cards", "Report a card",
                          [("Card", "card"), ("Report", ("choice", ["LOST", "STOLEN", "DAMAGED"])),
                           ("Reported by", "person")],
                          lambda v: b.report_card(v[0], v[1], v[2])),
            OperationSpec("Cards", "Replace a blocked card",
                          [("Card", "card"), ("Card operations", ("actor", bs.Bank.CARD_ROLES))],
                          lambda v: b.replace_card(v[0], v[1])),
            OperationSpec("Cards", "Switch on a card control",
                          [("Card", "card"), ("Control", ("choice", sorted(bs.CardControl.TYPES))),
                           ("Category (for MERCHANT_CATEGORY)", "text"), ("Set by (cardholder)", "person")],
                          lambda v: b.add_card_control(v[0], v[1], v[3], v[2] or None)),
            OperationSpec("Cards", "Switch off a card control",
                          [("Control", "control"), ("By (cardholder)", "person")],
                          lambda v: b.remove_card_control(v[0], v[1])),
            OperationSpec("Cases & compliance", "Impose a restriction",
                          [("Customer", "customer"), ("Scope", ("choice", ["DEBIT_BLOCK", "FULL_FREEZE"])),
                           ("Reason", "text"), ("Compliance employee", ("actor", bs.Bank.COMPLIANCE_ROLES))],
                          lambda v: b.impose_restriction(v[0], v[1], v[2] or "console review", v[3])),
            OperationSpec("Cases & compliance", "Lift a restriction",
                          [("Restriction", "restriction"), ("Reason", "text"), ("Compliance employee", ("actor", bs.Bank.COMPLIANCE_ROLES))],
                          lambda v: b.lift_restriction(v[0], v[1] or "cleared", v[2])),
            OperationSpec("Cases & compliance", "Open a dispute",
                          [("Payment", "posted_payment"), ("Amount", "amount"),
                           ("Reason", ("choice", sorted(bs.Chargeback.REASON_CODES))), ("Contact", "person"),
                           ("Employee", ("actor", bs.Bank.BRANCH_ROLES))],
                          lambda v: b.open_dispute(v[0], amt(v[1]), v[3], "BRANCH", v[4], v[2]),
                          "Reason codes follow the card schemes' dispute categories."),
            OperationSpec("Cases & compliance", "Resolve a dispute",
                          [("Dispute", "open_dispute"), ("Outcome", ("choice", ["UPHELD", "PARTIALLY_UPHELD", "REJECTED"])),
                           ("Amount given back (0 = none)", "text"), ("Employee", ("actor", bs.Bank.REVERSAL_ROLES))],
                          lambda v: b.resolve_dispute(v[0], v[1], _optional_money(v[2]) or None, v[3]),
                          "Card payments: a Chargeback against the merchant; other payments: a Reversal."),
            OperationSpec("Cases & compliance", "Log a complaint",
                          [("Customer", "customer"), ("Summary", "text"),
                           ("Category", ("choice", ["PAYMENT_DELAY", "SERVICE", "FEES", "CARD", "OTHER"])),
                           ("Contact person", "person"), ("Recorded by", branch)],
                          lambda v: b.log_complaint(v[0], v[1] or "customer complaint", "BRANCH", v[3], v[2], v[4])),
            OperationSpec("Cases & compliance", "Record a service request",
                          [("Customer", "customer"),
                           ("Request", ("choice", ["STATEMENT_COPY", "ADDRESS_CHANGE", "CHEQUE_BOOK", "LIMIT_REVIEW"])),
                           ("Contact person", "person"), ("Recorded by", branch)],
                          lambda v: b.raise_service_request(v[0], v[1], v[2], "BRANCH", v[3])),
            OperationSpec("Cases & compliance", "Raise a fraud alert",
                          [("Customer", "customer"), ("Rule", ("choice", ["UNUSUAL_PATTERN", "LARGE_FIRST_TIME_TRANSFER",
                                                                          "MULTIPLE_FAILED_ATTEMPTS"]))],
                          lambda v: b.raise_fraud_alert(v[0], v[1]),
                          "Normally raised by monitoring; an alert may turn out to be a false positive."),
            OperationSpec("Cases & compliance", "Open an investigation",
                          [("Customer", "customer"), ("Summary", "text"), ("Link to alert", "alert"),
                           ("Compliance employee", compliance)],
                          lambda v: b.open_investigation(v[0], v[1] or "compliance review", v[3], linked=[v[2]])),
            OperationSpec("Cases & compliance", "Add evidence (snapshot)",
                          [("Case", "open_case"), ("Description", "text"), ("Party on file", "party"),
                           ("Recorded by", compliance)],
                          lambda v: b.add_evidence(v[0], v[1] or "record at review time", v[2],
                                                   {"name": v[2].name,
                                                    "registered_address": v[2].detail("registered_address")}, v[3]),
                          "Freezes the party's details as they are now; later corrections do not change it."),
            OperationSpec("Cases & compliance", "Assign a case",
                          [("Case", "open_case"), ("Employee", "employee"), ("Assigned by", branch)],
                          lambda v: b.assign_case(v[0], v[1], v[2]),
                          "Each kind of case says which roles may work it."),
            OperationSpec("Cases & compliance", "Close a case",
                          [("Case", "open_case"), ("Outcome", "text"), ("Closed by", ("actor", None))],
                          lambda v: b.close_case(v[0], v[1] or "resolved", v[2]),
                          "A risk case refuses to close while its own restriction is in force."),
            OperationSpec("Lending", "Apply for financing",
                          [("Applicant", "customer"), ("Amount", "amount"), ("Months", "text"),
                           ("Submitted by", "person")],
                          lambda v: b.submit_financing_application(
                              v[0], next(p for p in b.products.values() if p.category == "FINANCING"),
                              amt(v[1]), int(v[2] or 12), "console application", v[3])),
            OperationSpec("Lending", "Decide an application",
                          [("Application", "application"), ("Decision", ("choice", ["APPROVE", "DECLINE"])),
                           ("Annual rate", "text"), ("Conditions (comma-separated, optional)", "text"),
                           ("Credit employee", credit)],
                          lambda v: b.decide_application(v[0], v[4], v[1] == "APPROVE", None, v[2] or "0.18",
                                                         [c.strip() for c in v[3].split(",") if c.strip()]),
                          "Each credit role may approve only up to its delegated limit."),
            OperationSpec("Lending", "Attach a supporting document",
                          [("Application", "open_app"), ("Document", "text"), ("Filed by", credit)],
                          lambda v: b.attach_application_document(v[0], v[1] or "financial statements", v[2])),
            OperationSpec("Lending", "Satisfy a condition",
                          [("Condition", "condition"), ("Evidence", "text"), ("Recorded by", branch)],
                          lambda v: b.satisfy_condition(v[0], v[1] or "original on file", v[2])),
            OperationSpec("Lending", "Disburse financing",
                          [("Approved application", "approved_app"), ("Settlement account", "account"),
                           ("First installment due (YYYY-MM-DD)", "text"), ("Credit employee", credit)],
                          lambda v: b.disburse_financing(v[0], v[1], _date(v[2]), v[3]),
                          "Refused until every condition is met."),
            OperationSpec("Lending", "Repay financing",
                          [("Agreement", "financing"), ("Amount", "amount"), ("From account", "account")],
                          lambda v: b.repay_financing(v[0], amt(v[1]), v[2]),
                          "Oldest installment first, interest before principal."),
            OperationSpec("Lending", "Restructure financing",
                          [("Agreement", "financing"), ("New term in months", "text"), ("Annual rate", "text"),
                           ("First installment due (YYYY-MM-DD)", "text"), ("Reason", "text"), ("Credit employee", credit)],
                          lambda v: b.restructure_financing(v[0], int(v[1] or 12), v[2] or "0.17", _date(v[3]),
                                                            v[4] or "cash-flow difficulty", v[5]),
                          "A new schedule version; paid installments stay PAID on the old one."),
            OperationSpec("Lending", "Settle financing early",
                          [("Agreement", "financing"), ("From account", "account"), ("Credit employee", credit)],
                          lambda v: b.settle_financing(v[0], v[1], v[2]),
                          "Principal plus interest already due; future interest is waived."),
            OperationSpec("Lending", "Record a collections contact",
                          [("Collections case", "collections_case"), ("Collections officer", ("actor", bs.Bank.COLLECTIONS_ROLES)),
                           ("Outcome", "text"), ("Promised amount (optional)", "text"), ("Promised by (YYYY-MM-DD, optional)", "text")],
                          lambda v: b.record_collections_contact(v[0], v[1], v[2] or "customer contacted",
                                                                 _optional_money(v[3]), _date(v[4], False))),
            OperationSpec("Organisation", "Open a branch",
                          [("Code", "text"), ("Name", "text"), ("City", "text")],
                          lambda v: b.open_branch(v[0] or "NEW-01", v[1] or "New Branch", v[2] or "Lahore")),
            OperationSpec("Organisation", "Hire an employee",
                          [("Person", "person"), ("Role", ("choice", ALL_ROLES)), ("Branch", "branch")],
                          lambda v: b.hire_employee(v[0], v[1], v[2])),
            OperationSpec("Organisation", "Change an employee's role",
                          [("Employee", "employee"), ("New role", ("choice", ALL_ROLES)), ("Branch", "branch")],
                          lambda v: b.change_role(v[0], v[1], v[2]),
                          "Old approvals keep the role held when they were made."),
            OperationSpec("Organisation", "Record an employee exit",
                          [("Employee", "employee"), ("Reason", "text")],
                          lambda v: b.record_employee_exit(v[0], v[1] or "resigned"),
                          "Refused while the person is still relationship manager for customers."),
            OperationSpec("Organisation", "Close a branch",
                          [("Branch", "branch"), ("Transfer into", "branch"), ("Authorised by", branch)],
                          lambda v: b.close_branch(v[0], v[1], str(v[2])),
                          "Customers, accounts, staff and vault cash move; opening branches stay recorded."),
            OperationSpec("Products", "Define a product",
                          [("Code", "text"), ("Name", "text"), ("Category", ("choice", sorted(bs.ProductDefinition.CATEGORIES))),
                           ("Terms (key=value, ...)", "text")],
                          lambda v: b.define_product(v[0] or "NEW", v[1] or "New product", v[2], **_terms(v[3])),
                          "e.g. monthly_fee=500, annual_rate=0.05, term_months=12"),
            OperationSpec("Products", "Publish new terms",
                          [("Product", "product"), ("Effective from (YYYY-MM-DD)", "text"), ("Changes (key=value, ...)", "text")],
                          lambda v: b.revise_product_terms(v[0], _date(v[1]), **_terms(v[2])),
                          "Existing customers stay on the version they were sold."),
            OperationSpec("Products", "Withdraw from sale",
                          [("Product", "product"), ("Reason", "text")],
                          lambda v: b.withdraw_from_sale(v[0], v[1] or "replaced by a newer product"),
                          "New customers cannot buy it; existing customers keep it."),
            OperationSpec("Records", "Archive a finished record",
                          [("Account", "any_arrangement"), ("Employee", ("actor", bs.Bank.BRANCH_ROLES))],
                          lambda v: b.archive_record(v[0], v[1])),
            OperationSpec("Records", "Request deletion",
                          [("Account", "any_arrangement"), ("Employee", ("actor", bs.Bank.BRANCH_ROLES))],
                          lambda v: b.request_deletion(v[0], v[1])),
        ]

    def _field_options(self, kind):
        ctl = self.ctl
        if isinstance(kind, tuple) and kind[0] == "actor":
            allowed = ctl.staff(kind[1]) if kind[1] else ctl.staff()
            others = [e for e in ctl.staff() if e not in allowed]
            return [(nice(label_of(x)), x) for x in allowed + others]
        if isinstance(kind, tuple) and kind[0] == "staff":
            # staff allowed to do this operation are listed first; the others stay available
            # so that a refusal by the model can still be demonstrated
            allowed = ctl.staff(kind[1])
            others = [e for e in ctl.staff() if e not in allowed]
            return [(nice(label_of(x)), x) for x in allowed + others]
        if isinstance(kind, tuple):
            return [(nice(x), x) for x in kind[1]]      # friendly words shown, exact codes passed on
        source = {
            "account": ctl.deposit_accounts(),
            "any_arrangement": list(ctl.bank.arrangements.values()),
            "beneficiary": [x for x in ctl.bank.beneficiaries.values() if x.status.current == "ACTIVE"],
            "biller": [x for x in ctl.bank.billers.values() if x.status.current == "ACTIVE"],
            "merchant": sorted(ctl.bank.merchants.values(), key=lambda m: m.name),
            "person": ctl.persons(),
            "customer": ctl.customers(),
            "staff": ctl.staff(),
            "card": list(ctl.bank.cards.values()),
            "awaiting": ctl.payments_in("AWAITING_AUTHORISATION"),
            "held": ctl.payments_in("HELD_FOR_REVIEW"),
            "posted": [t for t in ctl.bank.transactions.values()
                       if t.status.current in ("POSTED", "PARTIALLY_REVERSED") and not isinstance(t, bs.Reversal)],
            "posted_payment": ctl.payments_in("POSTED", "PARTIALLY_REVERSED"),
            "restriction": ctl.live_restrictions(),
            "control": ctl.live_controls(),
            "application": [a for a in ctl.bank.applications.values() if a.status.current == "SUBMITTED"],
            "party": sorted(ctl.bank.parties.values(), key=lambda p: p.name),
            "org": sorted((p for p in ctl.bank.parties.values() if isinstance(p, bs.Organization)),
                          key=lambda p: p.name),
            "document": [d for p in ctl.bank.parties.values() for d in p.documents],
            "mandate": [m for p in ctl.bank.parties.values() if isinstance(p, bs.Organization)
                        for m in p.mandates if m.period.end is None],
            "deposit_product": [p for p in ctl.bank.products.values()
                                if p.category in ("CURRENT", "SAVINGS") and p.can_sell(ctl.bank.today)],
            "term_product": [p for p in ctl.bank.products.values() if p.category == "TERM_DEPOSIT"],
            "card_product": [p for p in ctl.bank.products.values() if p.category == "DEBIT_CARD"],
            "product": sorted(ctl.bank.products.values(), key=lambda p: p.code),
            "all_beneficiary": [x for x in ctl.bank.beneficiaries.values() if x.status.current != "DELETED"],
            "standing_order": [x for x in ctl.bank.standing_orders.values() if x.status.current == "ACTIVE"],
            "term_deposit": [a for a in ctl.bank.arrangements.values()
                             if isinstance(a, bs.FixedTermDeposit) and a.status.current == "ACTIVE"],
            "card_payment": [t for t in ctl.payments_in("POSTED", "PARTIALLY_REVERSED") if isinstance(t, bs.CardPayment)],
            "open_app": [a for a in ctl.bank.applications.values() if a.status.current not in ("DISBURSED", "DECLINED")],
            "approved_app": [a for a in ctl.bank.applications.values()
                             if a.status.current in ("APPROVED", "APPROVED_WITH_CONDITIONS")],
            "condition": [c for a in ctl.bank.applications.values() for c in a.conditions if not c.is_met()],
            "financing": [a for a in ctl.bank.arrangements.values()
                          if isinstance(a, bs.FinancingAgreement) and a.status.current in a.USABLE_STATUSES],
            "open_case": [c for c in ctl.bank.cases.values() if c.is_open],
            "open_dispute": [c for c in ctl.bank.cases.values() if isinstance(c, bs.Dispute) and c.is_open],
            "collections_case": [c for c in ctl.bank.cases.values() if isinstance(c, bs.CollectionsCase) and c.is_open],
            "alert": [c for c in ctl.bank.cases.values() if isinstance(c, bs.FraudAlert)],
            "branch": [x for x in ctl.bank.branches.values() if x.status.current == "OPEN"],
            "employee": ctl.staff(),
        }.get(kind)
        return None if source is None else [(nice(label_of(x)), x) for x in source]

    def _build_forms(self, frame):
        t = self.theme
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)
        left = tk.Frame(frame, bg=t.CARD, highlightbackground=t.LINE, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        search_row = tk.Frame(left, bg=t.CARD)
        search_row.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(search_row, text="Find an operation", bg=t.CARD, fg=t.MUTED, font=t.f_small).pack(anchor="w")
        self.search = ttk.Entry(search_row, width=34)
        self.search.pack(fill="x", pady=(2, 0))
        self.search.bind("<KeyRelease>", lambda _e: self._populate())
        self.show_all = tk.BooleanVar(value=False)
        self.show_all_box = ttk.Checkbutton(left, text="Also show what my role may not do",
                                            variable=self.show_all, command=self._populate)
        self.show_all_box.pack(anchor="w", padx=10, pady=(4, 2))
        tree_box = tk.Frame(left, bg=t.CARD)
        tree_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.op_tree = ttk.Treeview(tree_box, show="tree", selectmode="browse", height=22)
        ys = ttk.Scrollbar(tree_box, orient="vertical", command=self.op_tree.yview)
        self.op_tree.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        self.op_tree.column("#0", width=300)
        self.op_tree.pack(fill="both", expand=True)
        self.op_tree.tag_configure("group", font=t.f_bold, foreground=t.INK)
        self.op_tree.tag_configure("other", foreground=t.MUTED)
        self.op_tree.bind("<<TreeviewSelect>>", self._pick_operation)
        self.form_frame = frame
        self.form = Panel(frame, t, "Choose an operation", icon="operations")
        self.form.grid(row=0, column=1, sticky="nsew")
        self.all_specs = self._specs()
        self.specs = {}
        self._seen_user = object()
        self._populate()

    def refresh(self):
        if self.app.user is not self._seen_user:          # a new sign-in: re-filter the forms
            self._populate()

    def _visible(self, spec):
        return self.show_all.get() or spec.allowed_for(self.app.user, self.ctl.today)

    def _populate(self):
        """Fill the tree with the forms the signed-in role may use (or all), matching the search."""
        self._seen_user = self.app.user
        term = self.search.get().strip().lower()
        self.op_tree.delete(*self.op_tree.get_children())
        self.specs, groups = {}, {}
        for spec in self.all_specs:
            if not self._visible(spec):
                continue
            if term and term not in f"{spec.group} {spec.label} {spec.hint}".lower():
                continue
            if spec.group not in groups:
                groups[spec.group] = self.op_tree.insert("", "end", text=spec.group, open=bool(term), tags=("group",))
            mine = spec.allowed_for(self.app.user, self.ctl.today)
            iid = self.op_tree.insert(groups[spec.group], "end", text="   " + spec.label + ("" if mine else "   (not your role)"),
                                      tags=() if mine else ("other",))
            self.specs[iid] = spec
        self._show_guide()

    def _show_guide(self):
        t = self.theme
        self.form.destroy()
        self.form = Panel(self.form_frame, t, "Choose an operation", icon="operations")
        self.form.grid(row=0, column=1, sticky="nsew")
        user = self.app.user
        counts = {}
        for spec in self.specs.values():
            counts[spec.group] = counts.get(spec.group, 0) + 1
        if isinstance(user, bs.Employee):
            a = user.role_on(self.ctl.today)
            who = (f"You are signed in as {user.person.name}, {nice(a.role) if a else 'no current role'}"
                   f"{' at ' + a.branch.name if a else ''}. The list shows the {len(self.specs)} operations "
                   f"your role may perform; you are recorded as the member of staff on each one.")
        else:
            who = f"Nobody is signed in, so all {len(self.specs)} operations are listed and each form asks who acts."
        tk.Label(self.form.body, text=who, bg=t.CARD, fg=t.INK, font=t.f_body, justify="left", anchor="w",
                 wraplength=640).pack(fill="x", pady=(0, 12))
        grid = tk.Frame(self.form.body, bg=t.CARD)
        grid.pack(fill="x")
        for i, (group, n) in enumerate(counts.items()):
            chip = tk.Frame(grid, bg=t.MIST)
            chip.grid(row=i // 3, column=i % 3, sticky="ew", padx=(0, 10), pady=5)
            tk.Label(chip, text=group, bg=t.MIST, fg=t.TEAL, font=t.f_bold, padx=12, pady=6).pack(side="left")
            tk.Label(chip, text=f"{n}", bg=t.MIST, fg=t.MUTED, font=t.f_small, padx=10).pack(side="right")
            grid.columnconfigure(i % 3, weight=1)
        tk.Label(self.form.body, text="Every form calls exactly one Bank operation, so each rule, refusal and "
                                      "audit entry is the model's own. Refused payments are kept on record as "
                                      "failed or declined; other refusals name the rule that stopped them.",
                 bg=t.CARD, fg=t.MUTED, font=t.f_small, justify="left", anchor="w",
                 wraplength=640).pack(fill="x", pady=(14, 0))

    def _pick_operation(self, _event=None):
        sel = self.op_tree.selection()
        if not sel or sel[0] not in self.specs:
            return
        self._render_form(self.specs[sel[0]])

    def _render_form(self, spec):
        t = self.theme
        self.form.destroy()
        self.form = Panel(self.form_frame, t, spec.label, icon="operations")
        self.form.grid(row=0, column=1, sticky="nsew")
        body, self.inputs = self.form.body, []
        body.columnconfigure(1, weight=1)
        if spec.hint:
            tk.Label(body, text=spec.hint, bg=t.CARD, fg=t.MUTED, font=t.f_small, anchor="w", justify="left",
                     wraplength=640).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        user = self.app.user
        for r, (name, kind) in enumerate(spec.fields, start=1):
            is_actor = isinstance(kind, tuple) and kind[0] == "actor"
            tk.Label(body, text="Performed by" if is_actor and isinstance(user, bs.Employee) else name,
                     bg=t.CARD, fg=t.MUTED, font=t.f_bold, anchor="w").grid(row=r, column=0, sticky="w", pady=6,
                                                                           padx=(0, 16))
            if is_actor and isinstance(user, bs.Employee):
                w = _Fixed(nice(label_of(user)))
                chip = tk.Frame(body, bg=t.MIST)
                Avatar(chip, user.person.name, t.MIST, t.TEAL, 24).pack(side="left", padx=(8, 6), pady=4)
                tk.Label(chip, text=f"You - {nice(label_of(user))}", bg=t.MIST, fg=t.TEAL, font=t.f_bold).pack(side="left")
                if not spec.allowed_for(user, self.ctl.today):
                    tk.Label(chip, text="  your role may not do this: the bank will refuse", bg=t.MIST, fg=t.BAD,
                             font=t.f_small).pack(side="left")
                chip.grid(row=r, column=1, sticky="w", pady=6)
                self.inputs.append((w, {w.get(): user}))
                continue
            options = self._field_options(kind)
            if options is None:
                w = ttk.Entry(body, width=40)
                self.inputs.append((w, None))
            else:
                w = ttk.Combobox(body, state="readonly", width=60, values=[o[0] for o in options])
                if options:
                    w.current(0)
                self.inputs.append((w, dict(options)))
            w.grid(row=r, column=1, sticky="ew", pady=6)
        ttk.Button(body, text="Run operation", style="Accent.TButton",
                   command=lambda: self._execute(spec)).grid(row=len(spec.fields) + 1, column=1, sticky="w",
                                                             pady=(14, 0))

    def _execute(self, spec):
        values = []
        for widget, mapping in self.inputs:
            raw = widget.get().strip()
            if mapping is not None:
                if raw not in mapping:
                    messagebox.showwarning("Missing value", "Please choose a value in every list.")
                    return
                values.append(mapping[raw])
            else:
                values.append(raw)
        try:
            outcome = self.ctl.run(spec.label, lambda: spec.call(values))
        except (ValueError, ArithmeticError) as e:
            problem = "an amount or rate is not a number" if isinstance(e, ArithmeticError) else str(e)
            messagebox.showwarning("Check the input", f"The input could not be read: {problem}")
            return
        self.app.show_outcome(outcome)
        self._render_form(spec)

    # --------------------------------------------------------------- guided checks
    def _build_checks(self, frame):
        frame.columnconfigure(0, weight=1)
        intro = ("Each check runs one real operation against the current data and shows the model's answer. "
                 "Run them in order during a demonstration. 'Reset data' in the top bar rebuilds the seeded bank.")
        tk.Label(frame, text=intro, bg=self.theme.BG, fg=self.theme.MUTED, font=self.theme.f_body,
                 wraplength=1000, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 10))
        frame.rowconfigure(1, weight=1)
        scroller = ScrollFrame(frame, self.theme)
        scroller.grid(row=1, column=0, sticky="nsew")
        grid = scroller.inner
        grid.columnconfigure(1, weight=1)
        for i, (title, expect, fn) in enumerate(self._checks()):
            row = tk.Frame(grid, bg=self.theme.CARD, highlightbackground=self.theme.LINE, highlightthickness=1)
            row.grid(row=i, column=0, columnspan=2, sticky="ew", pady=3, padx=(0, 6))
            row.columnconfigure(1, weight=1)
            tk.Label(row, text=f"{i + 1:>2}", bg=self.theme.BRASS, fg="#FFFFFF", font=self.theme.f_bold,
                     width=3).grid(row=0, column=0, rowspan=2, sticky="ns")
            tk.Label(row, text=title, bg=self.theme.CARD, fg=self.theme.INK, font=self.theme.f_bold,
                     anchor="w").grid(row=0, column=1, sticky="w", padx=12, pady=(6, 0))
            tk.Label(row, text="Expected: " + expect, bg=self.theme.CARD, fg=self.theme.MUTED,
                     font=self.theme.f_small, anchor="w").grid(row=1, column=1, sticky="w", padx=12, pady=(0, 6))
            ttk.Button(row, text="Run check", command=lambda t=title, f=fn: self.app.show_outcome(
                self.ctl.run(t, f))).grid(row=0, column=2, rowspan=2, padx=10)

    def _checks(self):
        ctl = self.ctl
        b = lambda: ctl.bank
        person = ctl.find_person
        staff = ctl.find_employee
        ravi = lambda: person("Ravi Textiles (Pvt) Ltd")
        ravi_cur = lambda: next(a for a in b().arrangements.values()
                                if isinstance(a, bs.CurrentAccount) and ravi() in a.holders)
        yarn = lambda: next(x for x in b().beneficiaries.values() if x.nickname == "Lahore Yarn Traders")
        first = lambda status: next(iter(ctl.payments_in(status)), None)

        def need(obj, what):
            if obj is None:
                raise bs.InvalidStateError(f"no {what} left in the current data; press 'Reset data'")
            return obj

        def restrict():
            return b().impose_restriction(ravi(), "DEBIT_BLOCK", "console demonstration", staff("Kamran Javed"))

        def lift():
            live = [r for r in ravi().restrictions if r.period.end is None]
            return b().lift_restriction(need(live[0] if live else None, "live restriction on Ravi"),
                                        "cleared in the console", staff("Kamran Javed"))

        def over_limit_credit():
            app = b().submit_financing_application(
                ravi(), next(p for p in b().products.values() if p.category == "FINANCING"),
                30_000_000, 36, "factory expansion", person("Ayesha Khan"))
            return b().decide_application(app, staff("Zainab Qureshi"), True, 30_000_000, "0.17")

        return [
            ("View-only signatory Noor pays a supplier", "refused and kept as FAILED",
             lambda: b().initiate_transfer(ravi_cur(), yarn(), 50_000, person("Noor Fatima"))),
            ("Hamza authorises his own pending payment", "AuthorityError: initiator cannot be the second signatory",
             lambda: b().authorise_payment(need(first("AWAITING_AUTHORISATION"), "pending payment"),
                                           person("Hamza Sheikh"))),
            ("Ayesha authorises it as second signatory", "posted (or held for review if large)",
             lambda: b().authorise_payment(need(first("AWAITING_AUTHORISATION"), "pending payment"),
                                           person("Ayesha Khan"))),
            ("Teller Farah releases a held payment", "AuthorityError: a teller may not release held payments",
             lambda: b().release_transaction(need(first("HELD_FOR_REVIEW"), "held payment"),
                                             staff("Farah Siddiqui"), "customer asked")),
            ("Compliance (Kamran) releases it", "posted",
             lambda: b().release_transaction(need(first("HELD_FOR_REVIEW"), "held payment"),
                                             staff("Kamran Javed"), "evidence satisfactory")),
            ("Former director Bilal pays from the company", "refused: his mandate ended on 20 Sep 2026",
             lambda: b().initiate_transfer(ravi_cur(), yarn(), 10_000, person("Bilal Ahmed"))),
            ("The stolen-then-destroyed card is used", "DECLINED",
             lambda: b().card_purchase(b().cards["CARD-001"], "Unknown shop", 1_000)),
            ("Online gambling on Hamza's card", "DECLINED by the MERCHANT_CATEGORY control",
             lambda: b().card_purchase(b().cards["CARD-004"], "BetWorld", 2_000, "ONLINE")),
            ("Credit manager approves PKR 30m", "AuthorityError: above the 25m delegated limit",
             over_limit_credit),
            ("Place a debit block on Ravi Textiles", "restriction in force from today", restrict),
            ("Hamza pays while the block is in force", "refused and kept as FAILED",
             lambda: b().initiate_transfer(ravi_cur(), yarn(), 10_000, person("Hamza Sheikh"))),
            ("Lift the debit block", "restriction period closed; history kept", lift),
            ("Delete the closed savings account", "InvalidStateError: retain until 2037; archive instead",
             lambda: b().request_deletion(next(a for a in b().arrangements.values()
                                               if isinstance(a, bs.SavingsAccount)), staff("Maryam Tahir"))),
            ("Delete a payee used by past payments", "InvalidStateError: deactivate instead",
             lambda: b().delete_beneficiary(yarn(), staff("Maryam Tahir"))),
        ]


# ----------------------------------------------------------------------------- books and audit
class BooksPage(Page):
    title = "Books and audit"
    subtitle = "Double-entry trial balance on any date, and the append-only audit log"

    def build(self):
        self.content.columnconfigure(0, weight=2, uniform="books")
        self.content.columnconfigure(1, weight=3, uniform="books")
        self.content.rowconfigure(0, weight=1)
        tb = Panel(self.content, self.theme, "Trial balance", "credits positive, debits negative")
        tb.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        bar = tk.Frame(tb.body, bg=self.theme.CARD)
        bar.pack(fill="x", pady=(0, 8))
        tk.Label(bar, text="As at", bg=self.theme.CARD, fg=self.theme.MUTED).pack(side="left")
        self.as_at = ttk.Entry(bar, width=12)
        self.as_at.pack(side="left", padx=8)
        ttk.Button(bar, text="Show", command=self.refresh).pack(side="left")
        self.total = tk.Label(tb.body, text="", bg=self.theme.CARD, font=self.theme.f_bold, anchor="w")
        self.total.pack(fill="x", pady=(0, 6))
        self.tb = DataTable(tb.body, self.theme, [("Account", 95), ("Name", 180), ("Balance", 125)], height=18)
        self.tb.pack(fill="both", expand=True)

        log = Panel(self.content, self.theme, "Audit log", "what changed, who did it, why")
        log.grid(row=0, column=1, sticky="nsew")
        bar2 = tk.Frame(log.body, bg=self.theme.CARD)
        bar2.pack(fill="x", pady=(0, 8))
        tk.Label(bar2, text="Filter", bg=self.theme.CARD, fg=self.theme.MUTED).pack(side="left")
        self.filter = ttk.Entry(bar2, width=30)
        self.filter.pack(side="left", padx=8)
        self.filter.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(bar2, text="Apply", command=self.refresh).pack(side="left")
        self.log = DataTable(log.body, self.theme, [("Date", 85), ("Actor", 150), ("Action", 170),
                                                    ("Subject", 90), ("Detail", 320)], height=18)
        self.log.pack(fill="both", expand=True)

    def refresh(self):
        bank = self.ctl.bank
        if not self.as_at.get():
            self.as_at.insert(0, str(bank.today))
        try:
            on = date.fromisoformat(self.as_at.get().strip())
        except ValueError:
            on = bank.today
        rows, total = bank.trial_balance(on)
        self.tb.set_rows([(r, [r[0], r[1].replace(r[0], "", 1).strip(), f"{r[2]:,.2f}"]) for r in rows if r[2] != 0])
        self.total.config(text=f"Total of all balances: {total:,.2f}   "
                               f"{'the books balance' if total == 0 else 'NOT BALANCED'}",
                          fg=self.theme.OK if total == 0 else self.theme.BAD)
        term = self.filter.get().strip().lower()
        events = [e for e in reversed(bank.audit)
                  if not term or term in f"{e.on} {e.actor} {e.action} {e.subject} {e.detail}".lower()]
        self.log.set_rows([(e, [e.on, e.actor, e.action, e.subject, e.detail],
                            "bad" if "REFUSED" in e.action or "FAILED" in e.action or "DECLINED" in e.action
                            or "BLOCKED" in e.action else None) for e in events[:600]])


# ----------------------------------------------------------------------------- counterparties
class CounterpartiesPage(MasterDetailPage):
    title = "Counterparties"
    subtitle = ("Merchants, billers and payees: external parties the bank pays or is paid by. "
                "They are not customers, so the bank holds no KYC for them")
    columns = [("Kind", 70), ("Name", 172), ("Detail", 172), ("Paid", 44)]
    pane_weights = (3, 2)

    def rows(self):
        bank = self.ctl.bank
        out = []
        for m in sorted(bank.merchants.values(), key=lambda m: m.name):
            out.append((m, ["Merchant", m.name, f"{m.category}, {m.country}", len(m.payments)], None))
        for b in bank.billers.values():
            paid = [t for t in bank.transactions.values() if isinstance(t, bs.BillPayment) and t.biller is b]
            out.append((b, ["Biller", b.name, b.category, len(paid)],
                        "muted" if b.status.current != "ACTIVE" else None))
        for x in bank.beneficiaries.values():
            paid = [t for t in bank.transactions.values() if isinstance(t, bs.TransferPayment) and t.beneficiary is x]
            out.append((x, ["Payee", x.nickname, f"of {x.owner.name}", len(paid)],
                        "muted" if x.status.current != "ACTIVE" else None))
        return out

    def _payments(self, payments, extra):
        self.detail.h2("Payments")
        if not payments:
            self.detail.line("None yet.", "muted")
            return
        self.detail.table(["Txn", "Date", "Amount", "Status", extra[0]],
                          [[t.txn_id, t.initiated_on, f"{t.amount:,.2f}", t.status.current, extra[1](t)]
                           for t in payments])

    def show(self, x):
        d, bank = self.detail, self.ctl.bank
        if isinstance(x, bs.Merchant):
            d.h1(x.name, f"{x.merchant_id}  class: Merchant (standalone, not a Party)")
            d.kv("Category / country", f"{x.category} / {x.country}")
            d.kv("First presented by the card network", x.first_seen)
            d.line("Card controls check the category and country copied onto each payment.", "muted")

            def after(t):
                parts = [f"refund {r.txn_id}" for r in t.refunds]
                parts += [f"{r.label} {r.txn_id}" for r in t.reversals]
                return f"card {t.card.card_id}" + ("; " + ", ".join(parts) if parts else "")
            self._payments(x.payments, ("Card and follow-ups", after))
        elif isinstance(x, bs.Biller):
            d.h1(x.name, f"{x.code}  class: Biller")
            d.kv("Category", x.category)
            d.kv("Status trail", x.status.trail())
            paid = [t for t in bank.transactions.values() if isinstance(t, bs.BillPayment) and t.biller is x]
            self._payments(paid, ("Consumer reference", lambda t: t.consumer_reference))
        else:
            d.h1(x.nickname, f"{x.beneficiary_id}  payee of {x.owner.name}  class: Beneficiary")
            d.kv("Status trail", x.status.trail())
            d.h2("Versions (details are never overwritten)")
            for v in x.versions:
                d.line(f"  {v}")
            paid = [t for t in bank.transactions.values() if isinstance(t, bs.TransferPayment) and t.beneficiary is x]
            self._payments(paid, ("Sent to version", lambda t: f"v{t.beneficiary_version.version}"))


# ----------------------------------------------------------------------------- reports
class ReportsPage(Page):
    title = "Reports"
    subtitle = "Historical questions answered from the records: authority on a date, the audit trail, a day's activity"

    def build(self):
        t = self.theme
        self.content.columnconfigure(0, weight=2, uniform="rep")
        self.content.columnconfigure(1, weight=3, uniform="rep")
        self.content.rowconfigure(0, weight=1)
        left = tk.Frame(self.content, bg=t.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        out = Panel(self.content, t, "Result")
        out.grid(row=0, column=1, sticky="nsew")
        self.out = DetailView(out.body, t)
        self.out.pack(fill="both", expand=True)
        self.choices, self.panels = {}, []

        def panel(title, subtitle, fields, run):
            box = Panel(left, t, title)
            box.pack(fill="x", pady=(0, 12))
            box.body.columnconfigure(1, weight=1)
            tk.Label(box.body, text=subtitle, bg=t.CARD, fg=t.MUTED, font=t.f_small, anchor="w", justify="left",
                     wraplength=420).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
            widgets = []
            for r, (label, kind, default) in enumerate(fields, start=1):
                tk.Label(box.body, text=label, bg=t.CARD, fg=t.MUTED, font=t.f_small,
                         anchor="w").grid(row=r, column=0, sticky="w", padx=(0, 8), pady=2)
                w = ttk.Combobox(box.body, state="readonly") if kind else ttk.Entry(box.body)
                if not kind and default:
                    w.insert(0, default)
                w.grid(row=r, column=1, sticky="ew", pady=2)
                widgets.append((w, kind))
            ttk.Button(box.body, text="Run report", command=lambda: self._run(title, widgets, run)).grid(
                row=len(fields) + 1, column=1, sticky="e", pady=(6, 0))
            self.panels.append((title, widgets, run))

        panel("Who had authority, and when",
              "the mandates a person held for an organisation on a past date",
              [("Organisation", "org", None), ("Person", "person", None), ("On (YYYY-MM-DD)", None, "2026-04-11")],
              self._authority)
        panel("Approvals and authority audit",
              "for auditors and branch managers; every run is itself logged",
              [("Requested by", "staff", None), ("From (YYYY-MM-DD)", None, "2026-01-01"),
               ("To (YYYY-MM-DD)", None, "2026-12-31")],
              self._audit)
        panel("What happened on a day", "the audit log for one date: who did what, and why",
              [("Date (YYYY-MM-DD)", None, "2026-03-02")], self._daily)

    def refresh(self):
        bank = self.ctl.bank
        self.choices = {
            "org": [(p.name, p) for p in sorted(bank.parties.values(), key=lambda p: p.name)
                    if isinstance(p, bs.Organization)],
            "person": [(p.name, p) for p in self.ctl.persons()],
            "staff": [(nice(label_of(e)), e) for e in (self.ctl.staff(bs.Bank.AUDIT_ROLES)
                                                 + [e for e in self.ctl.staff() if e not in self.ctl.staff(bs.Bank.AUDIT_ROLES)])],
        }
        preferred = {"org": "Ravi Textiles (Pvt) Ltd", "person": "Bilal Ahmed"}   # a former director
        for combo, kind in self._combos():
            labels = [label for label, _ in self.choices[kind]]
            combo["values"] = labels
            if combo.get() not in labels and labels:
                combo.set(preferred[kind] if preferred.get(kind) in labels else labels[0])
        if not self.out.text.get("1.0", "end").strip():
            self._run(*self.panels[0])                  # open with a worked example

    def _combos(self):
        found = []

        def walk(widget):
            for c in widget.winfo_children():
                if isinstance(c, ttk.Combobox):
                    found.append(c)
                walk(c)
        walk(self.content.winfo_children()[0])
        kinds = ["org", "person", "staff"]
        return list(zip(found, kinds))

    def _run(self, title, widgets, run):
        values = []
        for w, kind in widgets:
            raw = w.get().strip()
            values.append(dict(self.choices.get(kind, [])).get(raw) if kind else raw)
        self.out.clear()
        self.out.h1(title)
        try:
            run(*values)
        except bs.BankingError as e:
            self.out.line(f"Refused by {type(e).__name__}: {e}", "bad")
        except ValueError as e:
            self.out.line(f"Check the input: {e}", "bad")
        self.out.done()

    def _authority(self, org, person, on):
        on = _date(on)
        held = self.ctl.bank.authority_on(org, person, on)
        self.out.kv("Question", f"What could {person.name} do for {org.name} on {on}?")
        if held:
            for m in held:
                self.out.line(f"  {m}", "ok")
        else:
            self.out.line("  No mandate in force on that date.", "bad")
        self.out.h2("Every mandate this person has ever held here")
        for m in [m for m in org.mandates if m.person is person] or []:
            self.out.line(f"  {m}")
        offices = [r for r in org.officers if r.person is person]
        if offices:
            self.out.h2("Offices held")
            for r in offices:
                self.out.line(f"  {r}")

    def _audit(self, by, start, end):
        for line in self.ctl.bank.approvals_and_authority_audit(by, _date(start), _date(end)):
            self.out.line(line, "muted" if not line.startswith("  ") else None)

    def _daily(self, on):
        lines = self.ctl.bank.daily_report(_date(on))
        self.out.kv("Events", len(lines))
        for line in lines:
            self.out.line(line)


# ----------------------------------------------------------------------------- scenario log
class ScenarioLogPage(Page):
    title = "Scenario log"
    subtitle = ("Simulation record, not a bank screen: the seeded demonstration that built this data "
                "(16 scenarios on a simulated calendar)")

    def build(self):
        self.content.columnconfigure(1, weight=1)
        self.content.rowconfigure(0, weight=1)
        left = tk.Frame(self.content, bg=self.theme.CARD, highlightbackground=self.theme.LINE, highlightthickness=1)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        self.sections = tk.Listbox(left, width=44, bd=0, highlightthickness=0, activestyle="none",
                                   font=self.theme.f_body, fg=self.theme.INK, bg=self.theme.CARD,
                                   selectbackground=self.theme.SELECT, selectforeground=self.theme.INK)
        self.sections.pack(fill="both", expand=True, padx=6, pady=6)
        self.sections.bind("<<ListboxSelect>>", self._jump)
        right = tk.Frame(self.content, bg=self.theme.CARD, highlightbackground=self.theme.LINE, highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew")
        self.view = DetailView(right, self.theme)
        self.view.pack(fill="both", expand=True)
        self.marks = []

    def refresh(self):
        v = self.view
        v.clear()
        self.sections.delete(0, "end")
        self.marks = []
        lines = self.ctl.scenario_log.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("=" * 10):
                continue
            if line and not line.startswith(" ") and i > 0 and lines[i - 1].startswith("=" * 10):
                mark = f"m{len(self.marks)}"
                v.text.mark_set(mark, "end-1c")
                v.text.mark_gravity(mark, "left")
                self.marks.append(mark)
                self.sections.insert("end", " " + line.replace("SCENARIO", "Scenario")[:60])
                v.write(line + "\n", "h2")
            elif "[BLOCKED]" in line:
                v.write(line + "\n", "bad")
            elif "[OK]" in line:
                v.write(line + "\n", "ok")
            else:
                v.write(line + "\n", "mono")
        v.done()

    def _jump(self, _event=None):
        sel = self.sections.curselection()
        if sel:
            self.view.text.see(self.marks[sel[0]])
            self.view.text.yview(self.marks[sel[0]])


# =============================================================================
# Sign-in screen
# =============================================================================
class SignInScreen(tk.Frame):
    """Choose who you are: a member of staff (the operations console) or a customer or company
    signatory (digital banking). There are no passwords - this is a simulation - but every
    action is then checked against that person's authority by the model."""

    def __init__(self, parent, app):
        t = app.theme
        super().__init__(parent, bg=t.BG)
        self.app, self.theme, self.ctl = app, t, app.ctl
        brand = tk.Frame(self, bg=t.SIDEBAR, width=400)
        brand.pack(side="left", fill="y")
        brand.pack_propagate(False)
        logo = tk.Canvas(brand, width=64, height=64, bg=t.SIDEBAR, highlightthickness=0)
        logo.create_oval(2, 2, 62, 62, fill=t.BRASS, outline=t.BRASS)
        logo.create_text(32, 33, text="IB", fill=t.SIDEBAR, font=(t.family, 20, "bold"))
        logo.pack(anchor="w", padx=44, pady=(80, 18))
        tk.Label(brand, text="Indus Commercial Bank", bg=t.SIDEBAR, fg="#FFFFFF", font=(t.family, 22, "bold"),
                 anchor="w", justify="left", wraplength=320).pack(fill="x", padx=44)
        tk.Label(brand, text="Customers, payments, cards, lending and compliance in one model",
                 bg=t.SIDEBAR, fg=t.SIDEBAR_TEXT, font=t.f_body, anchor="w", justify="left",
                 wraplength=320).pack(fill="x", padx=44, pady=(8, 28))
        self.date_label = tk.Label(brand, text="", bg=t.SIDEBAR, fg=t.BRASS, font=t.f_bold, anchor="w")
        self.date_label.pack(fill="x", padx=44)
        tk.Label(brand, text="The data is a seeded simulation: 16 scenarios from January 2026 to August 2027. "
                             "There are no passwords. Choose who you are; the model then checks that "
                             "person's authority on every action, exactly as it does for the demonstration.",
                 bg=t.SIDEBAR, fg=t.SIDEBAR_MUTED, font=t.f_small, anchor="w", justify="left",
                 wraplength=320).pack(fill="x", padx=44, pady=(10, 0))
        tk.Label(brand, text="Problem 4 - classes and inheritance", bg=t.SIDEBAR, fg=t.SIDEBAR_MUTED,
                 font=t.f_small, anchor="w").pack(side="bottom", fill="x", padx=44, pady=26)

        right = tk.Frame(self, bg=t.BG)
        right.pack(side="left", fill="both", expand=True, padx=36, pady=40)
        tk.Label(right, text="Sign in", bg=t.BG, fg=t.INK, font=t.f_big, anchor="w").pack(fill="x")
        tk.Label(right, text="Staff use the operations console; customers and company signatories use "
                             "digital banking.", bg=t.BG, fg=t.MUTED, font=t.f_body, anchor="w").pack(fill="x",
                                                                                                pady=(2, 18))
        cols = tk.Frame(right, bg=t.BG)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1, uniform="signin")
        cols.columnconfigure(1, weight=1, uniform="signin")
        cols.rowconfigure(0, weight=1)

        staff = Panel(cols, t, "Staff console", "branch, operations, cards, credit, compliance", icon="staff")
        staff.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.staff_table = DataTable(staff.body, t, [("Name", 150), ("Role", 170), ("Branch", 120)], height=12)
        self.staff_table.pack(fill="both", expand=True)
        self.staff_table.tree.bind("<Double-1>", lambda _e: self._staff())
        row = tk.Frame(staff.body, bg=t.CARD)
        row.pack(fill="x", pady=(12, 0))
        ttk.Button(row, text="Sign in to the console", style="Accent.TButton", command=self._staff).pack(side="left")
        ttk.Button(row, text="Open without signing in", style="Link.TButton",
                   command=lambda: self.app.sign_in_staff(None)).pack(side="right")

        people = Panel(cols, t, "Digital banking", "customers and authorised signatories", icon="phone")
        people.grid(row=0, column=1, sticky="nsew")
        self.people_table = DataTable(people.body, t, [("Name", 150), ("Can use", 300)], height=12)
        self.people_table.pack(fill="both", expand=True)
        self.people_table.tree.bind("<Double-1>", lambda _e: self._customer())
        row = tk.Frame(people.body, bg=t.CARD)
        row.pack(fill="x", pady=(12, 0))
        ttk.Button(row, text="Sign in to digital banking", style="Accent.TButton",
                   command=self._customer).pack(side="left")

    def refresh(self):
        self.date_label.config(text=f"Business date  {self.ctl.today:%d %B %Y}")
        rows = []
        for e in self.ctl.staff():
            a = e.role_on(self.ctl.today)
            rows.append((e, [e.person.name, a.role if a else "-", a.branch.name if a else "-"]))
        self.staff_table.set_rows(rows)
        people = []
        for p in self.ctl.digital_people():
            uses = []
            if p.relationship and p.relationship.status.current == "ACTIVE":
                uses.append("own accounts")
            for m in self.ctl.mandates_of(p):
                uses.append(f"{m.organization.name} ({', '.join(sorted(m.capabilities)).lower()})")
            people.append((p, [p.name, "; ".join(uses)]))
        self.people_table.set_rows(people)
        for table in (self.staff_table, self.people_table):
            if table.selected() is None:
                table.select_first()

    def _staff(self):
        e = self.staff_table.selected()
        if e is not None:
            self.app.sign_in_staff(e)

    def _customer(self):
        p = self.people_table.selected()
        if p is not None:
            self.app.sign_in_customer(p)


# =============================================================================
# Digital banking: what a customer or company signatory sees
# =============================================================================
class CustomerView(ttk.Frame):
    """One screen of digital banking. Like Page, but for a signed-in person; every button calls
    one Bank operation with that person as the one acting, so mandates and limits apply."""

    title = "View"

    def __init__(self, parent, shell):
        super().__init__(parent, padding=(28, 20))
        self.shell, self.app, self.theme, self.ctl = shell, shell.app, shell.app.theme, shell.app.ctl
        tk.Label(self, text=self.title, font=self.theme.f_h1, fg=self.theme.INK, bg=self.theme.BG,
                 anchor="w").pack(fill="x", pady=(0, 12))
        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.build()

    @property
    def person(self):
        return self.app.user

    def build(self):
        """Create the widgets."""

    def refresh(self):
        """Re-read the model."""

    def act(self, label, action):
        """Run one Bank operation and show the result."""
        try:
            outcome = self.ctl.run(label, action)
        except (ValueError, ArithmeticError) as e:
            problem = "an amount is not a number" if isinstance(e, ArithmeticError) else str(e)
            outcome = Outcome("blocked", f"{label}: check the input", problem)
        self.shell.show_outcome(outcome)
        return outcome

    def accounts(self, capability=None):
        return [row for row in self.ctl.access_for(self.person) if capability is None or capability in row[2]]

    @staticmethod
    def account_label(row):
        a, capacity, _caps, _m = row
        return f"{a.number}  {a.product.name}  ({capacity})"

    def labelled(self, parent, text, widget, row):
        tk.Label(parent, text=text, bg=self.theme.CARD, fg=self.theme.MUTED, font=self.theme.f_bold,
                 anchor="w").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 16))
        widget.grid(row=row, column=1, sticky="ew", pady=6)
        return widget


class HomeView(CustomerView):
    title = "My accounts"

    def build(self):
        t = self.theme
        self.content.columnconfigure(0, weight=2, uniform="home")
        self.content.columnconfigure(1, weight=3, uniform="home")
        self.content.rowconfigure(0, weight=1)
        self.list_panel = Panel(self.content, t, "Accounts you can use", icon="accounts")
        self.list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.cards_box = ScrollFrame(self.list_panel.body, t)
        self.cards_box.pack(fill="both", expand=True)
        quick = tk.Frame(self.list_panel.body, bg=t.CARD)
        quick.pack(fill="x", pady=(10, 0))
        tk.Label(quick, text="Quick actions", bg=t.CARD, fg=t.MUTED, font=t.f_bold).pack(anchor="w", pady=(0, 6))
        row = tk.Frame(quick, bg=t.CARD)
        row.pack(fill="x")
        for label, view in (("Pay someone", "Pay & transfer"), ("Approvals", "Approvals"), ("My cards", "Cards"),
                            ("Help", "Help")):
            ttk.Button(row, text=label, command=lambda v=view: self.shell.show(v)).pack(side="left", padx=(0, 6))
        self.detail = Panel(self.content, t, "Recent activity", icon="transactions")
        self.detail.grid(row=0, column=1, sticky="nsew")
        self.summary = tk.Label(self.detail.body, text="", bg=t.CARD, fg=t.INK, font=t.f_body, anchor="w",
                                justify="left", wraplength=620)
        self.summary.pack(fill="x", pady=(0, 10))
        self.entries = DataTable(self.detail.body, t, [("Date", 90), ("Description", 280), ("Amount", 120)],
                                 height=14)
        self.entries.pack(fill="both", expand=True)
        row = tk.Frame(self.detail.body, bg=t.CARD)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text="Statement for the last 30 days", command=self._statement).pack(side="left")
        self.selected = None

    def refresh(self):
        t = self.theme
        for w in self.cards_box.inner.winfo_children():
            w.destroy()
        rows = self.accounts()
        if not rows:
            tk.Label(self.cards_box.inner, text="No open accounts you can use today.", bg=t.BG,
                     fg=t.MUTED).pack(anchor="w")
        if self.selected not in [r[0] for r in rows]:
            self.selected = rows[0][0] if rows else None
        for row in rows:
            self._account_card(row)
        self._show_account()

    def _account_card(self, row):
        t = self.theme
        a, capacity, caps, mandate = row
        chosen = a is self.selected
        bg = t.MIST if chosen else t.CARD
        card = tk.Frame(self.cards_box.inner, bg=bg, highlightbackground=t.TEAL_3 if chosen else t.LINE,
                        highlightthickness=1, cursor="hand2")
        card.pack(fill="x", pady=(0, 10), padx=(0, 6))
        top = tk.Frame(card, bg=bg)
        top.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(top, text=a.product.name, bg=bg, fg=t.INK, font=t.f_bold).pack(side="left")
        tk.Label(top, text=a.number, bg=bg, fg=t.MUTED, font=t.f_small).pack(side="right")
        tk.Label(card, text=f"PKR {a.available_balance(self.ctl.today):,.2f}", bg=bg, fg=t.INK,
                 font=t.f_stat, anchor="w").pack(fill="x", padx=14)
        who = "Your own account" if capacity == "Personal" else f"For {capacity}"
        can = "view only" if caps == {"VIEW"} else ", ".join(sorted(c.lower() for c in caps - {"VIEW"}))
        limit = ""
        if mandate is not None and mandate.limit is not None:
            limit = f"; up to PKR {mandate.limit:,.0f}"
        if mandate is not None and mandate.dual_control_above is not None:
            limit += f"; 2nd signatory above PKR {mandate.dual_control_above:,.0f}"
        tk.Label(card, text=f"{who}  -  you can: {can}{limit}", bg=bg, fg=t.MUTED, font=t.f_small, anchor="w",
                 justify="left", wraplength=360).pack(fill="x", padx=14, pady=(0, 10))
        for w in (card, top, *card.winfo_children(), *top.winfo_children()):
            w.bind("<Button-1>", lambda _e, acct=a: self._choose(acct))

    def _choose(self, account):
        self.selected = account
        self.refresh()

    def _show_account(self):
        a = self.selected
        if a is None:
            self.summary.config(text="")
            self.entries.set_rows([])
            return
        today = self.ctl.today
        self.summary.config(text=f"{a.number} {a.product.name} held by {', '.join(h.name for h in a.holders)}.  "
                                 f"Balance PKR {a.ledger_balance():,.2f}; available PKR {a.available_balance(today):,.2f}"
                                 f"{'; on hold PKR ' + format(a.held_amount(today), ',.2f') if a.held_amount(today) else ''}.")
        rows = []
        for e in reversed(a.entries[-60:]):
            rows.append((e.transaction, [e.posted_on, e.transaction.narrative, f"{e.amount:+,.2f}"],
                         "ok" if e.amount > 0 else None))
        self.entries.set_rows(rows)

    def _statement(self):
        if self.selected is None:
            return
        end = self.ctl.today
        text = self.ctl.bank.generate_statement(self.selected, end - timedelta(days=30), end).render()
        messagebox.showinfo("Statement", "\n".join(text) if isinstance(text, list) else str(text))


class PayView(CustomerView):
    title = "Pay and transfer"

    def build(self):
        t = self.theme
        self.content.columnconfigure(0, weight=3, uniform="pay")
        self.content.columnconfigure(1, weight=2, uniform="pay")
        self.content.rowconfigure(0, weight=1)
        tabs = ttk.Notebook(self.content)
        tabs.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        recent = Panel(self.content, t, "Your recent payments", icon="transactions")
        recent.grid(row=0, column=1, sticky="nsew")
        self.recent = DataTable(recent.body, t, [("Status", 150), ("Amount", 110), ("Payment", 200)], height=16)
        self.recent.pack(fill="both", expand=True)
        self.forms = {}
        for key, label in [("payee", "  To a payee  "), ("bill", "  Pay a bill  "), ("own", "  Between my accounts  "),
                           ("new", "  Add a payee  ")]:
            frame = tk.Frame(tabs, bg=t.CARD, padx=24, pady=20)
            tabs.add(frame, text=label)
            self.forms[key] = frame
        f = self.forms["payee"]
        self.p_from = self.labelled(f, "From account", ttk.Combobox(f, state="readonly", width=50), 0)
        self.p_from.bind("<<ComboboxSelected>>", lambda _e: self._payees())
        self.p_to = self.labelled(f, "To payee", ttk.Combobox(f, state="readonly", width=50), 1)
        self.p_amount = self.labelled(f, "Amount (PKR)", ttk.Entry(f, width=24), 2)
        self.p_note = tk.Label(f, text="", bg=t.CARD, fg=t.MUTED, font=t.f_small, anchor="w", justify="left",
                               wraplength=460)
        self.p_note.grid(row=3, column=1, sticky="w")
        ttk.Button(f, text="Send payment", style="Accent.TButton", command=self._send).grid(row=4, column=1,
                                                                                           sticky="w", pady=14)
        f = self.forms["bill"]
        self.b_from = self.labelled(f, "From account", ttk.Combobox(f, state="readonly", width=50), 0)
        self.b_biller = self.labelled(f, "Biller", ttk.Combobox(f, state="readonly", width=50), 1)
        self.b_ref = self.labelled(f, "Consumer reference", ttk.Entry(f, width=30), 2)
        self.b_amount = self.labelled(f, "Amount (PKR)", ttk.Entry(f, width=24), 3)
        ttk.Button(f, text="Pay bill", style="Accent.TButton", command=self._bill).grid(row=4, column=1, sticky="w",
                                                                                        pady=14)
        f = self.forms["own"]
        self.o_from = self.labelled(f, "From account", ttk.Combobox(f, state="readonly", width=50), 0)
        self.o_to = self.labelled(f, "To account", ttk.Combobox(f, state="readonly", width=50), 1)
        self.o_amount = self.labelled(f, "Amount (PKR)", ttk.Entry(f, width=24), 2)
        ttk.Button(f, text="Transfer", style="Accent.TButton", command=self._own).grid(row=3, column=1, sticky="w",
                                                                                       pady=14)
        f = self.forms["new"]
        self.n_owner = self.labelled(f, "Payee for", ttk.Combobox(f, state="readonly", width=50), 0)
        self.n_nick = self.labelled(f, "Nickname", ttk.Entry(f, width=30), 1)
        self.n_bank = self.labelled(f, "Bank", ttk.Entry(f, width=30), 2)
        self.n_acct = self.labelled(f, "Account number", ttk.Entry(f, width=30), 3)
        self.n_title = self.labelled(f, "Account title", ttk.Entry(f, width=30), 4)
        ttk.Button(f, text="Save payee", style="Accent.TButton", command=self._new).grid(row=5, column=1, sticky="w",
                                                                                         pady=14)
        self.maps = {}

    def _fill(self, combo, key, pairs):
        self.maps[key] = dict(pairs)
        combo["values"] = [label for label, _ in pairs]
        if combo.get() not in self.maps[key]:
            combo.set(pairs[0][0] if pairs else "")

    def refresh(self):
        # every account the person can see is offered; the model refuses view-only use
        rows = self.accounts()
        pairs = [(self.account_label(r), r) for r in rows]
        for combo, key in ((self.p_from, "p_from"), (self.b_from, "b_from"), (self.o_from, "o_from"),
                           (self.o_to, "o_to")):
            self._fill(combo, key, pairs)
        owners = []
        for r in rows:
            owner = r[0].holders[0]
            if owner.name not in [o[0] for o in owners]:
                owners.append((owner.name, owner))
        self._fill(self.n_owner, "n_owner", owners)
        billers = [(b.name, b) for b in self.ctl.bank.billers.values() if b.status.current == "ACTIVE"]
        self._fill(self.b_biller, "b_biller", billers)
        self._payees()
        mine = [x for x in self.ctl.bank.transactions.values()
                if isinstance(x, bs.CustomerPayment) and x.initiated_by is self.person]
        self.recent.set_rows([(x, [x.status.current, f"{x.amount:,.2f}", x.narrative],
                               "bad" if x.status.current in ("FAILED", "DECLINED", "REJECTED") else
                               "warn" if x.status.current in ("AWAITING_AUTHORISATION", "HELD_FOR_REVIEW") else None)
                              for x in reversed(mine[-30:])])

    def _payees(self):
        row = self.maps.get("p_from", {}).get(self.p_from.get())
        if row is None:
            self._fill(self.p_to, "p_to", [])
            return
        owner = row[0].holders[0]
        payees = [(f"{b.nickname} - {b.current_version.bank_name} {b.current_version.account_no}", b)
                  for b in self.ctl.bank.beneficiaries.values()
                  if b.owner is owner and b.status.current == "ACTIVE"]
        self._fill(self.p_to, "p_to", payees)
        m = row[3]
        if m is None:
            note = "Your own account: you are the holder."
        else:
            note = (f"You act for {m.organization.name} under mandate {m.mandate_id}: "
                    f"{', '.join(sorted(m.capabilities)).lower()}"
                    f"{', up to PKR ' + format(m.limit, ',.0f') if m.limit is not None else ', no limit'}"
                    f"{'; a 2nd signatory must approve above PKR ' + format(m.dual_control_above, ',.0f') if m.dual_control_above else ''}.")
        self.p_note.config(text=note + "  Payments of PKR 1,000,000 or more are held for a compliance review.")

    def _pick(self, key, combo):
        return self.maps.get(key, {}).get(combo.get())

    def _send(self):
        row, payee = self._pick("p_from", self.p_from), self._pick("p_to", self.p_to)
        if row and payee:
            self.act("Transfer", lambda: self.ctl.bank.initiate_transfer(row[0], payee, bs.money(self.p_amount.get()),
                                                                        self.person, "DIGITAL"))

    def _bill(self):
        row, biller = self._pick("b_from", self.b_from), self._pick("b_biller", self.b_biller)
        if row and biller:
            self.act("Bill payment", lambda: self.ctl.bank.pay_bill(row[0], biller, self.b_ref.get() or "REF-1",
                                                                    bs.money(self.b_amount.get()), self.person, "DIGITAL"))

    def _own(self):
        src, dst = self._pick("o_from", self.o_from), self._pick("o_to", self.o_to)
        if src and dst:
            self.act("Transfer between accounts", lambda: self.ctl.bank.transfer_between_accounts(
                src[0], dst[0], bs.money(self.o_amount.get()), self.person, "DIGITAL"))

    def _new(self):
        owner = self._pick("n_owner", self.n_owner)
        if owner:
            self.act("Add payee", lambda: self.ctl.bank.add_beneficiary(
                owner, self.n_nick.get() or "New payee", self.n_bank.get() or "HBL", self.n_acct.get() or "0000000000",
                self.n_title.get() or self.n_nick.get() or "New payee", self.person))
            self.refresh()


class ApprovalsView(CustomerView):
    title = "Approvals"

    def build(self):
        t = self.theme
        mine = Panel(self.content, t, "Waiting for your approval",
                     "company payments above the 2nd-signatory threshold, started by someone else", icon="check")
        mine.pack(fill="both", expand=True)
        self.waiting = DataTable(mine.body, t, [("Reference", 80), ("Payment", 240), ("Amount", 120),
                                                ("Started by", 140), ("Account", 110)], height=7)
        self.waiting.pack(fill="both", expand=True)
        row = tk.Frame(mine.body, bg=t.CARD)
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text="Approve", style="Accent.TButton", command=self._approve).pack(side="left")
        ttk.Button(row, text="Decline", style="Danger.TButton", command=self._decline).pack(side="left", padx=8)
        started = Panel(self.content, t, "Payments you started", "and where each one is now", icon="transactions")
        started.pack(fill="both", expand=True, pady=(16, 0))
        self.started = DataTable(started.body, t, [("Reference", 80), ("Payment", 240), ("Amount", 120),
                                                   ("Status", 170), ("Date", 90)], height=7)
        self.started.pack(fill="both", expand=True)

    def refresh(self):
        self.waiting.set_rows([(x, [x.txn_id, x.narrative, bs.fmt(x.amount), x.initiated_by.name,
                                    x.source_account.number]) for x in self.ctl.awaiting_my_signature(self.person)])
        mine = [x for x in self.ctl.bank.transactions.values()
                if isinstance(x, bs.CustomerPayment) and x.initiated_by is self.person]
        self.started.set_rows([(x, [x.txn_id, x.narrative, bs.fmt(x.amount), x.status.current, x.initiated_on],
                                "bad" if x.status.current in ("FAILED", "DECLINED", "REJECTED") else
                                "warn" if x.status.current in ("AWAITING_AUTHORISATION", "HELD_FOR_REVIEW") else None)
                               for x in reversed(mine)])

    def _approve(self):
        txn = self.waiting.selected()
        if txn:
            self.act("Approve payment", lambda: self.ctl.bank.authorise_payment(txn, self.person))

    def _decline(self):
        txn = self.waiting.selected()
        if txn:
            self.act("Decline payment", lambda: self.ctl.bank.cancel_pending_payment(txn, self.person,
                                                                                     "declined in digital banking"))


class CardsView(CustomerView):
    title = "My cards"
    CONTROLS = [("ONLINE", "Online purchases blocked"), ("INTERNATIONAL", "International use blocked"),
                ("CASH_WITHDRAWAL", "Cash withdrawals blocked")]

    def build(self):
        t = self.theme
        self.content.columnconfigure(0, weight=2, uniform="cards")
        self.content.columnconfigure(1, weight=3, uniform="cards")
        self.content.rowconfigure(0, weight=1)
        left = Panel(self.content, t, "Card", icon="cards")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.picker = ttk.Combobox(left.body, state="readonly")
        self.picker.pack(fill="x")
        self.picker.bind("<<ComboboxSelected>>", lambda _e: self._show())
        self.face = tk.Canvas(left.body, width=340, height=200, bg=t.CARD, highlightthickness=0)
        self.face.pack(pady=12)
        self.facts = tk.Label(left.body, text="", bg=t.CARD, fg=t.INK, font=t.f_body, anchor="w", justify="left")
        self.facts.pack(fill="x")
        tk.Label(left.body, text="Card controls (switch on to block)", bg=t.CARD, fg=t.MUTED, font=t.f_bold,
                 anchor="w").pack(fill="x", pady=(12, 4))
        self.vars = {}
        for code, text in self.CONTROLS:
            var = tk.BooleanVar()
            ttk.Checkbutton(left.body, text=text, variable=var,
                            command=lambda c=code: self._toggle(c)).pack(anchor="w", pady=2)
            self.vars[code] = var
        row = tk.Frame(left.body, bg=t.CARD)
        row.pack(fill="x", pady=(14, 0))
        ttk.Button(row, text="Report lost", style="Danger.TButton",
                   command=lambda: self._report("LOST")).pack(side="left")
        ttk.Button(row, text="Report stolen", style="Danger.TButton",
                   command=lambda: self._report("STOLEN")).pack(side="left", padx=8)
        right = Panel(self.content, t, "Card payments", "on this card and every card it replaced", icon="transactions")
        right.grid(row=0, column=1, sticky="nsew")
        self.payments = DataTable(right.body, t, [("Date", 90), ("Merchant", 190), ("Amount", 110),
                                                  ("Status", 120), ("Card", 80)], height=12)
        self.payments.pack(fill="both", expand=True)
        form = tk.Frame(right.body, bg=t.CARD)
        form.pack(fill="x", pady=(10, 0))
        tk.Label(form, text="Dispute the selected payment:", bg=t.CARD, fg=t.MUTED, font=t.f_bold).pack(side="left")
        self.d_reason = ttk.Combobox(form, state="readonly", width=20,
                                     values=[nice(r) for r in sorted(bs.Chargeback.REASON_CODES)])
        self.d_reason.set(nice("NOT_RECEIVED"))
        self.d_reason.pack(side="left", padx=8)
        ttk.Button(form, text="Open dispute", command=self._dispute).pack(side="left")
        self.cards = {}

    def refresh(self):
        cards = self.ctl.cards_of(self.person)
        self.cards = {f"{c.masked_number}  ({nice(c.status.current)})": c for c in cards}
        self.picker["values"] = list(self.cards)
        if self.picker.get() not in self.cards:
            active = [k for k, c in self.cards.items() if c.status.current == "ACTIVE"]
            self.picker.set(active[0] if active else (list(self.cards)[0] if self.cards else ""))
        self._show()

    def card(self):
        return self.cards.get(self.picker.get())

    def _show(self):
        t, c = self.theme, self.card()
        self.face.delete("all")
        if c is None:
            self.face.create_text(170, 100, text="You hold no cards", fill=t.MUTED, font=t.f_body)
            self.facts.config(text="")
            self.payments.set_rows([])
            return
        live = c.status.current == "ACTIVE"
        colour = t.TEAL if live else "#8A9896"
        self.face.create_rectangle(4, 4, 336, 196, fill=colour, outline=colour)
        self.face.create_polygon(210, 4, 336, 4, 336, 196, 270, 196, fill=_tint(colour, 0.12), outline="")
        self.face.create_text(22, 30, text="Indus Commercial Bank", anchor="w", fill="#FFFFFF", font=t.f_bold)
        self.face.create_rectangle(22, 62, 62, 92, fill=t.BRASS, outline=t.BRASS)
        self.face.create_text(22, 124, text=c.masked_number, anchor="w", fill="#FFFFFF", font=(t.mono, 15, "bold"))
        self.face.create_text(22, 164, text=c.cardholder.name.upper(), anchor="w", fill="#FFFFFF", font=t.f_bold)
        self.face.create_text(318, 164, text=f"{c.expires_on:%m/%y}", anchor="e", fill="#FFFFFF", font=t.f_bold)
        if not live:
            self.face.create_text(318, 30, text=nice(c.status.current).upper(), anchor="e", fill="#FFFFFF",
                                  font=t.f_bold)
        today = self.ctl.today
        self.facts.config(text=f"Daily limit PKR {c.daily_limit_on(today):,.0f}; spent today PKR "
                               f"{c.spent_on(today):,.0f}\nLinked to {c.account.number} "
                               f"({', '.join(h.name for h in c.account.holders)})")
        live_controls = {k.control_type for k in c.controls if k.period.contains(today)}
        for code, var in self.vars.items():
            var.set(code in live_controls)
        hits = self.ctl.bank.search_transactions(card=c)
        self.payments.set_rows([(x, [x.initiated_on, x.merchant.name, bs.fmt(x.amount), x.status.current,
                                     x.card.card_id], "bad" if x.status.current == "DECLINED" else None)
                                for x in reversed(hits)])

    def _toggle(self, code):
        c = self.card()
        if c is None:
            return
        live = [k for k in c.controls if k.control_type == code and k.period.contains(self.ctl.today)]
        if self.vars[code].get() and not live:
            self.act("Switch on card control", lambda: self.ctl.bank.add_card_control(c, code, self.person))
        elif not self.vars[code].get() and live:
            self.act("Switch off card control", lambda: self.ctl.bank.remove_card_control(live[0], self.person))

    def _report(self, kind):
        c = self.card()
        if c and messagebox.askyesno("Report card", f"Block card {c.masked_number} as {kind.lower()}?"):
            self.act(f"Report card {kind.lower()}", lambda: self.ctl.bank.report_card(c, kind, self.person))

    def _dispute(self):
        txn = self.payments.selected()
        if txn is None:
            messagebox.showinfo("Select a payment", "Select a card payment first.")
            return
        reason = next(r for r in bs.Chargeback.REASON_CODES if nice(r) == self.d_reason.get())
        self.act("Open dispute", lambda: self.ctl.bank.open_dispute(txn, txn.net_amount, self.person, "DIGITAL",
                                                                    self.person, reason))


class HelpView(CustomerView):
    title = "Help and requests"

    def build(self):
        t = self.theme
        top = tk.Frame(self.content, bg=t.BG)
        top.pack(fill="x")
        top.columnconfigure(0, weight=1, uniform="help")
        top.columnconfigure(1, weight=1, uniform="help")
        comp = Panel(top, t, "Make a complaint", icon="alert")
        comp.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        comp.body.columnconfigure(1, weight=1)
        self.c_party = self.labelled(comp.body, "About", ttk.Combobox(comp.body, state="readonly"), 0)
        self.c_cat = self.labelled(comp.body, "Topic", ttk.Combobox(comp.body, state="readonly",
                                   values=["Payment delay", "Service", "Fees", "Card", "Other"]), 1)
        self.c_cat.set("Service")
        self.c_text = self.labelled(comp.body, "What happened", ttk.Entry(comp.body), 2)
        ttk.Button(comp.body, text="Send complaint", style="Accent.TButton", command=self._complain).grid(
            row=3, column=1, sticky="w", pady=10)
        req = Panel(top, t, "Request a service", icon="log")
        req.grid(row=0, column=1, sticky="nsew")
        req.body.columnconfigure(1, weight=1)
        self.r_party = self.labelled(req.body, "For", ttk.Combobox(req.body, state="readonly"), 0)
        self.r_type = self.labelled(req.body, "Request", ttk.Combobox(req.body, state="readonly", values=[
            "Statement copy", "Address change", "Cheque book", "Limit review"]), 1)
        self.r_type.set("Statement copy")
        ttk.Button(req.body, text="Send request", style="Accent.TButton", command=self._request).grid(
            row=2, column=1, sticky="w", pady=10)
        cases = Panel(self.content, t, "Your cases", "complaints, requests and disputes you raised", icon="cases")
        cases.pack(fill="both", expand=True, pady=(16, 0))
        self.cases = DataTable(cases.body, t, [("Case", 80), ("Kind", 110), ("Summary", 320), ("Status", 90),
                                               ("Opened", 90)], height=8)
        self.cases.pack(fill="both", expand=True)
        self.parties = {}

    def refresh(self):
        parties = {}
        for a, capacity, _caps, _m in self.accounts():
            owner = a.holders[0]
            parties[owner.name] = owner
        if self.person.relationship:
            parties[self.person.name] = self.person
        self.parties = parties
        for combo in (self.c_party, self.r_party):
            combo["values"] = list(parties)
            if combo.get() not in parties and parties:
                combo.set(list(parties)[0])
        mine = [c for c in self.ctl.bank.cases.values()
                if getattr(c, "contact_person", None) is self.person]
        self.cases.set_rows([(c, [c.case_id, c.kind, c.summary, "Open" if c.is_open else "Closed", c.opened_on])
                             for c in reversed(mine)])

    def _complain(self):
        party = self.parties.get(self.c_party.get())
        if party:
            code = self.c_cat.get().upper().replace(" ", "_")
            self.act("Complaint", lambda: self.ctl.bank.log_complaint(party, self.c_text.get() or "customer complaint",
                                                                      "DIGITAL", self.person, code, self.person))

    def _request(self):
        party = self.parties.get(self.r_party.get())
        if party:
            code = self.r_type.get().upper().replace(" ", "_")
            self.act("Service request", lambda: self.ctl.bank.raise_service_request(party, code, self.person, "DIGITAL",
                                                                                    self.person))


class DigitalBanking(tk.Frame):
    """The digital-banking shell: a header with the person's name, tabs, and the views."""

    VIEWS = [("Home", HomeView, "accounts"), ("Pay & transfer", PayView, "transactions"),
             ("Approvals", ApprovalsView, "check"), ("Cards", CardsView, "cards"), ("Help", HelpView, "log")]

    def __init__(self, parent, app):
        t = app.theme
        super().__init__(parent, bg=t.BG)
        self.app, self.theme = app, t
        head = tk.Frame(self, bg=t.SIDEBAR)
        head.pack(fill="x")
        inner = tk.Frame(head, bg=t.SIDEBAR)
        inner.pack(fill="x", padx=24, pady=10)
        logo = tk.Canvas(inner, width=34, height=34, bg=t.SIDEBAR, highlightthickness=0)
        logo.create_oval(1, 1, 33, 33, fill=t.BRASS, outline=t.BRASS)
        logo.create_text(17, 17, text="IB", fill=t.SIDEBAR, font=(t.family, 11, "bold"))
        logo.pack(side="left")
        tk.Label(inner, text="Indus Digital", bg=t.SIDEBAR, fg="#FFFFFF", font=(t.family, 14, "bold")).pack(
            side="left", padx=(10, 30))
        self.tabs = {}
        for name, _cls, icon in self.VIEWS:
            tab = tk.Label(inner, text=name, bg=t.SIDEBAR, fg=t.SIDEBAR_TEXT, font=t.f_bold, padx=14, pady=6,
                           cursor="hand2")
            tab.pack(side="left")
            tab.bind("<Button-1>", lambda _e, n=name: self.show(n))
            self.tabs[name] = tab
        ttk.Button(inner, text="Sign out", command=app.sign_out).pack(side="right")
        self.who = tk.Label(inner, text="", bg=t.SIDEBAR, fg="#FFFFFF", font=t.f_bold)
        self.who.pack(side="right", padx=12)
        self.avatar_box = tk.Frame(inner, bg=t.SIDEBAR)
        self.avatar_box.pack(side="right")
        self.date = tk.Label(inner, text="", bg=t.SIDEBAR, fg=t.SIDEBAR_MUTED, font=t.f_small)
        self.date.pack(side="right", padx=16)
        self.banner = Banner(self, t)
        self.banner.pack(fill="x")
        self.stack = tk.Frame(self, bg=t.BG)
        self.stack.pack(fill="both", expand=True)
        self.views = {}
        for name, cls, _icon in self.VIEWS:
            view = cls(self.stack, self)
            view.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.views[name] = view
        self.current = None

    def start(self):
        t, person = self.theme, self.app.user
        for w in self.avatar_box.winfo_children():
            w.destroy()
        Avatar(self.avatar_box, person.name, t.SIDEBAR, t.BRASS, 30).pack()
        self.who.config(text=person.name)
        self.date.config(text=f"{self.app.ctl.today:%d %b %Y}")
        self.banner.clear()
        self.show("Home")

    def show(self, name):
        t = self.theme
        self.current = name
        waiting = len(self.app.ctl.awaiting_my_signature(self.app.user))
        for n, tab in self.tabs.items():
            text = f"{n} ({waiting})" if n == "Approvals" and waiting else n
            tab.config(text=text, bg=t.SIDEBAR_ACTIVE if n == name else t.SIDEBAR,
                       fg="#FFFFFF" if n == name else t.SIDEBAR_TEXT)
        view = self.views[name]
        view.refresh()
        view.tkraise()

    def show_outcome(self, outcome):
        self.banner.show(outcome)
        self.show(self.current)


# =============================================================================
# The application window
# =============================================================================
class BankingApp(tk.Tk):
    """The window. It opens on the sign-in screen and then shows either the staff console
    (sidebar, top bar, pages) or digital banking (for a customer or company signatory)."""

    # The bank's own screens, then two teaching/simulation aids kept visibly apart from them
    # (the brief describes the model as being "for teaching and simulation purposes").
    SECTIONS = [
        ("Bank", [("Overview", DashboardPage), ("Operations", OperationsPage), ("Customers", CustomersPage),
                  ("Accounts", AccountsPage), ("Transactions", TransactionsPage), ("Cards", CardsPage),
                  ("Counterparties", CounterpartiesPage), ("Cases", CasesPage), ("Staff", StaffPage),
                  ("Products & branches", ProductsPage), ("Books & audit", BooksPage), ("Reports", ReportsPage)]),
        ("Teaching & simulation", [("Class model", ClassModelPage), ("Scenario log", ScenarioLogPage)]),
    ]
    PAGES = [page for _section, pages in SECTIONS for page in pages]
    ICONS = {"Overview": "overview", "Operations": "operations", "Customers": "customers", "Accounts": "accounts",
             "Transactions": "transactions", "Cards": "cards", "Counterparties": "counterparties", "Cases": "cases",
             "Staff": "staff", "Products & branches": "products", "Books & audit": "books", "Reports": "reports",
             "Class model": "classes", "Scenario log": "log"}

    def __init__(self, sign_in=True):
        super().__init__()
        self.title("Indus Commercial Bank")
        self.geometry("1440x880")
        self.minsize(1180, 720)
        self.theme = Theme(self)
        self.configure(bg=self.theme.BG)
        self.ctl = BankController()
        self.user = None                              # an Employee (console), a Person (digital) or None

        self.console = tk.Frame(self, bg=self.theme.BG)
        self._build_sidebar(self.console)
        main = tk.Frame(self.console, bg=self.theme.BG)
        main.pack(side="left", fill="both", expand=True)
        self._build_topbar(main)
        self.banner = Banner(main, self.theme)
        self.banner.pack(fill="x")
        self.stack = tk.Frame(main, bg=self.theme.BG)
        self.stack.pack(fill="both", expand=True)
        self.pages = {}
        for name, cls in self.PAGES:
            page = cls(self.stack, self)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.pages[name] = page
        self.current = None
        self.digital = DigitalBanking(self, self)
        self.signin = SignInScreen(self, self)
        for frame in (self.console, self.digital, self.signin):
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        if sign_in:
            self.sign_out()
        else:
            self.sign_in_staff(None)

    # ---------------------------------------------------------------- who is using the program
    def sign_in_staff(self, employee):
        """Open the staff console as this employee (None = nobody: every form asks who acts)."""
        self.user = employee
        self.console.tkraise()
        self._update_user_chip()
        self.banner.clear()
        self.show("Overview")

    def sign_in_customer(self, person):
        """Open digital banking as this person (a customer or a company signatory)."""
        self.user = person
        self.digital.tkraise()
        self.digital.start()

    def sign_out(self):
        self.user = None
        self.signin.refresh()
        self.signin.tkraise()

    def _relocate_user(self):
        """After "Reset data" the bank is rebuilt, so find the same person in the new one."""
        if isinstance(self.user, bs.Employee):
            name = self.user.person.name
            self.user = next((e for e in self.ctl.bank.employees.values() if e.person.name == name), None)
        elif isinstance(self.user, bs.Person):
            self.user = self.ctl.find_person(self.user.name)

    # ---------------------------------------------------------------- chrome
    def _build_sidebar(self, parent):
        t = self.theme
        side = tk.Frame(parent, bg=t.SIDEBAR, width=240)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand = tk.Frame(side, bg=t.SIDEBAR)
        brand.pack(fill="x", padx=18, pady=(20, 16))
        logo = tk.Canvas(brand, width=36, height=36, bg=t.SIDEBAR, highlightthickness=0)
        logo.create_oval(1, 1, 35, 35, fill=t.BRASS, outline=t.BRASS)
        logo.create_text(18, 18, text="IB", fill=t.SIDEBAR, font=(t.family, 11, "bold"))
        logo.pack(side="left")
        names = tk.Frame(brand, bg=t.SIDEBAR)
        names.pack(side="left", padx=10)
        tk.Label(names, text="Indus Commercial", bg=t.SIDEBAR, fg="#FFFFFF", font=(t.family, 10, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(names, text="Operations console", bg=t.SIDEBAR, fg=t.SIDEBAR_MUTED, font=t.f_small,
                 anchor="w").pack(fill="x")
        self.nav = {}
        for i, (section, pages) in enumerate(self.SECTIONS):
            tk.Label(side, text=section.upper(), bg=t.SIDEBAR, fg=t.SIDEBAR_MUTED, font=t.f_small,
                     anchor="w").pack(fill="x", padx=22, pady=(14 if i else 4, 4))
            for name, _cls in pages:
                self._nav_item(side, name)
        tk.Label(side, text="Every rule lives in banking_system.py; this window only calls it.", bg=t.SIDEBAR,
                 fg=t.SIDEBAR_MUTED, font=t.f_small, justify="left", anchor="w", wraplength=190).pack(
            side="bottom", fill="x", padx=22, pady=16)

    def _nav_item(self, side, name):
        t = self.theme
        item = tk.Frame(side, bg=t.SIDEBAR, cursor="hand2")
        item.pack(fill="x", padx=10, pady=1)
        bar = tk.Frame(item, bg=t.SIDEBAR, width=3)
        bar.pack(side="left", fill="y")
        icon = tk.Canvas(item, width=18, height=18, bg=t.SIDEBAR, highlightthickness=0)
        icon.pack(side="left", padx=(12, 10), pady=7)
        label = tk.Label(item, text=name, bg=t.SIDEBAR, fg=t.SIDEBAR_TEXT, font=t.f_body, anchor="w")
        label.pack(side="left", fill="x", expand=True)
        item.parts = (item, bar, icon, label)
        self._paint_nav(name, item, False)
        for w in item.parts:
            w.bind("<Button-1>", lambda _e, n=name: self.show(n))
            w.bind("<Enter>", lambda _e, n=name: self._hover(n, True))
            w.bind("<Leave>", lambda _e, n=name: self._hover(n, False))
        self.nav[name] = item

    def _paint_nav(self, name, item, active, hover=False):
        t = self.theme
        bg = t.SIDEBAR_ACTIVE if active else t.SIDEBAR_HOVER if hover else t.SIDEBAR
        frame, bar, icon, label = item.parts
        for w in (frame, icon, label):
            w.config(bg=bg)
        bar.config(bg=t.BRASS if active else bg)
        label.config(fg="#FFFFFF" if active else t.SIDEBAR_TEXT, font=t.f_bold if active else t.f_body)
        icon.delete("all")
        Icons.draw(icon, self.ICONS.get(name, ""), 1, 1, 16, "#FFFFFF" if active else t.SIDEBAR_TEXT)

    def _hover(self, name, on):
        if name != self.current:
            self._paint_nav(name, self.nav[name], False, on)

    def _active_nav(self):
        return self.nav.get(self.current)

    def _build_topbar(self, parent):
        t = self.theme
        bar = tk.Frame(parent, bg=t.CARD, highlightbackground=t.LINE, highlightthickness=1)
        bar.pack(fill="x")
        inner = tk.Frame(bar, bg=t.CARD)
        inner.pack(fill="x", padx=24, pady=10)
        self.date_chip = tk.Label(inner, text="", bg=t.MIST, fg=t.TEAL, font=t.f_bold, padx=12, pady=5)
        self.date_chip.pack(side="left")
        self.books_chip = tk.Label(inner, text="", font=t.f_bold, padx=12, pady=5)
        self.books_chip.pack(side="left", padx=10)
        ttk.Button(inner, text="Next day", command=lambda: self.advance(1)).pack(side="left", padx=(12, 0))
        ttk.Button(inner, text="Next month", command=lambda: self.advance(30)).pack(side="left", padx=6)
        ttk.Button(inner, text="Reset", style="Link.TButton", command=self.reset).pack(side="left", padx=2)
        ttk.Button(inner, text="Switch user", command=self.sign_out).pack(side="right")
        self.user_chip = tk.Frame(inner, bg=t.CARD)
        self.user_chip.pack(side="right", padx=14)

    def _update_user_chip(self):
        t = self.theme
        for w in self.user_chip.winfo_children():
            w.destroy()
        user = self.user
        if isinstance(user, bs.Employee):
            a = user.role_on(self.ctl.today)
            Avatar(self.user_chip, user.person.name, t.CARD, t.TEAL, 32).pack(side="left")
            text = tk.Frame(self.user_chip, bg=t.CARD)
            text.pack(side="left", padx=8)
            tk.Label(text, text=user.person.name, bg=t.CARD, fg=t.INK, font=t.f_bold, anchor="w").pack(fill="x")
            tk.Label(text, text=f"{nice(a.role)}, {a.branch.code}" if a else "no current role", bg=t.CARD,
                     fg=t.MUTED, font=t.f_small, anchor="w").pack(fill="x")
        else:
            tk.Label(self.user_chip, text="Not signed in: forms ask who acts", bg=t.CARD, fg=t.MUTED,
                     font=t.f_small).pack(side="left")

    def _update_topbar(self):
        t, ctl = self.theme, self.ctl
        self.date_chip.config(text=f"Business date  {ctl.today:%d %b %Y}")
        ok = ctl.books_balance()
        self.books_chip.config(text="Books balance" if ok else "Books do NOT balance",
                               bg=t.OK_BG if ok else t.BAD_BG, fg=t.OK if ok else t.BAD)

    # ---------------------------------------------------------------- navigation and actions
    def show(self, name):
        if self.current and self.current in self.nav:
            self._paint_nav(self.current, self.nav[self.current], False)
        self.current = name
        self._paint_nav(name, self.nav[name], True)
        self.console.tkraise()
        page = self.pages[name]
        page.refresh()
        page.tkraise()
        self._update_topbar()

    def refresh_current(self):
        self.pages[self.current].refresh()
        self._update_topbar()

    def advance(self, days):
        self.ctl.advance(days)
        self.show_outcome(Outcome("ok", f"Business date moved to {self.ctl.today:%d %b %Y}",
                                  "The end-of-day batch ran for every day in between."))

    def reset(self):
        if messagebox.askyesno("Reset data", "Rebuild the seeded bank? Changes made in the console are lost."):
            self.ctl.reset()
            self._relocate_user()
            self._update_user_chip()
            self.show_outcome(Outcome("ok", "Seeded data rebuilt", "The 16 scenarios were run again."))

    def show_outcome(self, outcome):
        """Show the result of the last operation in a coloured banner and refresh the page."""
        self.banner.show(outcome)
        self.refresh_current()


def main():
    try:
        app = BankingApp(sign_in="--no-sign-in" not in sys.argv)
    except tk.TclError as e:
        print("Could not open a window:", e, file=sys.stderr)
        print("The GUI needs a graphical desktop session. "
              "Without one, run: python banking_system.py", file=sys.stderr)
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
