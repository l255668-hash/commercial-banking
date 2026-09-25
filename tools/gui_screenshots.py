"""Capture the GUI screenshots used in the report (Linux / X11 only).

    xvfb-run -a -s "-screen 0 1440x880x24" python tools/gui_screenshots.py
    xvfb-run -a -s "-screen 0 1440x880x24" python tools/gui_screenshots.py --all /tmp/shots

The default run writes the two newest report figures to docs/screenshots/:
the Diagrams screen showing a flowchart, and the "Register a person" form in
the Operations screen.  ``--all DIR`` instead saves every screen to DIR, for
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


def show_flowchart(app):
    app.show("Diagrams")
    page = app.pages["Diagrams"]
    names = [p.name for p in page.files]
    index = names.index("flowchart_3_transfer.png") if "flowchart_3_transfer.png" in names else 0
    page.list.selection_clear(0, "end")
    page.list.selection_set(index)
    page.list.see(index)
    page._show()


def show_onboarding_form(app):
    app.show("Operations")
    ops = app.pages["Operations"]
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
        steps = [("gui_07_diagrams.png", show_flowchart),
                 ("gui_08_onboarding_form.png", show_onboarding_form)]
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
