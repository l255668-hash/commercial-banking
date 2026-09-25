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
    if "(blank" in name:
        return ""                                      # the optional fields are left empty
    if kind == "amount":
        return "1000"
    if "YYYY-MM-DD" in name:
        return "1990-01-01"
    if "Months" in name:
        return "12"
    if "rate" in name.lower():
        return "0.18"
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


def main():
    app = g.BankingApp()
    try:
        guided_checks(app)
        app.ctl.reset()
        every_form(app)
        app.ctl.reset()
        onboarding_story(app)
        print("== every screen refreshed")
        for name, _ in app.PAGES:
            app.show(name)
            app.update()
        print(f"  {len(app.PAGES)} screens, {len(app.pages['Diagrams'].files)} diagram files")
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
