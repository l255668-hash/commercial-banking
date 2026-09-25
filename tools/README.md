# Build tools

These scripts regenerate the files in `docs/`. **None of them is needed to run or mark the project**: `banking_system.py` and `banking_gui.py` use the Python standard library only. Run every command from the repository root.

| Script | What it does | Needs |
|---|---|---|
| `make_flowcharts.py` | Draws the six flowcharts as `docs/flowchart_*.svg` using the standard symbols | Python only |
| `make_state_diagrams.py` | Draws the four UML state machine diagrams (`docs/state_*.svg`) from each class's `LIFECYCLE` | Python only |
| `render_diagrams.py` | Turns `docs/*.svg` (flowcharts, class and UML diagrams) into same-size PNGs | Chromium, Pillow |
| `build_report_pdf.py` | Builds `docs/Design_Report.pdf` from `docs/Design_Report.md` | Chromium, `markdown` |
| `md2docx.js` | Builds `docs/Design_Report.docx` from `docs/Design_Report.md` | Node.js, `docx` |
| `make_deck.js` | Builds `docs/Viva_Presentation.pptx` (15 slides, speaker notes) | Node.js, `pptxgenjs` |
| `gui_smoke_test.py` | Drives every guided check, every operation form and an onboarding story in the GUI; exits 1 on a crash or unbalanced books | Tkinter, a display (or `xvfb-run`) |
| `gui_screenshots.py` | Captures the GUI screenshots used in the report | Linux/X11: `xwd`, netpbm |

## Rebuilding everything

```
python banking_system.py --diagram docs     # class and UML diagrams (SVG)
python tools/make_flowcharts.py             # flowcharts (SVG)
python tools/make_state_diagrams.py         # state machine diagrams (SVG)
python tools/render_diagrams.py             # every SVG -> PNG
python tools/build_report_pdf.py            # report PDF

cd tools && npm install && cd ..            # once: docx and pptxgenjs
node tools/md2docx.js docs/Design_Report.md docs/Design_Report.docx
node tools/make_deck.js

xvfb-run -a python tools/gui_smoke_test.py
xvfb-run -a -s "-screen 0 1440x880x24" python tools/gui_screenshots.py
```

If Chromium is not found automatically, set `CHROME=/path/to/chrome`. On Debian/Ubuntu the GUI tools need `sudo apt install python3-tk xvfb x11-apps netpbm`.

## Flowchart symbols

`make_flowcharts.py` follows ISO 5807: a stadium for start and end (red when a rule ends the flow), a rectangle for a process, a diamond for a yes/no decision, a parallelogram for input or output, a rectangle with double sides for a named `Bank` operation, and a cylinder for stored records. Connectors are drawn at right angles, and every diamond has exactly one Yes exit and one No exit. To change a chart, edit its function in `make_flowcharts.py` (`c.node(key, shape, column, row, text)` and `c.edge(from, to, label)`), then rerun it and `render_diagrams.py`.

## Continuous integration

`.github/workflows/tests.yml` runs on every push: the unit tests, the demonstration (it must end with a zero trial balance) and a lint check on Python 3.9, 3.11 and 3.13; the GUI smoke test under a virtual display; and a check that regenerating every SVG from the code gives exactly the committed files, so the diagrams can never drift from the code.
