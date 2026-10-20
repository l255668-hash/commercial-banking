# Viva study guide: explain it yourself

**Khizar Rizwan (25L-5668)**, Problem 4. Learn this page by page. The goal is to explain every part **without notes**, in your own words. Each section ends with a one-line summary in Roman Urdu to help you remember it.

How to study: read one section, close the file, explain it aloud, then open `banking_system.py` and find the code. Repeat until it is easy.

---

## Part A. The four inheritance hierarchies

The rule behind every decision: **inheritance only where the child truly *is a* kind of the parent, and the parent's data belongs to every child.** Everything else (cards, mandates, branches, employees) is linked by association.

### A1. Parties: `Party › Organization › Company / Charity`, and `Party › Person`

| Level | What it adds | Why it sits at this level |
|---|---|---|
| `Party` (abstract) | `party_id`, documents, verification checks, corrections, restrictions, the customer relationship; `kyc_gaps()` | Every person *and* organisation is identified, verified and can be restricted |
| `Person` | `date_of_birth`; no structural rules; no connected persons | A human has no board or owners |
| `Organization` (abstract) | `registration_no`, `officers`, `owners`, `mandates`; `connected_persons()`; `find_mandate()`; 25% `OWNERSHIP_THRESHOLD` | Only organisations have directors/trustees, owners and people acting for them |
| `Company` | `incorporated_on`; needs at least one active director | Governance rule of a company |
| `Charity` | needs at least 2 trustees (`MIN_TRUSTEES`) | Governance rule of a trust (assumption A4) |

**The template method.** `Party.kyc_gaps(on)` always runs three steps: (1) the party's own verification, (2) `structural_gaps(on)` from the subclass, (3) the KYC gaps of every `connected_persons(on)`. The steps are fixed in the parent, and each subclass fills in only steps 2 and 3. So onboarding a company automatically checks its directors and owners.

**Why `Person` and `Organization` are siblings, not parent and child:** an organisation is not a kind of person. They share only "can be identified and verified", and that is `Party`.

**Why there is no `Customer` subclass:** being a customer is a *role* that starts and ends. Ayesha is a customer, a director, an owner and a signatory at the same time. Roles are dated objects (`CustomerRelationship`, `OfficerRole`, `BeneficialOwnership`, `Mandate`).

*Roman Urdu: Party mein woh sab hai jo har insaan aur organisation ka hota hai; Organization directors aur mandates add karta hai; Company aur Charity sirf apna governance rule add karte hain.*

### A2. Arrangements: `Arrangement › DepositAccount › Current / Savings / FixedTermDeposit`, and `Arrangement › FinancingAgreement`

| Level | What it adds | Why |
|---|---|---|
| `Arrangement` (abstract) | `number`, `product`, pinned `terms` and `terms_history`, `holders`, branch history, `status`, restrictions; `position()` | Anything a customer holds under a product's terms |
| `DepositAccount` (abstract) | ledger `entries`, `holds`; `ledger_balance()`, `available_balance()`, `check_debit()` | Accounts that hold the customer's money |
| `CurrentAccount` | `overdraft_limit()` from its terms | May go overdrawn |
| `SavingsAccount` | overrides `check_debit()`: a monthly withdrawal limit | Savings restrict withdrawals |
| `FixedTermDeposit` | term, rate, maturity; overrides `check_debit()` (no withdrawal before maturity) and `ensure_usable()` (funded once) | Money locked for a term |
| `FinancingAgreement` | principal, repayment schedules (versioned), `outstanding_principal()`, `allocate()` | The bank's money lent to the customer |

**Each subclass changes one behaviour.** `SavingsAccount.check_debit` adds its own rule, then calls `super().check_debit(...)` for the shared funds check. That is inheritance doing real work.

**Why `FinancingAgreement` is not a `DepositAccount`:** it holds no customer money; it is money *owed*. It shares only "held by a customer under terms", so it is a sibling under `Arrangement`, and `position()` returns "held" for deposits but "owed" for financing.

**Why a card is not an `Arrangement`:** a card holds no money. It is a credential linked to an account (`IssuedCard`).

*Roman Urdu: Arrangement woh hai jo customer kisi product ki terms par rakhta hai; deposit accounts mein paisa hota hai, financing mein paisa wajib-ul-ada hota hai, is liye dono alag branches hain.*

### A3. Transactions: `BankTransaction › CustomerPayment › Transfer / Card / Bill / OwnAccount`, `BankTransaction › LoanTransaction › …`, `BankTransaction › Reversal › Chargeback`

| Level | What it adds |
|---|---|
| `BankTransaction` (abstract) | `txn_id`, amount, date, `status` (a lifecycle), ledger `entries`, `reversals`, `failure_reason`; `post()`, `net_amount()`, `story_lines()` (template method); abstract `counterparty()` |
| `CustomerPayment` (abstract) | `source_account`, `initiated_by`, channel, `mandate_used`, second-signatory `authorisations`, `disputes`; extra lifecycle states (awaiting authorisation, held for review) |
| `TransferPayment`, `CardPayment`, `BillPayment`, `OwnAccountTransfer` | Each adds its own counterparty: beneficiary *version*, card and merchant, biller, target account |
| `LoanTransaction` (abstract) | the `agreement`; children: disbursement, repayment, interest capitalisation |
| `Reversal` | the `original` transaction, reason, staff `approval` |
| `Chargeback(Reversal)` | the `dispute`, `merchant`, scheme `reason_code` |

**Why `Chargeback` extends `Reversal`:** a chargeback *is* a reversal of a card payment, with extra obligations (dispute and reason code). Both use one shared method, `Bank._counter_post`.

**Why `MerchantRefund` does *not* extend `Reversal`:** in a refund the merchant gives money back voluntarily, and the original purchase stays valid. Making it a reversal would wrongly mark the purchase as reversed.

*Roman Urdu: har transaction ka ledger aur status hota hai; customer payment mein mandate aur signatory aate hain; chargeback ek khaas qism ka reversal hai.*

### A4. Cases: `Case › CustomerCase › Complaint / Dispute / ServiceRequest`, `Case › RiskCase › FraudAlert / ComplianceInvestigation`, `Case › CollectionsCase`

| Level | What it adds |
|---|---|
| `Case` (abstract) | `case_id`, subject, summary, status, assignments, notes, evidence, links, outcome; abstract `handler_roles()` (who may work on it) |
| `CustomerCase` | channel and contact person; handled by branch staff |
| `RiskCase` | risk level and **restrictions**; handled by compliance; overrides `close()` so the case cannot close while one of its restrictions is still in force |
| `CollectionsCase` | the overdue agreement and promises to pay; handled by collections |

*Roman Urdu: har case ka record aur history ek jaisi hai; farq sirf yeh hai ke kaun us par kaam karta hai aur close hone par kya hota hai.*

---

## Part B. Five key methods, line by line

### B1. `Bank.initiate_transfer(account, beneficiary, amount, initiated_by)`

1. Create a `TransferPayment` and **store it immediately**, so even a refused payment is kept.
2. Check the beneficiary is active and belongs to this account's holder.
3. `_check_authority`: a personally restricted person is refused; an account holder needs no mandate; otherwise the organisation must have a live mandate with the PAYMENTS capability and a high enough limit (`find_mandate`). The mandate used is saved on the payment.
4. `account.check_debit(...)`: **polymorphism.** A savings account checks its monthly limit, a term deposit refuses before maturity, and all of them check available funds.
5. Any rule broken: `_fail` marks the payment FAILED, with the reason, and logs it.
6. If the amount is above the mandate's dual-control threshold, the status becomes AWAITING_AUTHORISATION and a second signatory must approve.
7. Otherwise `_complete_transfer`: a very large transfer gets a hold, becomes HELD_FOR_REVIEW and raises a fraud alert; a normal one is posted with two ledger legs (customer account minus, clearing account plus).

*Key sentence: "Every outcome (posted, waiting, held or failed) is a recorded state, never a deleted object."*

### B2. `Bank.reverse_transaction` and `Bank._counter_post`

1. Only staff in `REVERSAL_ROLES` may reverse.
2. A reversal cannot itself be reversed. Only POSTED or PARTIALLY_REVERSED transactions qualify.
3. The amount must be positive and at most what is still reversible (`net_amount`).
4. An `Approval` is recorded with the approver's role **at that time**.
5. A new `Reversal` (or `Chargeback`, the `kind` argument) posts **opposite legs** in proportion to the amount; rounding is absorbed in the bank's leg, so the books still sum to zero.
6. The original is marked REVERSED or PARTIALLY_REVERSED and keeps its own entries.

*Key sentence: "A reversal counteracts the original with new records; nothing is edited or deleted."*

### B3. `Bank.authority_on(org, person, on)`

One line: the person's mandates for that organisation whose `Period` contains the date. Because revoking a mandate **closes its period** instead of deleting it, this still answers correctly for any past date (scenario 7: Bilal, after he stopped being a director).

### B4. `Party.kyc_gaps(on)`: the template method

Fixed order: own verification against a document valid **on that date**, then `structural_gaps(on)` (Company: a director; Charity: 2 trustees), then each connected person's `kyc_gaps(on)` (directors, and owners of 25% or more). An empty list means onboarding may proceed. Checking "on a date" is why a document that expires mid-process blocks onboarding (scenario 1).

### B5. `Bank.repay_financing(agreement, amount, from_account)`

1. Create the `LoanRepayment` and store it.
2. **Every check runs before anything changes:** the agreement is usable, there is no overpayment, and the paying account has the funds. If any fails, the repayment is FAILED and no instalment is touched.
3. `allocate()` pays interest first, then principal, across the instalments.
4. Post three legs: customer account minus, loan principal plus, interest income plus.

---

## Part C. Questions to practise (answer aloud)

1. Why is `Customer` not a subclass of `Person`?
2. Name all your multi-level hierarchies.
3. What does `Organization` add that `Party` does not have?
4. Why is `FinancingAgreement` not a `DepositAccount`?
5. What is a template method? Show one in the code.
6. What happens to a refused payment?
7. Why is a reversal a new object?
8. Why is `MerchantRefund` not a `Reversal`, but `Chargeback` is?
9. How do you show authority that existed only in the past?
10. What is the difference between a product and an arrangement?
11. What does "deletion" mean in your system? (Archiving; deletion requests are refused with a retention date.)
12. Name three tempting inheritances you rejected, and why.
13. How do you know the books balance? (`trial_balance()` sums to zero; every posting has equal and opposite legs.)
14. Give one weakness of your design. (Section 10: single currency, saving only as one whole JSON file with no database, two-signatory dual control only.)
15. What design would be the plausible alternative, and why is yours better? (An account-centric model; report section 7.1.)

16. Are all 71 classes meaningful? (48 have their own behaviour, already above the 30 required; 20 are record classes that keep history; only 3 are small subclasses, each with a reason. Report section 5.1.)
17. How does saving work, and where is the inheritance? (`Repository` holds the JSON format; `JsonFileRepository` and `MemoryRepository` only decide where the text is kept. Links are saved as references, so shared objects stay shared. Report section 5.2.)

When you can answer all 17 without notes, you are ready.
