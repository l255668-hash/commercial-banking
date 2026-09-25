# Submission checklist

Work through this list before you hand the project in.

## 1. Fill in your details

- [ ] Name, roll number and course on the report cover (`docs/Design_Report.md`, then rebuild `.docx` / `.pdf`, or edit the Word file directly).
- [ ] The same fields on slide 1 of `docs/Viva_Presentation.pptx`.

## 2. Check the course rules (only your instructor can answer these)

- [ ] Required file format (PDF, Word, or both) and any page limit. Both are provided.
- [ ] Whether a zip of the whole folder is expected, or separate files.
- [ ] **Whether AI assistance is allowed, and whether it must be declared.** If it must, say so honestly in the report or in your submission note. If it is not allowed, talk to your instructor before submitting.
- [ ] Whether a demo video or live demo is required (`python banking_system.py` is the live demo).

## 3. Make the research your own

- [ ] Look at each source listed in report section 1 (at least the parts named) so you can discuss it.
- [ ] Remove any source you have not looked at, or replace it with one you have.

## 4. Verify on your own computer

```
python banking_system.py --test       # expect: Ran 70 tests ... OK
python banking_system.py              # expect: TOTAL 0.00 at the end
python banking_system.py --classes    # expect: 75 domain classes (69 business + 6 supporting), 7 error classes, 97 Bank operations
python banking_gui.py                 # the desktop console opens (Linux: sudo apt install python3-tk)
python tools/gui_smoke_test.py        # optional: expect "GUI smoke test passed" (needs a display)
```

- [ ] Open `docs/Design_Report.docx` and `docs/Viva_Presentation.pptx` in Word / PowerPoint and check the layout (they could not be previewed where they were generated).

## 5. Prepare for the viva

- [ ] Read `docs/Viva_Preparation.md` and answer each question aloud in your own words.
- [ ] Be able to explain, line by line: `Arrangement`, `DepositAccount`, `SavingsAccount.check_debit`, `Bank.initiate_transfer`, `Bank.reverse_transaction`, `Bank.repay_financing`.
- [ ] Rehearse the slides once (speaker notes are in the deck).
- [ ] Be able to explain the abstract classes (`python banking_system.py --classes` marks them) and walk through State machine 1: which statuses `BankTransaction`, `CustomerPayment` and `TransferPayment` each added.
- [ ] Be able to walk through Flowchart 3 (transfer payment) and Flowchart 2 (onboarding) decision by decision, and say which method each diamond comes from. Know the six symbols.
- [ ] Rehearse a live demo in the GUI: Operations > Guided rule checks, run 1 to 14 in order; then show Customers (Ayesha's timeline and the time machine on 2026-04-11), Cards (the replacement chain) and Books & audit (zero trial balance). Use "Reset data" to start again. If asked to show a new customer, use Operations > Customers: register a person, add a document, verify, onboard, open an account. Class model (in the Teaching & simulation section) shows the inheritance tree live.
- [ ] If your course requires the single code file only, submit `banking_system.py`; `banking_gui.py` is an optional extra that needs it.

## What is in the folder

| File | Purpose |
|---|---|
| `banking_system.py` | The whole implementation: model, demo, tests, diagram generators |
| `banking_gui.py` | Optional desktop GUI (Tkinter); every button calls one Bank operation |
| `README.md` | How to run, file map, requirement map |
| `docs/Design_Report.pdf` / `.docx` / `.md` | Written submission, sections 1 to 10 of the brief (flowcharts in 4.1, GUI in 11) |
| `docs/*.png`, `docs/*.svg` | Class overview, four UML hierarchy diagrams, three association diagrams, six flowcharts, four state machine diagrams |
| `docs/demo_output.txt` | Captured output of the 16 scenarios |
| `docs/Code_Review.md` | Defects found in the supplied code and how each was fixed |
| `docs/Viva_Preparation.md` | Likely questions and model answers |
| `docs/Viva_Presentation.pptx` | 15-slide deck for the viva, with speaker notes |
| `docs/Submission_Checklist.md` | This list |
| `docs/screenshots/` | GUI screenshots used in report section 11 |
| `tools/` | Optional build scripts that regenerate the flowcharts, PNGs, PDF, Word file, deck and screenshots, plus the GUI smoke test (see `tools/README.md`) |
| `.github/workflows/tests.yml` | Runs the tests, demo, GUI smoke test and a diagrams-match-the-code check on GitHub for every push |
