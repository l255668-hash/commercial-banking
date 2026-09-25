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
Run `python banking_system.py --classes`: 67 domain classes, 7 error classes, 78 `Bank` operations, counted from the code. A test (`ModelShapeTests`) fails if either count drops below 30.

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
