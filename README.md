# Problem 4: Commercial Banking, Lending, Payments and Compliance

**Prepared by:** Khizar Rizwan and Bilal Nadeem

[![tests](https://github.com/l255668-hash/commercial-banking/actions/workflows/tests.yml/badge.svg?branch=claude/reading-assistance-5l43go)](https://github.com/l255668-hash/commercial-banking/actions/workflows/tests.yml)

An object-oriented model of a commercial bank (the fictional Indus Commercial Bank, Lahore), written for the OOP project brief, Problem 4. The assessed concepts are **classes and inheritance**. The model keeps a complete history: nothing is deleted, and any past state can be reconstructed.

The model, demo and tests are in **one Python file**, `banking_system.py`, using the standard library only (Python 3.9 or later). There is nothing to install.

An optional desktop GUI, `banking_gui.py`, is a separate file that uses the model without changing it. It is pure Python (Tkinter, part of the standard library). Its sidebar keeps the bank's own screens apart from two teaching and simulation aids (Class model, Scenario log).

## Quick start

```
python banking_system.py              # run the seeded demonstration (16 scenarios)
python banking_system.py --test       # run the 73 automated tests
python banking_system.py --classes    # print the inheritance tree and the class/operation counts
python banking_system.py --diagram docs   # regenerate every diagram (SVG) from the code
python banking_gui.py                 # open the desktop app (sign in as staff or as a customer)
```

On Windows and macOS, Tkinter comes with Python. On Linux you may need `sudo apt install python3-tk`.

## Files

```
banking_system.py            the whole implementation: model, demo, tests, diagram generators
banking_gui.py               desktop GUI (Tkinter): every button calls one Bank operation
docs/
  Design_Report.pdf/.docx/.md  the written submission (sections 1 to 10 of the brief)
  class_diagram.png/.svg       overview of all hierarchies and standalone classes
  uml_*.png/.svg               UML: four hierarchy diagrams (attributes, methods, overrides)
                               and three association diagrams
  flowchart_*.png/.svg         six flowcharts of the main workflows, standard symbols
  state_*.png/.svg             four UML state machine diagrams, drawn from each class's LIFECYCLE
  demo_output.txt              captured output of the demonstration
  Code_Review.md               analysis of the supplied code, defects found and how each was fixed
  Viva_Preparation.md          likely questions and model answers
  Viva_Presentation.pptx       16-slide viva deck with speaker notes
  Submission_Checklist.md      what to check and fill in before handing in
  screenshots/gui_*.png        screenshots of the desktop GUI
.github/workflows/tests.yml    CI: tests on Python 3.9 / 3.11 / 3.13, GUI smoke test, diagrams up to date
tools/                         scripts that rebuild the flowcharts, state diagrams, PNGs, PDF, Word report,
                               slide deck and GUI screenshots, plus a GUI smoke test
                               (not needed to run the project; see tools/README.md)
```

## Abstract classes, polymorphism and lifecycles

The brief assesses classes and inheritance only; it says abstraction and polymorphism are not assessed. They are used here only to make the inheritance decisions enforceable, not as extra features.

- **Abstract base classes.** `Party`, `Organization`, `Arrangement`, `DepositAccount`, `BankTransaction`, `CustomerPayment`, `LoanTransaction` and `Case` use Python's `abc` and cannot be instantiated. Each concrete subclass implements the abstract methods whose answer differs by class: `structural_gaps` / `connected_persons` (KYC), `position` (money held or owed), `overdraft_limit`, `counterparty` and `handler_roles`. `python banking_system.py --classes` marks them "(abstract)"; the UML diagrams show them in italics.
- **Polymorphism instead of type checks.** `Bank.transaction_story` and `Bank.assign_case` used `isinstance` chains; now each class answers for itself (`story_lines()` template method, `handler_roles()`).
- **Declared state machines.** Every record with a status declares its `LIFECYCLE` once (initial status, allowed moves with the operation that causes each, final statuses). `StatusHistory` refuses anything else, and subclasses extend their parent's lifecycle: `BankTransaction` -> `CustomerPayment` (dual control) -> `TransferPayment` (compliance hold). The four state diagrams in `docs/state_*.png` are drawn from these declarations.

![State machine 1 - TransferPayment](docs/state_1_payment.png)

## Flowcharts

Six flowcharts in `docs/` show the behaviour the class diagrams cannot: the order in which the code checks each rule and where a refusal ends the flow. They use the standard symbols: stadium = start / end (red when a rule ends the flow), rectangle = process, diamond = yes / no decision, parallelogram = input / output, double-sided rectangle = a named `Bank` operation, cylinder = stored records.

| Flowchart | Traced from |
|---|---|
| 1. Program overview | `banking_system.py` command line, `run_demo()` |
| 2. Customer onboarding and account opening | `verify_party`, `become_customer`, `open_deposit_account` |
| 3. Transfer payment | `initiate_transfer`, `authorise_payment`, `release_transaction` |
| 4. Card purchase | `card_purchase` |
| 5. Financing lifecycle | `submit_financing_application` to `settle_financing` |
| 6. Desktop console interaction | `BankController.run` in `banking_gui.py` |

![Flowchart 3 - Transfer payment](docs/flowchart_3_transfer.png)

## Inside `banking_system.py`

| Part | Contents |
|---|---|
| 1-2 | Helpers, business-rule errors, `Period`, `StatusHistory`, audit events |
| 3 | Parties and KYC: `Party -> Person`, `Party -> Organization -> Company / Charity`, documents, checks, officers, owners, mandates |
| 4 | Branches, employees, role assignments, `Approval` (freezes the role held at the time) |
| 5 | Products with versioned terms; `Arrangement -> DepositAccount -> CurrentAccount / SavingsAccount`; ledger, holds, restrictions |
| 6 | Financing: `FinancingAgreement`, versioned repayment schedules, installments, applications and conditions |
| 7 | Beneficiaries (versioned) and standing orders |
| 8 | Transactions, double-entry: `BankTransaction -> CustomerPayment -> TransferPayment / CardPayment`, `LoanTransaction -> ...`, reversals |
| 9 | Issued cards with a replacement chain |
| 10 | Cases: `Case -> CustomerCase -> Dispute / Complaint / ServiceRequest`, `Case -> RiskCase -> FraudAlert / ComplianceInvestigation` |
| 11 | Statements and notices |
| 12 | `Bank`: 98 operations (80 state-changing commands), each checking its rules and writing an audit event |
| 13 | Seeded demonstration on a simulated calendar (Jan 2026 to Aug 2027) |
| 14 | 73 automated tests (including abstraction, lifecycle, refund and chargeback tests) |
| 15-16 | Class and UML diagram generators, command line |

## The desktop GUI (`banking_gui.py`)

The app opens on a sign-in screen with two ways in, as in a real bank:

- **Staff console:** sign in as a member of staff. You are recorded automatically on every operation, the forms list what your role may do (with a search box), and the top bar shows who you are.
- **Digital banking:** sign in as a customer or a company signatory. You see your own accounts and the companies you may act for, and can pay, transfer, pay bills, approve a colleague's payment as second signatory, switch card controls, report a card and dispute a payment. The model's rules still apply: a view-only signatory is refused and the attempt is kept on record.

![Sign in](docs/screenshots/gui_01_sign_in.png)

![Staff console overview](docs/screenshots/gui_02_overview.png)

![Digital banking](docs/screenshots/gui_11_digital_home.png)

Staff console screens:

| Screen | What it shows |
|---|---|
| Overview | Customers, deposits, lending, open cases, payments waiting for a second signatory or held for review (authorise or release them here), recent audit events, and whether the books balance |
| Operations | 80 operation forms in ten groups (customers, accounts, payments, cash, cards and merchants, cases and compliance, lending, organisation, products, records), enough to run every workflow in the brief by hand, and 14 guided rule checks, each running one real operation and showing the model's answer |
| Customers | Every party with its class path, KYC, capacities, a timeline of dated roles (offices, ownerships, mandates, branch and RM history, restrictions), and a time machine for any past date |
| Accounts | Each arrangement with its pinned terms, branch history, balances, ledger with running balance, term-deposit maturity, and every financing schedule version |
| Transactions | Filter by class (including parent classes such as `CustomerPayment`), status or text; each record's story, beneficiary as sent vs today, and its double-entry legs |
| Cards | Replacement chains, controls with their periods, and every payment across the chain |
| Counterparties | Merchants, billers and payees (external parties, not customers) with every payment made to or from them, including merchant refunds and chargebacks |
| Cases | Customer, risk and collections cases, with evidence snapshots compared against the corrected record |
| Staff / Products & branches | Role history and every approval with the role held then; products with terms versions and holders; branches and their history |
| Books & audit | Trial balance on any date (always zero) and a searchable audit log |
| Reports | Who held which mandate on a past date; the auditors' approvals-and-authority report (refused for a teller, itself logged); everything that happened on a given day |
| Class model *(teaching section)* | The inheritance tree read from the code (abstract classes marked), what each level adds, each class's lifecycle, and live object counts |
| Scenario log *(teaching section)* | The 16 seeded scenarios with refusals highlighted |

Digital banking screens (for the signed-in customer or signatory):

| Screen | What it does |
|---|---|
| Home | Every account the person may use (their own, and each company's under a live mandate) with the balance and what the mandate allows; recent activity; a statement |
| Pay & transfer | Pay a payee, pay a bill, move money between accounts, add a payee; shows the mandate's limit and 2nd-signatory threshold; lists the person's recent payments and their status |
| Approvals | Company payments waiting for this person as 2nd signatory (approve or decline), and payments they started |
| Cards | The card, its controls switched on and off by the cardholder, reporting it lost or stolen, and every payment across the replacement chain with a dispute button |
| Help | Complaints and service requests, and the cases the person has raised |

The GUI never edits an object directly: every button calls one `Bank` operation, so all rules, refusals and audit events are the model's own. The top bar advances the business date (running the end-of-day batch) or resets the seeded data. The GUI is itself built from classes and inheritance (`Page -> MasterDetailPage -> CustomersPage` and so on).

## Where each requirement of the brief is met

| Required item | Where |
|---|---|
| Domain research summary | Report section 1 |
| Assumptions | Report section 2 (A1 to A36) |
| Requirements interpretation | Report section 3 |
| Class diagram | Report section 4: overview, 4 UML hierarchy and 3 association diagrams; 4.1: 6 flowcharts; 4.2: 4 state machine diagrams |
| Implementation (at least 30 classes and 30 operations) | `banking_system.py`: 77 classes (71 business + 6 supporting), 98 operations; report section 5 |
| Multi-level inheritance explained | Report section 6; 6.1 abstract classes and polymorphism; 6.2 inherited state machines |
| At least three rejected inheritances | Report section 7 (fourteen given) and 7.1 (comparison with a plausible alternative design) |
| Seeded demonstration | `run_demo()`, `docs/demo_output.txt`, report section 8 |
| At least five complex scenarios | 16 scenarios, report section 9 |
| Limitations and scaling | Report section 10 |

## The brief's critical cases

| Critical case | Scenario | Test |
|---|---|---|
| Customer is personal and represents several organisations | 1, 7 | `test_same_person_is_never_duplicated_across_roles` |
| Transaction posted, reversed, re-posted differently, disputed | 4 | `test_repost_links_original_and_correction`, `test_partial_reversal_and_over_reversal`, `test_dispute_cannot_be_resolved_twice` |
| Product no longer sold but valid for old customers | 10 | `test_withdrawn_product_blocks_new_but_not_existing`, `test_terms_pinned_until_migration` |
| Person loses signing authority; history still shows it | 7 | `test_revoked_mandate_still_provable_for_past_dates` |
| Customer temporarily restricted then cleared | 5 | `test_restriction_blocks_then_lifts_with_history`, `test_risk_case_cannot_close_with_live_restriction` |
| Card replaced multiple times; old transactions searchable | 3, 10, 15 | `test_stolen_replaced_card_cannot_be_reactivated`, `test_card_search_covers_the_replacement_chain` |
| Financing restructured after installments paid | 6 | `test_restructure_supersedes_schedule_and_keeps_paid` |
| Beneficiary changes after old transfers | 8 | `test_beneficiary_snapshot_survives_amendment` |
| Branch closes; customers and staff transferred | 11 | `test_branch_closure_moves_but_keeps_history`, `test_branch_closure_moves_vault_cash` |
| Compliance case references data later corrected | 9 | `test_correction_keeps_past_value`, `test_evidence_snapshot_is_not_rewritten_by_correction` |

## Beyond the critical cases

Report section 3.2 maps every participant, research area and scope item in the brief to the model. Scenarios 14 to 16 cover what the critical cases do not: sole traders and high-value customers (enhanced due diligence), fixed-term deposits, card controls, bill payments, collections staff and promises to pay, the auditor's approvals and authority report, and record retention (archive versus delete). Report section 3.1 answers the brief's eight open questions one by one.

## Notes

The bank, people and companies are fictional. All amounts are Pakistani rupees. Data is held in memory and rebuilt on each run.
