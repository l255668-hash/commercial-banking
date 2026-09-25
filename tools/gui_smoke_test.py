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
        print("== every screen refreshed")
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
