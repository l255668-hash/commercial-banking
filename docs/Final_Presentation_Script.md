# Final presentation (30 minutes): script and demo plan

**Khizar Rizwan (25L-5668)**, Problem 4. Slides: `docs/Viva_Presentation.pptx` (24 slides; English speaker notes on each).

For a 30-minute talk, use talking points rather than a word-for-word speech. Learn the points below in your own words; they are in Roman Urdu with the technical terms in English, as you would say them. For the details behind any point, see `docs/Viva_Study_Guide.md`.

## Time plan

| Part | Slides | Time |
|---|---|---|
| Opening, agenda, research | 1–4 | 0:00–3:15 |
| Scale and core rule | 5–6 | 3:15–5:00 |
| Class model and the four hierarchies | 7–12 | 5:00–10:30 |
| Design decisions: rejected inheritances, the alternative, SOLID | 13–15 | 10:30–13:15 |
| Behaviour: scenarios, coverage, flowcharts, sequence diagram | 16–19 | 13:15–16:00 |
| Saving and the assistant | 20 | 16:00–16:45 |
| No libraries: own building blocks, IBAN and card checks | 21 | 16:45–17:30 |
| **Live demonstration** | 22 | 17:30–25:00 |
| Code review, limitations, close | 23–24 | 25:00–26:45 |
| Questions | — | 27:00–30:00 |

If you are behind time, shorten slides 17 and 23; never cut the hierarchies (7–12) or the demo. These are what the brief marks.

## Talking points

**1. Title (0:00–0:30).** Assalam-o-Alaikum. Main Khizar Rizwan, roll number 25L-5668. Mera project Problem 4 hai: commercial bank ka object-oriented model. Bunyadi khayal: jo kuch hua, woh kabhi delete nahi hota.

**2. Agenda (0:30–1:00).** Pehle research, phir class model aur hierarchies, phir design decisions, phir scenarios, phir live demo, aakhir mein limitations. Yeh tarteeb brief ke "Required Submission" ke mutabiq hai.

**3. Research sources (1:00–2:15).** Aath banking sources: FATF, State Bank of Pakistan, Basel, ISO 20022, Visa/Mastercard, IFRS 9, BIAN, Fowler. Har ek ka ek sabaq batayein (slide par likha hai). Neeche likha hai ke chaar standards code ke peeche hain (IBAN, card numbers, PCI DSS, Money/JSON/xUnit); unki baat slide 21 par karein. *Sirf woh source batayein jo aap ne khud parha ho.*

**4. Research changed the design (2:15–3:15).** Har row: pehla khayal → research ne kya dikhaya → design. Sab se wazeh misaal: Customer subclass nahi, kyunke KYC mein customer, director, signatory ek hi insaan ke roles hain. Aakhri row: payee ka account number ab IBAN hai, jis ke check digits ghalat type kiya hua number pakar lete hain.

**5. At a glance (3:15–4:00).** Ek file, koi library nahi. 74 business classes, 98 operations, 4 multi-level hierarchies, 16 scenarios, 84 tests, trial balance 0.00. Brief 30 classes maangta hai; sirf woh 51 classes jin ka apna behaviour hai, woh bhi 30 se zyada hain (report 5.1).

**6. Core rule (4:00–5:00).** Chaar tareeqe: Period (mandate ki validity), StatusHistory (har status ki date), Versions (terms, payee details), Counter-records (Reversal naya record hai). Is liye "date X par kya sach tha" hamesha answer ho sakta hai.

**7. Class model overview (5:00–5:45).** Chaar hierarchies: Party, Arrangement, BankTransaction, Case. Baqi classes (Mandate, ProductDefinition, IssuedCard, Employee) association se jurri hain, kyunke related hain magar ek doosre ki qism nahi.

**8. Parties (5:45–6:45).** Party → Organization → Company / Charity; Party → Person. Organization officers, owners aur mandates add karta hai. `kyc_gaps()` template method hai: apni verification, phir subclass ka rule, phir connected persons.

**9. Arrangements (6:45–7:45).** DepositAccount ledger aur balance add karta hai; har subclass ek rule badalti hai (SavingsAccount monthly limit, FixedTermDeposit maturity). FinancingAgreement sibling hai, kyunke us mein customer ka paisa nahi, wajib-ul-ada paisa hai.

**10. Transactions (7:45–8:45).** CustomerPayment mandate aur second signatory add karta hai. Reversal → Chargeback: chargeback ek khaas reversal hai. MerchantRefund reversal nahi, kyunke purchase valid rehti hai.

**11. Cases (8:45–9:30).** Case ki history sab mein same; RiskCase restrictions rakhta hai aur jab tak restriction live ho, close nahi ho sakta (scenario 5).

**12. Abstract classes and lifecycles (9:30–10:30).** Roots abstract hain. Har class apna LIFECYCLE declare karti hai; StatusHistory ghalat move refuse karta hai; subclasses lifecycle extend karti hain. State diagram code se draw hota hai.

**13. Rejected inheritances (10:30–11:30).** Customer(Person), IssuedCard(DepositAccount), FinancingAgreement(DepositAccount), MerchantRefund(Reversal), har ek ki wajah. Report mein 14 hain.

**14. The alternative (11:30–12:15).** Account-centric model (flags aur edits) aasaan hai, magar purani history mita deta hai: brief ke dason critical cases mein fail.

**15. SOLID and patterns (12:15–13:15).** Course ke SOLID principles ko checklist ki tarah poore code par lagaya, aur do masle mile jo fix kiye. Pehla: `open_deposit_account` mein `is FixedTermDeposit` check tha, is liye FixedTermDeposit ki koi subclass payout-account rule chhor deti; ab yeh class constant hai jo har term deposit inherit karta hai, aur ek test nayi `IslamicTermDeposit` subclass bana kar dikhata hai ke Bank badle baghair chalta hai. Doosra: `resolve_dispute` ab payment se poochta hai (`dispute_refund()`): card payment Chargeback deta hai, baqi Reversal. Liskov: SavingsAccount zyada debits refuse karta hai magar usi BankingError se, is liye har caller chalta rehta hai. Imandari se kahein: `Bank` class bari hai; bare bank mein yeh services mein toot jayegi (report 6.4).

**16. Scenarios (13:15–14:00).** 16 scenarios; brief ke saare 10 critical cases. Do misaalein dein: expire hone wala document onboarding rokta hai; stolen card, replacement, purana card mil jata hai.

**17. Everything the brief names (14:00–14:30).** Sole trader, term deposits, card controls, billers, collections, auditors: har cheez ka class aur test hai (report 3.2). *Waqt kam ho to yeh slide chhota karein.*

**18. Flowcharts (14:30–15:15).** Transfer flowchart: beneficiary, authority, funds, dual control, compliance hold, usi tarteeb mein jaise code check karta hai. Red end = refused, magar record mein rehta hai.

**19. Sequence diagram (15:15–16:00).** Yeh scenario 2 ka TRF-002 hai: teen din, teen log. Hamza payment shuru karta hai, Ayesha second signatory ke taur par approve karti hai, Kamran compliance se release karta hai. Dikhayein ke har qadam par mandate aur funds dobara check hote hain, kyunke beech mein badal sakte hain. Diagram ka script demo ke apne records se label bharta hai, aur agar status trail na mile to diagram banane se inkaar karta hai (report 4.3).

**20. Saving and the assistant (16:00–16:45).** Repository → JsonFileRepository / MemoryRepository: format parent mein, subclass sirf jagah batati hai. Assistant → OfflineAssistant → ClaudeAssistant: sirf parhta aur form bharta hai, Run insaan dabata hai.

**21. No libraries (16:45–17:30).** Program sirf `sys` import karta hai; ek test file ka apna source parh kar yeh check karta hai. Jo kaam library karti, woh meri apni class karti hai: `Exact` → `Money` (paisa tak round, float kabhi nahi), `Date`, `Abstract`, `Json`/`JsonReader`, `TestCase`/`TestRunner`. `Money` inheritance ki chhoti misaal hai: `Exact` ka saara hisaab inherit, sirf paisa rounding ka rule add. Research se do checks: IBAN ke check digits (97 se taqseem karke 1 bachta hai) aur card number ka Luhn digit; bank card ke sirf pehle 6 aur aakhri 4 digits rakhta hai (PCI DSS).

**22. Live demo (17:30–25:00).** Follow the demo path below.

**23. Code review (25:00–25:45).** Asal code mein 20 defects mile, har ek ka fix aur test hai (docs/Code_Review.md). *Waqt kam ho to chhota karein.*

**24. Limitations and close (25:45–26:45).** Aaj: single currency, ek JSON file (database nahi), sirf do signatories. Bara bank: database, services, login, Islamic products naye Arrangement subclasses ke taur par. Shukriya, sawalat?

## Live demo path (7½ minutes)

**Before the class:**
1. Run `python banking_system.py --test` (expect "Ran 84 tests ... OK").
2. Run `python banking_system.py --save backup.json`. If anything goes wrong during the demo, press **Open** in the top bar and choose `backup.json` to restore the seeded bank.
3. Start `python banking_gui.py` once to check that it opens, then close it.

**During the demo** (each step just under a minute):

1. **Sign in as staff.** Choose *Kamran Javed* and press *Sign in to the console*. On the Overview, point at the two payments in "Needs attention" (one waiting for a 2nd signatory, one held for review) and the trial balance of 0.00.
2. **A rule refusing an action.** Open *Operations*, then the *Guided rule checks* tab, and run one check. Point out that the refusal names the model's rule.
3. **History.** Open *Customers*, then *Ayesha Khan*: one Person with many roles, and the timeline. Then *Cards*, then *CARD-001*: the status steps (Active → Blocked (stolen) → Destroyed) and the replacement chain.
4. **Digital banking, refused.** Press *Switch user*, choose *Noor Fatima* and press *Sign in to digital banking*. Try a payment: it is refused because she is view-only, and the attempt is kept.
5. **Dual control.** Sign in as *Hamza Sheikh* and pay PKR 1,200,000 to a payee: it waits for a second signatory.
6. **Approval.** Sign in as *Ayesha Khan*, open *Approvals*, and approve Hamza's payment.
7. **Assistant.** Sign in to the console as any member of staff, open *Assistant*, and ask "Why was BIL-002 refused?". Then ask "Deposit 5,000 into CUR-001", press *Open the filled form*, check it and press *Run operation*.
8. **Saving.** Press *Save* in the top bar, then *Open* the same file: the bank comes back exactly.

**If the GUI fails:** stay calm. Run `python banking_system.py` and scroll through the scenario output, or show the screenshots in `docs/screenshots/` (slide 22 also has one). Say what you would have shown; the marks are for the design, not for a perfect click.

## Questions

Practise the 25 questions at the end of `docs/Viva_Study_Guide.md`. If you do not know an answer, say what you do know, and say that you would check the code. Never invent an answer.
