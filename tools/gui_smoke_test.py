"""Drive the desktop GUI without a person at the keyboard.

    python tools/gui_smoke_test.py            # needs a display
    xvfb-run -a python tools/gui_smoke_test.py   # on a server without one

Three passes, each through ``BankController.run`` exactly as a button would:

1. every guided rule check on the Operations screen;
2. every operation form, filled with the first choice in each list;
3. a full onboarding story typed into the Customers forms: register a
   person, refuse KYC on an expired document, verify a valid one, onboard,
   open an account (and be refused the wrong product), deposit, grant and
   revoke a mandate, add a beneficiary.

Refusals and blocked outcomes are expected; the script fails (exit code 1)
only if something crashes, an outcome is not the expected kind, or the
books stop balancing.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import banking_gui as g  # noqa: E402

problems = []


def show(outcome):
    print(f"  {outcome.kind:8} {outcome.title[:100]}")
    return outcome


def guided_checks(app):
    print("== guided rule checks")
    ops = app.pages["Operations"]
    for title, _expect, fn in ops._checks():
        show(app.ctl.run(title, fn))


def sample_text(name, kind):
    """A plausible value for a free-text field, judged by its label."""
    lowered = name.lower()
    if "(blank" in name or "optional" in lowered:
        return ""                                      # the optional fields are left empty
    if kind == "amount" or "amount given back" in lowered:
        return "1000"
    if "YYYY-MM-DD" in name:                           # future dates for dues, past for births
        return "2028-01-15" if any(w in lowered for w in ("due", "effective", "to (")) else "1990-01-01"
    if "months" in lowered:
        return "12"
    if "rate" in lowered:
        return "0.18"
    if "percentage" in lowered:
        return "30"
    if "day of month" in lowered:
        return "5"
    if "key=value" in lowered:
        return "monthly_fee=100"
    return "Smoke test " + name.split(" (")[0].lower()


def every_form(app):
    print("== every operation form, first choice in each list")
    ops = app.pages["Operations"]
    for spec in ops.specs.values():
        ops._render_form(spec)
        values = []
        for (widget, mapping), (name, kind) in zip(ops.inputs, spec.fields):
            if mapping is None:                        # free text: fill a sensible value
                if not widget.get().strip():
                    widget.insert(0, sample_text(name, kind))
                values.append(widget.get().strip())
            elif widget.get().strip() in mapping:
                values.append(mapping[widget.get().strip()])
            else:
                values = None
                break
        if values is None:
            print(f"  skipped  {spec.label}: a list has no choices right now")
            continue
        try:
            show(app.ctl.run(spec.label, lambda: spec.call(values)))
        except (ValueError, ArithmeticError) as exc:   # the Submit button shows "Check the input"
            print(f"  input    {spec.label}: {exc}")
        except Exception as exc:
            problems.append(f"{spec.label}: {type(exc).__name__}: {exc}")
            print(f"  CRASH    {spec.label}: {exc}")


def onboarding_story(app):
    print("== onboarding story through the Customers forms")
    ops, ctl = app.pages["Operations"], app.ctl
    bank = ctl.bank
    spec = {s.label: s for s in ops.specs.values()}

    def run(label, values, expect):
        outcome = show(ctl.run(label, lambda: spec[label].call(values)))
        if outcome.kind != expect:
            problems.append(f"{label}: expected {expect}, got {outcome.kind} ({outcome.detail[:80]})")
        return outcome

    officer = ctl.find_employee("Maryam Tahir")
    teller = ctl.find_employee("Farah Siddiqui")
    run("Register a person", ["Kashif Mehmood", "1991-03-04", officer], "ok")
    kashif = ctl.find_person("Kashif Mehmood")
    run("Onboard as a customer", [kashif, "RETAIL", "", officer], "blocked")      # no document yet
    run("Add an identity document",
        [kashif, "CNIC", "35202-9", "2020-01-01", "2026-01-01", officer], "ok")   # already expired
    run("Verify a party against a document", [kashif.documents[0], officer], "refused")
    run("Onboard as a customer", [kashif, "RETAIL", "", officer], "blocked")
    run("Add an identity document",
        [kashif, "CNIC", "35202-9", "2026-01-02", "2036-01-01", officer], "ok")
    run("Verify a party against a document", [kashif.documents[1], officer], "ok")
    run("Onboard as a customer", [kashif, "RETAIL", "", officer], "ok")
    product = next(p for p in bank.products.values() if p.code == "CUR-PERS")
    run("Open an account", ["CurrentAccount", product, kashif, officer], "ok")
    run("Open an account", ["SavingsAccount", product, kashif, officer], "blocked")  # wrong product
    account = next(a for a in bank.arrangements.values() if kashif in a.holders)
    run("Deposit cash", [account, "25000", teller], "ok")
    company = ctl.find_person("Ravi Textiles (Pvt) Ltd")
    run("Grant a mandate", [company, kashif, "PAYMENTS", "100000", "", officer], "ok")
    mandate = next(m for m in company.mandates if m.person is kashif)
    run("Revoke a mandate", [mandate, "left the company", officer], "ok")
    run("Add a beneficiary", [kashif, "Landlord", "UBL", "1234567890", "Mr Landlord", kashif], "ok")


def lending_and_dispute_story(app):
    print("== financing lifecycle and a card dispute through the forms")
    ops, ctl = app.pages["Operations"], app.ctl
    bank = ctl.bank
    spec = {s.label: s for s in ops.specs.values()}

    def run(label, values, expect):
        outcome = show(ctl.run(label, lambda: spec[label].call(values)))
        if outcome.kind != expect:
            problems.append(f"{label}: expected {expect}, got {outcome.kind} ({outcome.detail[:80]})")
        return outcome

    ravi = ctl.find_person("Ravi Textiles (Pvt) Ltd")
    ayesha = ctl.find_person("Ayesha Khan")
    zainab = ctl.find_employee("Zainab Qureshi")
    officer = ctl.find_employee("Maryam Tahir")
    cards_ops = ctl.find_employee("Hina Aslam")
    account = next(a for a in bank.arrangements.values()
                   if ravi in a.holders and isinstance(a, g.bs.CurrentAccount) and a.status.current == "ACTIVE")
    run("Apply for financing", [ravi, "2000000", "12", ayesha], "ok")
    app_ = [a for a in bank.applications.values() if a.status.current == "SUBMITTED"][-1]
    run("Decide an application", [app_, "APPROVE", "0.18", "board resolution", zainab], "ok")
    run("Disburse financing", [app_, account, "2027-10-01", zainab], "blocked")   # condition still open
    run("Satisfy a condition", [app_.conditions[0], "original on file", officer], "ok")
    run("Disburse financing", [app_, account, "2027-10-01", zainab], "ok")
    fin = app_.agreement
    run("Repay financing", [fin, "100000", account], "ok")
    run("Restructure financing", [fin, "18", "0.17", "2027-11-01", "cash-flow delay", zainab], "ok")
    run("Settle financing early", [fin, account, zainab], "ok")
    card = next(c for c in bank.cards.values() if c.status.current == "ACTIVE" and c.account is account)
    run("Card purchase", [card, bank.merchants["Liberty Books"], "5000", "POS"], "ok")
    buy = [t for t in bank.transactions.values() if isinstance(t, g.bs.CardPayment)][-1]
    run("Merchant refund", [buy, "1000", "one book returned"], "ok")
    run("Open a dispute", [buy, "4000", "NOT_RECEIVED", card.cardholder, officer], "ok")
    dispute = buy.disputes[-1]
    run("Resolve a dispute", [dispute, "UPHELD", "4000", cards_ops], "ok")
    if not isinstance(dispute.refund, g.bs.Chargeback):
        problems.append("an upheld card dispute did not produce a Chargeback")


def reports_and_counterparties(app):
    ctl = app.ctl
    app.show("Reports")
    page = app.pages["Reports"]
    ravi, bilal = ctl.find_person("Ravi Textiles (Pvt) Ltd"), ctl.find_person("Bilal Ahmed")
    checks = [
        ("authority while director", lambda: page._authority(ravi, bilal, "2026-04-11"), "MND-"),
        ("authority after revocation", lambda: page._authority(ravi, bilal, "2027-08-01"), "No mandate"),
        ("audit by the auditor", lambda: page._audit(ctl.find_employee("Nida Farooq"), "2026-01-01", "2026-12-31"),
         "Approvals by staff"),
        ("daily report", lambda: page._daily("2026-03-02"), "Events"),
    ]
    for name, call, expect in checks:
        page.out.clear()
        call()
        text = page.out.text.get("1.0", "end")
        print(f"  {'ok' if expect in text else 'MISSING':8} report: {name}")
        if expect not in text:
            problems.append(f"report '{name}' did not show '{expect}'")
    page.out.clear()
    page._run("audit", [], lambda: page._audit(ctl.find_employee("Farah Siddiqui"), "2026-01-01", "2026-12-31"))
    if "Refused by AuthorityError" not in page.out.text.get("1.0", "end"):
        problems.append("a teller was allowed to run the audit report")
    else:
        print("  ok       report: a teller is refused the audit")
    app.show("Counterparties")
    cp = app.pages["Counterparties"]
    kinds = {row[1][0] for row in cp.rows()}
    for obj, _cells, _tag in cp.rows():
        cp._show_selected(obj)
    print(f"  ok       counterparties: {len(cp.rows())} rows of kinds {sorted(kinds)}")
    if kinds != {"Merchant", "Biller", "Payee"}:
        problems.append(f"counterparties screen shows {kinds}")


def sign_in_and_roles(app):
    """A signed-in member of staff is recorded automatically and sees their own forms."""
    print("== sign-in, role-filtered forms and automatic 'performed by'")
    ctl = app.ctl
    teller = ctl.find_employee("Farah Siddiqui")
    app.sign_in_staff(teller)
    app.show("Operations")
    ops = app.pages["Operations"]
    labels = {s.label for s in ops.specs.values()}
    if "Deposit cash" not in labels or "Approve" in labels or "Disburse financing" in labels:
        problems.append(f"a teller sees the wrong forms: {sorted(labels)[:6]}...")
    print(f"  ok       a teller sees {len(labels)} of {len(ops.all_specs)} forms")
    spec = next(s for s in ops.all_specs if s.label == "Deposit cash")
    ops._render_form(spec)
    fixed = [w for w, m in ops.inputs if isinstance(w, g._Fixed)]
    if len(fixed) != 1 or fixed[0].get() != g.nice(g.label_of(teller)):
        problems.append("the teller was not filled in as the member of staff")
    account = ctl.deposit_accounts()[0]
    outcome = show(ctl.run("Deposit cash", lambda: spec.call([account, "1000", teller])))
    if outcome.kind != "ok":
        problems.append("a signed-in teller could not take a deposit")
    ops.show_all.set(True)
    ops._populate()
    if len(ops.specs) != len(ops.all_specs):
        problems.append("'show everything' did not show every form")
    ops.show_all.set(False)
    ops.search.insert(0, "card")
    ops._populate()
    print(f"  ok       search 'card' finds {len(ops.specs)} teller forms")
    ops.search.delete(0, "end")
    app.sign_out()


def digital_banking_story(app):
    """Customers and company signatories act through digital banking; mandates still apply."""
    print("== digital banking: the same rules for customers and signatories")
    ctl = app.ctl
    bank = ctl.bank

    def check(label, outcome, expect):
        show(outcome)
        if outcome.kind != expect:
            problems.append(f"digital {label}: expected {expect}, got {outcome.kind} ({outcome.detail[:80]})")

    noor, hamza, ayesha = (ctl.find_person(n) for n in ("Noor Fatima", "Hamza Sheikh", "Ayesha Khan"))
    app.sign_in_customer(noor)
    home = app.digital.views["Home"]
    if not home.accounts() or home.accounts()[0][2] != {"VIEW"}:
        problems.append("Noor should see the company account as view-only")
    pay = app.digital.views["Pay & transfer"]
    app.digital.show("Pay & transfer")
    pay.p_amount.insert(0, "5000")
    before = len(bank.transactions)
    pay._send()
    last = list(bank.transactions.values())[-1]
    check("view-only transfer", g.Outcome("refused" if last.status.current == "FAILED" else "ok", last.txn_id),
          "refused")
    if len(bank.transactions) != before + 1:
        problems.append("the refused transfer was not kept on record")

    app.sign_in_customer(hamza)
    app.digital.show("Pay & transfer")
    pay.p_amount.delete(0, "end")
    pay.p_amount.insert(0, "1200000")                   # above Hamza's 2nd-signatory threshold
    pay._send()
    pending = list(bank.transactions.values())[-1]
    check("transfer needing a 2nd signatory",
          g.Outcome("ok" if pending.status.current == "AWAITING_AUTHORISATION" else "blocked", pending.txn_id), "ok")
    cards = app.digital.views["Cards"]
    app.digital.show("Cards")
    cards.vars["ONLINE"].set(True)
    cards._toggle("ONLINE")
    card = cards.card()
    if not any(c.control_type == "ONLINE" and c.period.contains(ctl.today) for c in card.controls):
        problems.append("Hamza could not switch on his online block")
    cards.vars["ONLINE"].set(False)
    cards._toggle("ONLINE")
    print(f"  ok       Hamza switched his online block on and off ({len(card.controls)} control records kept)")

    app.sign_in_customer(ayesha)
    approvals = app.digital.views["Approvals"]
    app.digital.show("Approvals")
    waiting = ctl.awaiting_my_signature(ayesha)
    if pending not in waiting:
        problems.append("Ayesha does not see Hamza's payment for approval")
    approvals.waiting.set_rows([(pending, [pending.txn_id])])
    approvals.waiting.select_first()
    approvals._approve()
    check("Ayesha approves as 2nd signatory",
          g.Outcome("ok" if pending.status.current in ("HELD_FOR_REVIEW", "POSTED") else "blocked", pending.txn_id),
          "ok")
    help_view = app.digital.views["Help"]
    app.digital.show("Help")
    cases_before = len(bank.cases)
    help_view.c_text.insert(0, "statement arrived late")
    help_view._complain()
    if len(bank.cases) != cases_before + 1:
        problems.append("a digital complaint was not recorded as a case")
    for name in ("Home", "Pay & transfer", "Approvals", "Cards", "Help"):
        app.digital.show(name)
    print(f"  ok       all {len(app.digital.views)} digital banking views refreshed for {ayesha.name}")
    app.digital.show("Home")
    statements = len(bank.statements)
    app.digital.views["Home"]._statement()
    windows, stack = [], list(app.winfo_children())
    while stack:
        w = stack.pop()
        if isinstance(w, g.tk.Toplevel):
            windows.append(w)
        stack.extend(w.winfo_children())
    if len(bank.statements) != statements + 1 or not windows:
        problems.append("the statement was not produced and shown")
    else:
        print(f"  ok       statement {bank.statements[-1].statement_id} produced and shown in its own window")
    for w in windows:
        w.destroy()
    app.sign_out()


def assistant_story(app):
    """The assistant explains a refusal and prepares a form; the form is run by the user, not by it."""
    print("== assistant: answers from the records, prepares forms, never acts by itself")
    page = app.pages["Assistant"]
    app.show("Assistant")
    page.assistant = g.ba.OfflineAssistant(lambda: app.ctl.bank)     # the test must not depend on a key
    refused = next(t for t in app.ctl.bank.transactions.values() if t.status.current == "FAILED")
    reply = page.assistant.ask(f"Why was {refused.txn_id} refused?")
    if refused.failure_reason not in reply.text:
        problems.append("the assistant did not explain a refused payment")
    before = len(app.ctl.bank.transactions)
    page.send("Deposit 5,000 into CUR-001")
    action = page.assistant.conversation[-1].reply.action
    if len(app.ctl.bank.transactions) != before or action is None:
        problems.append("the assistant should prepare the deposit form without posting anything")
        return
    page.open_form(action)
    ops = app.pages["Operations"]
    ops._execute(ops.current_spec)
    last = list(app.ctl.bank.transactions.values())[-1]
    if not (last.txn_id.startswith("CSH") and last.amount == 5000 and last.status.current == "POSTED"):
        problems.append(f"the prepared deposit form did not post correctly ({last})")
    else:
        print(f"  ok       explained {refused.txn_id}; prepared and ran a deposit form: {last.txn_id} POSTED")


def main():
    app = g.BankingApp()
    try:
        guided_checks(app)
        app.ctl.reset()
        every_form(app)
        app.ctl.reset()
        onboarding_story(app)
        lending_and_dispute_story(app)
        print("== reports and counterparties screens")
        reports_and_counterparties(app)
        sign_in_and_roles(app)
        app.ctl.reset()
        digital_banking_story(app)
        app.sign_in_staff(None)
        assistant_story(app)
        print("== every screen refreshed")
        app.show("Overview")
        overview = app.pages["Overview"]
        if overview.queue.tree.get_children():
            overview.queue.select_first()
            waiting = overview.queue.selected()
            overview._open_payment()
            if app.pages["Transactions"].table.selected() is not waiting:
                problems.append("double-clicking a waiting payment did not open it")
            else:
                print(f"  ok       the overview opens {waiting.txn_id} on the Transactions screen")
        for name, _ in app.PAGES:
            app.show(name)
            app.update()
        print(f"  {len(app.PAGES)} screens in {len(app.SECTIONS)} sidebar sections")
        balanced = app.ctl.books_balance()
        print(f"  trial balance is zero: {balanced}")
        if not balanced:
            problems.append("the books do not balance")
    finally:
        app.destroy()
    if problems:
        print("\nFAILED:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print("\nGUI smoke test passed")


if __name__ == "__main__":
    main()
