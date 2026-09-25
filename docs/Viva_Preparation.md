# Viva preparation: likely questions and how to answer them

These notes are for defending the design in person. Answer in your own words; the point is to show you understand why each decision was made, not to recite this page.

## Inheritance

**Why is there a `DepositAccount` level between `Arrangement` and `CurrentAccount`?**
Because holding customer money is a real difference. Current and savings accounts both have ledger entries, holds and an available balance. A financing agreement is also an arrangement but holds no customer money, so those attributes would be meaningless on it. Putting them on `DepositAccount` means `FinancingAgreement` inherits only what is true for it.

**What does each subclass of `DepositAccount` actually change?**
`CurrentAccount` overrides `overdraft_limit()`. `SavingsAccount` overrides `check_debit()` to add the monthly withdrawal limit and then calls the parent version, so the general checks (status, restrictions, funds) still run. That is extension rather than replacement. Only customer withdrawals count towards the limit; bank fees do not.

**Why is `Customer` not a subclass of `Person`?**
Being a customer is a role, not a kind of person. Ayesha is a customer, a director, an owner and a signatory at the same time, and those roles start and end on different dates. If each role were a subclass she would need several objects, or would have to change class when a role ended. Instead there is one `Person` and separate role objects (`CustomerRelationship`, `OfficerRole`, `Mandate`, `Employee`) with their own validity periods.

**Why does `RiskCase` exist when you already have `Case`?**
Risk cases are opened by the bank and can impose restrictions, and `RiskCase` overrides `close()` so a case cannot close while its own restriction is still in force. Customer cases never impose restrictions, so that rule belongs at the `RiskCase` level only.

**Why is `Organization` between `Party` and `Company`?**
Companies and charities both have officers, owners and mandates, and both are only verified if their connected people are verified (`Organization.kyc_gaps`). What differs is the governance rule: a company needs a director, a charity two trustees. That is `structural_gaps`, overridden in each subclass.

**Give one inheritance you rejected and why.**
`GeneralLedgerAccount` could have inherited from `DepositAccount` because both have entries. It does not, because the bank's books have no holder, product, terms or restrictions. Sharing one attribute is not enough reason to inherit a whole contract. (The report lists nine more.)

**When did you choose composition instead of inheritance?**
For behaviour many unrelated classes need: `StatusHistory` and `Period`. Accounts, cards, cases, branches and employees all have lifecycles, but they are not the same kind of thing, so each has a `StatusHistory` rather than inheriting from a common base.

**How many classes and operations, and how do you know?**
Run `python banking_system.py --classes`: 75 classes, 7 error classes, 97 `Bank` operations (79 of them state-changing commands), counted from the code. Six of the classes are supporting infrastructure (`Period`, `StatusChange`, `StatusHistory`, `Lifecycle`, `AuditEvent`, `Bank`), so the honest business count is 69; the printout says so. A test (`ModelShapeTests`) fails if the business class count or the operation count drops below 30.

**Which of your classes are abstract, and why?**
The root of each hierarchy: `Party`, `Arrangement`, `BankTransaction`, `Case`, plus the middle levels `Organization`, `DepositAccount`, `CustomerPayment` and `LoanTransaction`. The bank never holds something that is only "a transaction" or only "a party", so creating one raises `TypeError`. Each has at least one abstract method whose answer genuinely differs by class, e.g. `DepositAccount.overdraft_limit()` (current accounts read it from the terms, savings and term deposits are zero) and `BankTransaction.counterparty()`. `CustomerCase` and `RiskCase` are concrete because each fully answers `handler_roles()`.

**What is the difference between `[implements]` and `[override]` in your UML?**
`[implements]` fills in a parent's abstract method, which has no body to reuse. `[override]` replaces or extends a working parent method, for example `SavingsAccount.check_debit` adds the withdrawal limit and then calls `super().check_debit`.

**Show me polymorphism in your code.**
`Bank.transaction_story(txn)` is now just `return txn.story_lines()`. `story_lines` is a template method in `BankTransaction`; `CustomerPayment.detail_lines` adds who initiated it and the mandate used, and `TransferPayment` and `CardPayment` extend that with `super()` to add the beneficiary snapshot or the card. The `Bank` no longer asks what type the transaction is. `assign_case` does the same with `case.handler_roles()`.

**What stops a destroyed card being used again?**
`IssuedCard.LIFECYCLE` declares the allowed moves, and `StatusHistory.change` refuses anything else. DESTROYED is a final state with no way out, so even code that bypasses `Bank.reactivate_card` and calls `card.status.change("ACTIVE", ...)` gets `InvalidStateError`. A test does exactly that.

**How are state machines inherited?**
`LIFECYCLE` is a class constant, so subclasses inherit it. `CashTransaction` uses `BankTransaction`'s as is; `CustomerPayment` calls `.extend(...)` to add dual control; `TransferPayment` extends that with the compliance hold. `FinancingAgreement` replaces `Arrangement`'s lifecycle completely, because a loan is settled, not closed. State machine 1 colours each status by the class that added it.

## Historical correctness

**How do you prove a payment was authorised after the signatory has left?**
The payment stores a reference to the exact `Mandate` it used. The mandate is never deleted; its `Period` is closed when revoked. So for any past date the model can answer who had authority, and the payment's own record shows which mandate it relied on. Scenario 7 shows this with TRF-012.

**Why does an old credit decision still say "Credit officer" after Zainab was promoted?**
`Approval` copies the role and branch at the moment of the decision. Pointing at the employee's current role would rewrite history.

**What happens to old transfers when a beneficiary changes bank details?**
Amending creates a new `BeneficiaryVersion`. Each transfer stores the version it was sent with, so old transfers still show the old bank.

**How is a correction different from an update?**
A `Correction` records the old value, new value, date, person and reason. `detail_on(field, date)` returns what the bank held on that date. Case evidence stores a snapshot, so a compliance case keeps the address it actually relied on.

**How do you undo a posted payment?**
You never edit it. A `Reversal` is a new transaction with its own amount, date, reason and approval. Partial and repeated reversals are allowed up to what remains; a reversal cannot itself be reversed.

**What does "delete" mean here?**
Nothing with history is deleted. Closing an account, ending a relationship, revoking a mandate or withdrawing a product is a status change or a closed period. Scenario 12 closes a savings account and all its entries remain.

## Money and rules

**How do you know the books are right?**
Every posting must balance: credits positive, debits negative, and `post()` refuses anything that does not sum to zero. So the trial balance is zero on every date. Tests check this and the demo prints it.

**What happens to a payment that fails a rule?**
If it got as far as being a payment, it is kept with status FAILED or DECLINED and a reason. Nothing is silently dropped.

**Who may approve financing?**
Credit staff within their delegated limit: an officer up to PKR 5m, a manager up to PKR 25m. Scenario 6 shows an 8m request refused for the officer.

**Why is a fixed-term deposit a `DepositAccount`, but a card is not?**
A term deposit holds customer money, so it reuses the ledger, holds and balances unchanged and only overrides two rules: no debits before maturity (`check_debit`) and only one credit, the placement (`ensure_usable`). A card holds no money; many cards can draw on one account, so it is a credential that points to an account.

**How is a sole trader different from a company?**
A sole trader has no separate legal personality, so it is a `Person` in the `SOLE_TRADER` segment with a trading name. Making it an `Organization` would wrongly suggest a separate entity with its own liability and officers.

**What does "delete" do in your system?**
`request_deletion` is always refused and logged with the retention date (10 years after closure). Finished records can be archived: they leave the working lists but stay in every registry and report. The only real delete is a payee nobody ever paid, because nothing refers to it.

**How does the auditor see who approved what?**
`approvals_and_authority_audit` lists every staff `Approval` with the role held at the time, plus every mandate, officer and role change from the audit log. Only auditors and branch managers may run it, and each run is itself logged (scenario 16).

**Where are the business rules - in the GUI or the model?**
Only in the model. The GUI's `BankController.run` calls one `Bank` operation and translates the result: a `BankingError` becomes a red "blocked" banner naming the error class; a FAILED or DECLINED transaction becomes "refused, kept on record". The GUI never sets an attribute on a domain object.

**What happens to the forms when you press "Reset data"?**
They keep working on the new bank. The forms are built once, so they hold a `CurrentBank` stand-in that looks up `controller.bank` on every call instead of capturing the old object. The GUI smoke test resets the bank between its passes to check exactly this.

**Why does a bank console show a class model and a scenario log?**
It doesn't mix them in: the sidebar has a "Bank" section with the ten screens staff would use, and a separate "Teaching & simulation" section with the class model and the scenario log. The brief says the model is for teaching and simulation, and those two screens let you see the inheritance tree and the seeded scenarios live. A real bank's staff application would not include them, which is why they are labelled as teaching aids. An earlier screen that displayed the diagram images was removed for that reason.

**Why is `Merchant` not a `Party`?**
The bank does no KYC on merchants; the merchant's own bank (the acquirer) does. We only record what card controls, disputes and fraud review need: name, category and country, and a link to every card payment made there. A shared `Counterparty` superclass with `Biller` was rejected too: they share only a name.

**Why does the GUI have its own inheritance?**
Every list screen has the same layout (table left, details right, refresh on show), so that lives once in `MasterDetailPage`; each subclass only declares its columns and how to draw one record. Same reasoning as `DepositAccount` in the model.

## Flowcharts

**What do your flowcharts add to the class diagrams?**
The class diagrams show structure: which classes exist and what each level adds. The flowcharts show behaviour: the order in which a method checks its rules and where a refusal ends the flow. Six are given (report section 4.1): program overview, onboarding, transfer, card purchase, financing lifecycle and the GUI.

**Why those shapes?**
They are the standard flowchart symbols (ISO 5807): a stadium for start and end, a rectangle for a step, a diamond for a yes/no decision, a parallelogram for input or output, a double-sided rectangle for a named operation defined elsewhere (for example `post()`), and a cylinder for stored data (the ledger and audit log). Red terminators mark flows that a rule ended, and every diamond has exactly one Yes exit and one No exit.

**How do you know the flowchart matches the code?**
Each chart was traced from the method it describes. In Flowchart 3 the diamonds follow `initiate_transfer`: beneficiary, then authority (mandate and limit), then funds, then dual control, then the PKR 1,000,000 hold. Change the order in the code and the chart would be wrong, so they are drawn by a script (`tools/make_flowcharts.py`) kept next to the code.

**Why does a refused card purchase end in a terminator but still reach the records?**
Because the purchase is created before the checks run (`CardPayment` remembers the exact card), so a refusal changes its status to DECLINED instead of discarding it. The red terminator means the flow ended, not that the record disappeared.

## The code review

**What bugs did you find and fix?**
Twenty are listed in `docs/Code_Review.md`, each with a regression test. Good examples: a refused loan overpayment used to mark installments as paid before failing; resolving a dispute twice used to refund twice; a card "found" while still active used to be destroyed; bank fees used up a customer's savings withdrawals.

## Scope and limits

**What would you change for a real bank?**
Store the data in a database with effective-dated tables (the `Period` class maps to valid-from and valid-to columns), split the `Bank` class into services, add authentication so the acting person comes from the login, and replace the fixed review threshold with risk scoring.

**What is deliberately simplified?**
Single currency, simple interest calculations, two-signatory dual control only, two credit authority levels and in-memory storage. These are listed in report section 10.

## Before the viva

Run `python banking_system.py` and read the output once alongside report section 9. Run `python banking_system.py --test`. Be able to explain `Arrangement`, `DepositAccount`, `SavingsAccount.check_debit`, `Bank.initiate_transfer`, `Bank.reverse_transaction` and `Bank.repay_financing` line by line. Check that the source list in report section 1 matches documents you have actually looked at.
