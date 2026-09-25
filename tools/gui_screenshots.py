"""Capture the GUI screenshots used in the report (Linux / X11 only).

    xvfb-run -a -s "-screen 0 1440x880x24" python tools/gui_screenshots.py
    xvfb-run -a -s "-screen 0 1440x880x24" python tools/gui_screenshots.py --all /tmp/shots

The default run rewrites the thirteen report figures in docs/screenshots/
(gui_01 to gui_13). ``--all DIR`` instead saves every screen to DIR, for
checking the layout after a change.

The whole X screen is grabbed with ``xwd`` and converted with netpbm
(Debian/Ubuntu: sudo apt install x11-apps netpbm).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import banking_gui as g  # noqa: E402

SHOTS = ROOT / "docs" / "screenshots"


def grab(target):
    subprocess.run(f"xwd -root -silent | xwdtopnm 2>/dev/null | pnmtopng > '{target}'",
                   shell=True, check=True)
    print("written", target)


def select(page, predicate):
    """Select the first row of a list screen whose object matches, and show it."""
    for iid, obj in page.table.objects.items():
        if predicate(obj):
            page.table.tree.selection_set(iid)
            page.table.tree.see(iid)
            page._show_selected(obj)
            return


def staff(name, page=None):
    """Sign in as a member of staff and open a page."""
    def setup(app):
        if not (isinstance(app.user, g.bs.Employee) and app.user.person.name == name):
            app.sign_in_staff(app.ctl.find_employee(name))
        if page:
            app.show(page)
    return setup


def customer(name, view="Home"):
    def setup(app):
        app.sign_in_customer(app.ctl.find_person(name))
        app.digital.show(view)
    return setup


def sign_in_screen(app):
    app.sign_out()


def guided_checks(app):
    staff("Kamran Javed", "Operations")(app)
    app.pages["Operations"].content.winfo_children()[0].select(1)


def operation_form(app):
    staff("Maryam Tahir", "Operations")(app)
    ops = app.pages["Operations"]
    ops.content.winfo_children()[0].select(0)          # the forms tab, not the guided checks
    iid = next(i for i, s in ops.specs.items() if s.label == "Onboard as a customer")
    ops.op_tree.item(ops.op_tree.parent(iid), open=True)
    ops.op_tree.selection_set(iid)
    ops.op_tree.see(iid)
    ops._pick_operation()


def class_model(app):
    staff("Kamran Javed", "Class model")(app)
    select(app.pages["Class model"], lambda c: c is g.bs.CustomerPayment)


def counterparty(app):
    staff("Kamran Javed", "Counterparties")(app)
    select(app.pages["Counterparties"], lambda x: getattr(x, "name", "") == "Imtiaz Auto Parts")


def main(argv):
    app = g.BankingApp()
    app.geometry("1440x880+0+0")
    if argv[:1] == ["--all"]:
        out = Path(argv[1] if len(argv) > 1 else ".")
        out.mkdir(parents=True, exist_ok=True)
        steps = [(f"{i:02d}_{name.replace(' ', '_').replace('&', 'and')}.png", staff("Maryam Tahir", name))
                 for i, (name, _) in enumerate(app.PAGES)]
    else:
        out = SHOTS
        steps = [("gui_01_sign_in.png", sign_in_screen),
                 ("gui_02_overview.png", staff("Kamran Javed", "Overview")),
                 ("gui_03_operation_form.png", operation_form),
                 ("gui_04_guided_checks.png", guided_checks),
                 ("gui_05_customer_timeline.png", staff("Kamran Javed", "Customers")),
                 ("gui_06_card_chain.png", staff("Kamran Javed", "Cards")),
                 ("gui_07_books_audit.png", staff("Kamran Javed", "Books & audit")),
                 ("gui_08_reports.png", staff("Kamran Javed", "Reports")),
                 ("gui_09_counterparties.png", counterparty),
                 ("gui_10_class_model.png", class_model),
                 ("gui_11_digital_home.png", customer("Hamza Sheikh")),
                 ("gui_12_digital_cards.png", customer("Hamza Sheikh", "Cards")),
                 ("gui_13_digital_approvals.png", customer("Ayesha Khan", "Approvals"))]
    queue = list(steps)

    def step():
        if not queue:
            app.destroy()
            return
        name, setup = queue.pop(0)
        setup(app)
        app.update_idletasks()

        def capture():
            app.update()
            grab(out / name)
            app.after(100, step)
        app.after(900, capture)                    # let the page lay itself out first

    app.after(800, step)
    app.mainloop()


if __name__ == "__main__":
    main(sys.argv[1:])
