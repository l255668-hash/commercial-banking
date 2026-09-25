# Code review: analysis, defects found and fixes

This review covers the Problem 4 work that was supplied in two versions, and records how the single-file submission `banking_system.py` was produced from them.

## 1. What was reviewed

| Version | Structure | State found |
|---|---|---|
| A. `problem4_banking.zip` ("Indus Commercial Bank") | `backend/banking_model.py` (model), `demo.py`, `api.py`, `server.py`, web console, 38 tests | Ran; all 38 tests passed; PKR; double-entry ledger with a zero trial balance |
| B. `bank/` package ("Meridian Commercial Bank") | 15 modules: `core`, `parties`, `organisation`, `products`, `payments`, `cards`, `lending`, `compliance`, `reporting`, `demo`, `seed`, `service`, `serialisation`, `server`, `__init__` | Demo ran; **no tests**; web console (`web/`) and `support.py` missing, so 5 API routes crashed; currency GBP (£) in a Lahore bank |

**Decision.** The brief asks only for Problem 4 with classes and inheritance as the assessed concepts. Version A was used as the base because it already had the double-entry books, PKR amounts, tests and a report that matched it. Version B's good ideas that were missing from A were carried over (delegated credit limits, refusing overpayments before touching installments, vault cash moving on branch closure, a point-in-time "time machine" query). The web console, HTTP API and chatbot were dropped: they are not assessed, and the request was for a single code file.

## 2. Defects found in version B (not carried forward)

| # | Defect | Where |
|---|---|---|
| B1 | Any collections officer could restructure a loan of any size: `restructure()` called `assert_authority("RESTRUCTURE_CREDIT")` without the amount | `lending.py`, `organisation.py` |
| B2 | Withdrawn products and the "no new products" restriction were never enforced: nothing called `assert_can_open_for` or checked `OPEN_PRODUCT` | `products.py`, `compliance.py` |
| B3 | Only internal transfers were double-entry, so the bank's books could not balance | `payments.py`, `lending.py` |
| B4 | A dispute could raise its provisional credit twice | `compliance.py` |
| B5 | Closed cases had no terminal status and could be changed again | `compliance.py` |
| B6 | A compliance case could close while its restrictions were still in force | `compliance.py` |
| B7 | Operation numbers 36 and 41 to 43 were used twice; 138 to 158 were missing | several |
| B8 | Currency and nationality defaulted to GBP / "GB" | `core.py`, `parties.py` |
| B9 | Missing `web/` folder and `support.py`, so the console showed "not found" and `/api/support/*` crashed | `server.py`, `service.py` |

## 3. Defects found in version A and fixed in `banking_system.py`

Every fix has a regression test (run `python banking_system.py --test`).

| # | Defect (failure scenario) | Fix | Test |
|---|---|---|---|
| 1 | `repay_financing` allocated the money to installments **before** refusing an overpayment, so a refused repayment left installments marked as paid and the transaction stuck in `INITIATED` | Check the total outstanding first; refuse as `FAILED` with nothing changed | `test_overpayment_is_refused_without_touching_installments` |
| 2 | `resolve_dispute` posted the refund before checking whether the dispute was already closed, so resolving twice refunded twice and then raised | Check the dispute is open first; refund may not exceed the disputed amount | `test_dispute_cannot_be_resolved_twice` |
| 3 | `open_dispute` accepted any transaction (a fee crashed with `AttributeError`), any amount, and several open disputes on one payment | Only customer payments; amount within what is still standing; one open dispute at a time | `test_only_customer_payments_can_be_disputed` |
| 4 | `record_card_found` accepted an ACTIVE card and destroyed it | Only a blocked (lost, stolen, damaged) card can be found | `test_found_active_card_is_not_destroyed` |
| 5 | `replace_card` went through `issue_card`, which refused if the card product was withdrawn, so existing customers could not get a replacement | Replacement allowed for existing cardholders; new cards still refused | `test_replacement_allowed_after_card_product_withdrawn` |
| 6 | `reject_held_transaction` released the hold before checking the status: on a payment with no hold it crashed with `AttributeError` | Check `HELD_FOR_REVIEW` first | `test_reject_of_a_non_held_payment_is_refused_cleanly` |
| 7 | Savings withdrawal limit counted every debit, so bank fees used up the customer's monthly withdrawals | Count only customer-initiated debits (cash and customer payments) | `test_bank_fees_do_not_use_savings_withdrawals` |
| 8 | `close_account` ignored holds and payments in progress, crashed on a financing agreement, and left cards and standing orders running on a closed account | Refuse while money is on hold, pending, or settles live financing; cancel cards and standing orders on closure | `test_close_account_refuses_while_money_is_on_hold_or_pending`, `test_closing_an_account_cancels_its_cards_and_standing_orders` |
| 9 | A standing order for day 29 to 31 crashed with `ValueError` from `date.replace` | Days 1 to 28 only, with a clear error | `test_standing_order_day_must_exist_every_month` |
| 10 | `become_customer` with an employee who had no role crashed with `AttributeError` | Only branch staff may onboard (`AuthorityError`) | `test_only_branch_staff_can_onboard` |
| 11 | `record_employee_exit` on someone who had already left crashed with `AttributeError` | Clear `InvalidStateError` | `test_employee_cannot_leave_twice` |
| 12 | `close_branch` allowed merging a branch into itself or into a closed branch, left the vault cash stranded in the closed branch, and staff could still be hired there | Validate both branches; move vault cash with an `InternalTransfer`; refuse hiring at a closed branch | `test_branch_closure_moves_vault_cash`, `test_branch_closure_moves_but_keeps_history` |
| 13 | A settled financing agreement could still be restructured or settled again | Only `ACTIVE` / `IN_ARREARS` agreements; first due date must be in the future | `test_early_settlement_clears_principal` |
| 14 | Disbursement accepted any settlement account, even one not held by the borrower | The applicant must hold the settlement account, and it must accept credits | `test_disbursement_only_into_the_applicants_account` |
| 15 | Any credit officer could approve any amount, and more than was requested | Delegated limits per role (officer 5m, manager 25m); never more than requested | `test_credit_approval_respects_delegated_limit` |
| 16 | `authorise_payment` by an account holder without a mandate (possible on a joint person-and-company account) would crash when logging `mandate.mandate_id` | Refuse with `AuthorityError` (defensive guard) | none: not reachable with the seeded data |
| 17 | `cancel_pending_payment` let anyone cancel another company's payment | Only the initiator or another signatory with a live mandate | `test_only_a_signatory_may_cancel_a_pending_payment` |
| 18 | `migrate_terms` "migrated" an account already on the latest version and sent a pointless notice | Refuse | `test_terms_pinned_until_migration` |
| 19 | `verify_party` accepted another party's document | Document must belong to the party | `test_verification_needs_the_partys_own_document` |
| 20 | Negative or zero amounts, duplicate branch/product codes, unknown mandate capabilities, product categories and ownership percentages were accepted | Validated where the record is created | covered by the tests above |

Smaller improvements: `Period.close` refuses to end before it starts; `ProductDefinition.terms_on` picks the latest effective version even when versions are added out of date order; savings interest starts from the opening date for accounts opened mid-month; expired cards are declined; a reversal cannot itself be reversed; reference counters reset at the start of each demo run, so the output is reproducible.

## 4. Review against the brief (second pass)

After the defect fixes, the model was checked against every sentence of Problem 4. All ten critical cases were already covered; these gaps were found and closed:

| Brief says | Gap found | Change |
|---|---|---|
| Customers include "sole traders and high-value customers" | Only an assumption; never modelled | `SOLE_TRADER` and `PRIVATE` segments; trading name; enhanced due diligence (source of wealth); scenario 14 |
| "payment cards, issuance/replacement, **controls**" | Only a daily limit | `CardControl` (online, international, cash, merchant category) with periods; scenario 15 |
| "external merchants, **billers**" | No bill payments | `Biller`, `BillPayment` (same authority and dual-control rules); scenario 15 |
| "**collections** personnel" | Collections cases opened but nobody worked them | `COLLECTIONS_OFFICER`, `assign_case`, `record_collections_contact`, `PromiseToPay` marked kept or broken by the batch; scenario 6 |
| "**auditors** and management"; "audit of approvals and authority changes" | No auditor role or report | `AUDITOR` role, `approvals_and_authority_audit`; scenario 16 |
| Operations include "view ... **delete** ... **archive**" | No archive or delete operations | `archive_record`, `request_deletion` (refused with retention date), `delete_beneficiary` (only if never used); scenario 16 |
| Which similarities among savings, transaction facilities, cards, financing and **investments** justify inheritance | No term or investment-like product | `FixedTermDeposit(DepositAccount)` with maturity payout and early-break penalty; `OwnAccountTransfer`; scenario 14 |
| "one beneficial owner" | The demo had two owners above 25% | Ayesha's share recorded at 10% (below the threshold); scenario 1 prints who counts |
| Old card transactions "remain **searchable**" | No search | `search_transactions` covers the whole replacement chain; scenario 15 |
| Eight "questions the specification does not answer" | Answered, but scattered | Report section 3.1 answers each one; section 3.2 maps every participant and scope item |

Each change has a test in `BriefCoverageTests` (11 tests).

## 5. Verification

| Check | Result |
|---|---|
| `python banking_system.py --test` | 70 tests, all passing |
| Python versions | 3.10, 3.11, 3.12 and 3.13 run the tests green; the file parses as Python 3.9 |
| `pyflakes banking_system.py` | no warnings |
| `python banking_system.py` | all 16 scenarios run; 27 refusals, each naming its rule; trial balance total 0.00 |
| Brief minimums (checked by tests from the code) | 69 business classes plus 6 supporting classes (at least 30), 97 operations of which 79 are commands (at least 30), four multi-level hierarchies |
