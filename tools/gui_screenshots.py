"""Capture the GUI screenshots used in the report (Linux / X11 only).

    xvfb-run -a -s "-screen 0 1440x880x24" python tools/gui_screenshots.py
    xvfb-run -a -s "-screen 0 1440x880x24" python tools/gui_screenshots.py --all /tmp/shots

The default run rewrites the nine report figures in docs/screenshots/
(gui_01 to gui_09). ``--all DIR`` instead saves every screen to DIR, for
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


def show_page(name):
    return lambda app: app.show(name)


def show_guided_checks(app):
    app.show("Operations")
    app.pages["Operations"].content.winfo_children()[0].select(1)


def show_class_model(app):
    app.show("Class model")
    select(app.pages["Class model"], lambda c: c is g.bs.CustomerPayment)


def show_counterparty(app):
    app.show("Counterparties")
    select(app.pages["Counterparties"], lambda x: getattr(x, "name", "") == "Imtiaz Auto Parts")


def show_onboarding_form(app):
    app.show("Operations")
    ops = app.pages["Operations"]
    ops.content.winfo_children()[0].select(0)          # the forms tab, not the guided checks
    iid = next(i for i, s in ops.specs.items() if s.label == "Register a person")
    ops.op_tree.item(ops.op_tree.parent(iid), open=True)
    ops.op_tree.selection_set(iid)
    ops.op_tree.see(iid)
    ops._pick_operation()


def main(argv):
    app = g.BankingApp()
    app.geometry("1440x880+0+0")
    if argv[:1] == ["--all"]:
        out = Path(argv[1] if len(argv) > 1 else ".")
        out.mkdir(parents=True, exist_ok=True)
        steps = [(f"{i:02d}_{name.replace(' ', '_').replace('&', 'and')}.png",
                  lambda a, n=name: a.show(n)) for i, (name, _) in enumerate(app.PAGES)]
    else:
        out = SHOTS
        steps = [("gui_01_overview.png", show_page("Overview")),
                 ("gui_02_guided_checks.png", show_guided_checks),
                 ("gui_03_customer_timeline.png", show_page("Customers")),
                 ("gui_04_card_chain.png", show_page("Cards")),
                 ("gui_05_books_audit.png", show_page("Books & audit")),
                 ("gui_06_class_model.png", show_class_model),
                 ("gui_07_onboarding_form.png", show_onboarding_form),
                 ("gui_08_reports.png", show_page("Reports")),
                 ("gui_09_counterparties.png", show_counterparty)]
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
