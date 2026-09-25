# Problem 4: Commercial Banking, Lending, Payments and Compliance

An object-oriented model of a commercial bank (the fictional Indus Commercial Bank, Lahore), written for the OOP project brief, Problem 4. The assessed concepts are **classes and inheritance**. The model keeps a complete history: nothing is deleted, and any past state can be reconstructed.

Everything is in **one Python file**, `banking_system.py`, using the standard library only (Python 3.9 or later). There is nothing to install.

## Quick start

```
python banking_system.py              # run the seeded demonstration (13 scenarios)
python banking_system.py --test       # run the 49 automated tests
python banking_system.py --classes    # print the inheritance tree and the class/operation counts
python banking_system.py --diagram docs   # regenerate every diagram (SVG) from the code
```

## Files

```
banking_system.py            the whole implementation: model, demo, tests, diagram generators
docs/
  Design_Report.pdf/.docx/.md  the written submission (sections 1 to 10 of the brief)
  class_diagram.png/.svg       overview of all hierarchies and standalone classes
  uml_*.png/.svg               UML: four hierarchy diagrams (attributes, methods, overrides)
                               and three association diagrams
  demo_output.txt              captured output of the demonstration
  Code_Review.md               analysis of the supplied code, defects found and how each was fixed
  Viva_Preparation.md          likely questions and model answers
  Viva_Presentation.pptx       11-slide viva deck with speaker notes
  Submission_Checklist.md      what to check and fill in before handing in
```

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
| 12 | `Bank`: 78 operations, each checking its rules and writing an audit event |
| 13 | Seeded demonstration on a simulated calendar (Jan 2026 to Feb 2027) |
| 14 | 49 automated tests |
| 15-16 | Class and UML diagram generators, command line |

## Where each requirement of the brief is met

| Required item | Where |
|---|---|
| Domain research summary | Report section 1 |
| Assumptions | Report section 2 (A1 to A28) |
| Requirements interpretation | Report section 3 |
| Class diagram | Report section 4: overview, 4 UML hierarchy and 3 association diagrams |
| Implementation (at least 30 classes and 30 operations) | `banking_system.py`: 67 domain classes, 78 operations; report section 5 |
| Multi-level inheritance explained | Report section 6 |
| At least three rejected inheritances | Report section 7 (ten given) |
| Seeded demonstration | `run_demo()`, `docs/demo_output.txt`, report section 8 |
| At least five complex scenarios | 13 scenarios, report section 9 |
| Limitations and scaling | Report section 10 |

## The brief's critical cases

| Critical case | Scenario | Test |
|---|---|---|
| Customer is personal and represents several organisations | 1, 7 | `test_same_person_is_never_duplicated_across_roles` |
| Transaction posted, reversed, re-posted differently, disputed | 4 | `test_repost_links_original_and_correction`, `test_partial_reversal_and_over_reversal`, `test_dispute_cannot_be_resolved_twice` |
| Product no longer sold but valid for old customers | 10 | `test_withdrawn_product_blocks_new_but_not_existing`, `test_terms_pinned_until_migration` |
| Person loses signing authority; history still shows it | 7 | `test_revoked_mandate_still_provable_for_past_dates` |
| Customer temporarily restricted then cleared | 5 | `test_restriction_blocks_then_lifts_with_history`, `test_risk_case_cannot_close_with_live_restriction` |
| Card replaced multiple times; old transactions searchable | 3, 10 | `test_stolen_replaced_card_cannot_be_reactivated` |
| Financing restructured after installments paid | 6 | `test_restructure_supersedes_schedule_and_keeps_paid` |
| Beneficiary changes after old transfers | 8 | `test_beneficiary_snapshot_survives_amendment` |
| Branch closes; customers and staff transferred | 11 | `test_branch_closure_moves_but_keeps_history`, `test_branch_closure_moves_vault_cash` |
| Compliance case references data later corrected | 9 | `test_correction_keeps_past_value`, `test_evidence_snapshot_is_not_rewritten_by_correction` |

## Notes

The bank, people and companies are fictional. All amounts are Pakistani rupees. Data is held in memory and rebuilt on each run.
